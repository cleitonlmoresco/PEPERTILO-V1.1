"""M2 - Extração vetorial unificada usando PyMuPDF.

A saída é uma representação comum consumida pelo M5: linhas, textos,
retângulos, curvas e metadados da página. O módulo aceita hairline PDFs
(linewidth=0) e não depende de pdfplumber para a geometria.
"""
import math
import pymupdf
from logger_erros import logger, monitorar, ErroExtracao, Severidade, ColetorErros
from utils import to_native

CONFIG = {
    'area_min_componente_relativa': 0.00002,
    'tam_min_fonte': 3,
    'dist_max_emenda': 4.0,
}


def _canvas(page):
    return (0.0, 0.0, float(page.rect.width), float(page.rect.height))


def _inside(x, y, c):
    return c[0] <= x <= c[2] and c[1] <= y <= c[3]


def _color_tuple(value):
    if value is None: return None
    try: return tuple(float(v) for v in value[:3])
    except Exception: return None


def _agrupar_palavras(palavras, gap_max=6.0, tol_linha=2.5):
    """Agrupa palavras vizinhas na mesma linha visual (ex.: 'PINO 1').

    `get_text('words')` separa rótulos com espaço; sem agrupar, o pipeline
    usa apenas a primeira palavra e o rótulo fica longe do fim do fio.
    O critério é a distância horizontal real entre as palavras, não só a
    coordenada vertical (que juntaria rótulos distantes na mesma altura).
    """
    grupos=[]
    for w in sorted(palavras, key=lambda p:(p['y0'],p['x0'])):
        texto=str(w.get('texto','')).strip()
        if not texto: continue
        cy=(w['y0']+w['y1'])/2.0
        for g in grupos:
            if abs(g['cy']-cy) > tol_linha:
                continue
            if w['x0']-g['x1'] > gap_max or w['x0'] < g['x0']:
                continue
            g['x1']=max(g['x1'],w['x1'])
            g['y0']=min(g['y0'],w['y0'])
            g['y1']=max(g['y1'],w['y1'])
            g['cy']=(g['y0']+g['y1'])/2.0
            g['texto']=f"{g['texto']} {texto}"
            g['tam']=max(g['tam'],w['y1']-w['y0'])
            break
        else:
            grupos.append({'x0':w['x0'],'x1':w['x1'],'y0':w['y0'],'y1':w['y1'],
                           'cy':cy,'texto':texto,'tam':w['y1']-w['y0']})
    return grupos


def _bezier_segmentos(p0, p1, p2, p3, passos=6):
    """Aproxima uma curva de Bézier por segmentos de reta.

    Diagramas CAD frequentemente desenham fios como curvas. Antes elas eram
    descartadas e o grafo ficava sem os segmentos que ligam pino e periférico.
    """
    pts=[p0]
    for i in range(1, passos+1):
        t=i/passos
        u=1.0-t
        x=u*u*u*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t*t*t*p3[0]
        y=u*u*u*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t*t*t*p3[1]
        pts.append((x,y))
    return [(pts[i],pts[i+1]) for i in range(len(pts)-1)]


def _retangulo_do_path(path):
    """Reconstrói uma caixa desenhada como path fechado de retas.

    `page.get_drawings()` só entrega um item `re` quando o produtor do PDF usa
    o operador de retângulo. Muitos CADs desenham a ECU como 4 linhas + `h`;
    nesse formato a caixa não aparecia em `retangulos` e a ECU nunca era
    detectada.
    """
    items=path.get('items') or ()
    if len(items) < 4:
        return None
    if any(it[0] not in ('m','l') for it in items):
        return None
    fechado=bool(path.get('closePath'))
    if not fechado:
        try:
            fechado=(items[0][1] == items[-1][-1])
        except Exception:
            fechado=False
    if not fechado:
        return None
    pontos=set()
    for it in items:
        for p in it[1:]:
            try: pontos.add((round(float(p.x),2), round(float(p.y),2)))
            except Exception: return None
    xs={p[0] for p in pontos}; ys={p[1] for p in pontos}
    if len(xs)!=2 or len(ys)!=2:
        return None
    if not all((x,y) in pontos for x in xs for y in ys):
        return None
    x0,x1=sorted(xs); y0,y1=sorted(ys)
    if abs(x1-x0) < 0.5 or abs(y1-y0) < 0.5:
        return None
    return (x0,y0,x1,y1)


