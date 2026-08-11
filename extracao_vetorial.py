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


def _extract_page(page, numero, coletor):
    canvas = _canvas(page)
    area_pagina = max(page.rect.width * page.rect.height, 1.0)
    linhas=[]; retangulos=[]; curvas=[]; textos=[]

    # Texto estruturado diretamente do PyMuPDF.
    for w in page.get_text('words') or []:
        x0,y0,x1,y1,text = map(lambda z: z, w[:5])
        text = str(text).strip()
        if not text: continue
        h = max(float(y1-y0), 0.0)
        if h < CONFIG['tam_min_fonte']: continue
        textos.append({'x':float((x0+x1)/2), 'y':float((y0+y1)/2),
                       'x0':float(x0),'y0':float(y0),'x1':float(x1),'y1':float(y1),
                       'texto':text,'tam':h,'pagina':numero})

    for path in page.get_drawings() or []:
        stroke = _color_tuple(path.get('color'))
        width = float(path.get('width', 0.0) or 0.0)
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
                    r=item[1]
                    x0,y0,x1,y1=map(float,(r.x0,r.y0,r.x1,r.y1))
                    area=abs((x1-x0)*(y1-y0))
                    if area >= area_pagina*CONFIG['area_min_componente_relativa']:
                        retangulos.append({'x0':x0,'y0':y0,'x1':x1,'y1':y1,
                                            'width':abs(x1-x0),'height':abs(y1-y0),
                                            'area':area,'linewidth':width,
                                            'fill':_color_tuple(path.get('fill')),
                                            'color':stroke,'pagina':numero})
                elif kind in ('c','qu'):
                    curvas.append({'tipo':kind,'pagina':numero,'stroke':stroke,'fill':_color_tuple(path.get('fill'))})
            except Exception as e:
                coletor.adicionar_aviso(f'Primitiva {kind} ignorada: {e}')
    return {'linhas':linhas,'textos':textos,'retangulos':retangulos,'curvas':curvas,
            'canvas':canvas,'width':canvas[2],'height':canvas[3]}


@monitorar(modulo='M2')
def extrair_primitivas_vetorial(caminho_pdf):
    if not caminho_pdf or not isinstance(caminho_pdf,str):
        raise ErroExtracao('Caminho do PDF inválido', severidade=Severidade.CRITICA)
    coletor=ColetorErros(); dados={}
    try:
        doc=pymupdf.open(caminho_pdf)
    except Exception as e:
        raise ErroExtracao(f'Não foi possível abrir o PDF: {e}', severidade=Severidade.CRITICA, causa=e)
    try:
        for i,page in enumerate(doc):
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