def _extract_page(page, numero, coletor):
    canvas = _canvas(page)
    area_pagina = max(page.rect.width * page.rect.height, 1.0)
    linhas=[]; retangulos=[]; curvas=[]; textos=[]

    # Texto estruturado diretamente do PyMuPDF, agrupado por linha visual.
    palavras=[]
    for w in page.get_text('words') or []:
        try:
            x0,y0,x1,y1,text = float(w[0]),float(w[1]),float(w[2]),float(w[3]),str(w[4])
        except (TypeError,ValueError,IndexError):
            continue
        text=text.strip()
        if not text: continue
        if max(y1-y0,0.0) < CONFIG['tam_min_fonte']: continue
        palavras.append({'x0':x0,'y0':y0,'x1':x1,'y1':y1,'texto':text})
    for g in _agrupar_palavras(palavras):
        textos.append({'x':float((g['x0']+g['x1'])/2), 'y':float((g['y0']+g['y1'])/2),
                       'x0':float(g['x0']),'y0':float(g['y0']),
                       'x1':float(g['x1']),'y1':float(g['y1']),
                       'texto':g['texto'],'tam':float(g['tam']),'pagina':numero})

    vistos=set()
    for path in page.get_drawings() or []:
        stroke = _color_tuple(path.get('color'))
        width = float(path.get('width', 0.0) or 0.0)
        tem_re=False
        for item in path.get('items', ()):
            if not item: continue
            kind=item[0]
            try:
                if kind == 'l':
                    p1,p2=item[1],item[2]
                    x1,y1=float(p1.x),float(p1.y); x2,y2=float(p2.x),float(p2.y)
                    if math.hypot(x2-x1,y2-y1) <= 0.01: continue
                    linhas.append(((x1,y1),(x2,y2)))
                elif kind == 're':
                    tem_re=True
                    r=item[1]
                    x0,y0,x1,y1=map(float,(r.x0,r.y0,r.x1,r.y1))
                    area=abs((x1-x0)*(y1-y0))
                    chave=(round(x0,1),round(y0,1),round(x1,1),round(y1,1))
                    if area >= area_pagina*CONFIG['area_min_componente_relativa'] and chave not in vistos:
                        vistos.add(chave)
                        retangulos.append({'x0':x0,'y0':y0,'x1':x1,'y1':y1,
                                            'width':abs(x1-x0),'height':abs(y1-y0),
                                            'area':area,'linewidth':width,
                                            'fill':_color_tuple(path.get('fill')),
                                            'color':stroke,'pagina':numero})
                elif kind == 'c':
                    curvas.append({'tipo':kind,'pagina':numero,'stroke':stroke,
                                   'fill':_color_tuple(path.get('fill'))})
                    p0=(float(item[1].x),float(item[1].y))
                    p1=(float(item[2].x),float(item[2].y))
                    p2=(float(item[3].x),float(item[3].y))
                    p3=(float(item[4].x),float(item[4].y))
                    for a,b in _bezier_segmentos(p0,p1,p2,p3):
                        if math.hypot(b[0]-a[0],b[1]-a[1]) > 0.01:
                            linhas.append((a,b))
                elif kind == 'qu':
                    curvas.append({'tipo':kind,'pagina':numero,'stroke':stroke,
                                   'fill':_color_tuple(path.get('fill'))})
            except Exception as e:
                coletor.adicionar_aviso(f'Primitiva {kind} ignorada: {e}')
        if not tem_re:
            caixa=_retangulo_do_path(path)
            if caixa:
                x0,y0,x1,y1=caixa
                chave=(round(x0,1),round(y0,1),round(x1,1),round(y1,1))
                area=abs((x1-x0)*(y1-y0))
                if area >= area_pagina*CONFIG['area_min_componente_relativa'] and chave not in vistos:
                    vistos.add(chave)
                    retangulos.append({'x0':x0,'y0':y0,'x1':x1,'y1':y1,
                                        'width':abs(x1-x0),'height':abs(y1-y0),
                                        'area':area,'linewidth':width,
                                        'fill':_color_tuple(path.get('fill')),
                                        'color':stroke,'pagina':numero})
    return {'linhas':linhas,'textos':textos,'retangulos':retangulos,'curvas':curvas,
            'canvas':canvas,'width':canvas[2],'height':canvas[3]}


@monitorar(modulo='M2')
def extrair_primitivas_vetorial(caminho_pdf, limite_paginas=0):
    if not caminho_pdf or not isinstance(caminho_pdf,str):
        raise ErroExtracao('Caminho do PDF inválido', severidade=Severidade.CRITICA)
    coletor=ColetorErros(); dados={}
    try:
        doc=pymupdf.open(caminho_pdf)
    except Exception as e:
        raise ErroExtracao(f'Não foi possível abrir o PDF: {e}', severidade=Severidade.CRITICA, causa=e)
    try:
        for i,page in enumerate(doc):
            if limite_paginas and i >= limite_paginas:
                logger.info(f'Limite de {limite_paginas} páginas atingido.', extra={'modulo':'M2'})
                break
            try:
                dados[i+1]=to_native(_extract_page(page,i+1,coletor))
                d=dados[i+1]
                if not d['linhas'] and not d['textos'] and not d['retangulos']:
                    coletor.adicionar_aviso(f'Página {i+1}: nenhuma primitiva útil')
            except Exception as e:
                coletor.adicionar_erro(ErroExtracao(f'Erro na página {i+1}: {e}',causa=e),severidade=Severidade.MEDIA)
    finally:
        doc.close()
    if not dados:
        raise ErroExtracao('Nenhuma página foi extraída com sucesso',severidade=Severidade.CRITICA,dados_extra=coletor.resumo())
    logger.info(f'Extração vetorial concluída: {len(dados)} páginas',extra={'modulo':'M2'})
    return dados

if __name__=='__main__':
    import sys
    r=extrair_primitivas_vetorial(sys.argv[1])
    for p,d in r.items(): print(p,len(d['linhas']),len(d['textos']),len(d['retangulos']))
