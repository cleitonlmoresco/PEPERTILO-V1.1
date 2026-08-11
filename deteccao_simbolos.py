"""
Módulo 4 - Detecção de Símbolos em Imagens Restauradas.
Recebe imagem binarizada/esqueletizada do Módulo 3 e identifica
componentes, pinos, textos e emendas com monitoramento de desempenho.
"""

import cv2
import numpy as np
import re
import time
import traceback
import os
import warnings
import pytesseract
from logger_erros import logger, monitorar, ErroExtracao, ErroPipeline, Severidade
from utils import to_native

# Suprimir warnings
warnings.filterwarnings('ignore')
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Configuração Tesseract
if os.name == 'nt':
    caminho_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(caminho_tesseract):
        pytesseract.pytesseract.tesseract_cmd = caminho_tesseract

CONFIG = {
    'area_min_componente': 300,      # reduzido para capturar retângulos menores
    'area_min_emenda': 10,
    'area_max_emenda': 200,
    'circularidade_min': 0.7,
    'dist_pino_borda': 15,
    'tam_min_fonte': 6,
}

RE_PINO = re.compile(r'^[A-Z]\d{1,2}$')

# Singleton PaddleOCR
_ocr_instance = None

def get_paddle_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("Inicializando PaddleOCR (singleton)...", extra={'modulo': 'M4'})
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang='en')
        except Exception as e:
            logger.warning(f"PaddleOCR não disponível: {e}", extra={'modulo': 'M4'})
            _ocr_instance = None
    return _ocr_instance

def extrair_retangulos(binaria, canvas):
    # Aplica Canny para realçar bordas
    bordas = cv2.Canny(binaria, 50, 150)
    contornos, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    retangulos = []
    for cnt in contornos:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area > CONFIG['area_min_componente']:
                cx, cy = x + w/2, y + h/2
                if not (canvas[0] <= cx <= canvas[2] and canvas[1] <= cy <= canvas[3]):
                    continue
                retangulos.append({
                    'x0': float(x), 'y0': float(y),
                    'x1': float(x+w), 'y1': float(y+h),
                    'width': float(w), 'height': float(h),
                    'area': float(area)
                })
    return to_native(retangulos)

def extrair_textos_ocr(imagem):
    textos = []
    
    # Tentar PaddleOCR singleton
    ocr = get_paddle_ocr()
    if ocr is not None:
        try:
            if len(imagem.shape) == 2:
                img_rgb = cv2.cvtColor(imagem, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB)
            
            resultado = ocr.ocr(img_rgb, cls=False)
            if resultado and resultado[0] is not None:
                for line in resultado[0]:
                    try:
                        box = line[0]
                        texto = line[1][0]
                        conf = line[1][1]
                        if conf < 0.3:
                            continue
                        xc = (box[0][0] + box[2][0]) / 2
                        yc = (box[0][1] + box[2][1]) / 2
                        altura = abs(box[2][1] - box[0][1])
                        if altura < CONFIG['tam_min_fonte']:
                            continue
                        textos.append({
                            'x': float(xc), 'y': float(yc),
                            'texto': str(texto),
                            'tam': float(altura),
                            'confianca': float(conf)
                        })
                    except Exception as e:
                        continue
            if textos:
                logger.info(f"PaddleOCR: {len(textos)} textos extraídos", extra={'modulo': 'M4'})
                return to_native(textos)
        except Exception as e:
            logger.warning(f"PaddleOCR falhou: {str(e)[:100]}", extra={'modulo': 'M4'})
    
    # Fallback Tesseract
    try:
        if len(imagem.shape) == 3:
            gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
        else:
            gray = imagem
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        for i in range(len(data['text'])):
            txt = data['text'][i].strip()
            if not txt or int(data['conf'][i]) < 30:
                continue
            x = float(data['left'][i] + data['width'][i] / 2)
            y = float(data['top'][i] + data['height'][i] / 2)
            textos.append({
                'x': x, 'y': y,
                'texto': txt,
                'tam': float(data['height'][i]),
                'confianca': int(data['conf'][i])
            })
        if textos:
            logger.info(f"Tesseract: {len(textos)} textos extraídos", extra={'modulo': 'M4'})
            return to_native(textos)
    except Exception as e:
        logger.debug(f"Tesseract falhou: {str(e)[:100]}", extra={'modulo': 'M4'})
    
    logger.warning("Nenhum OCR disponível - retornando lista vazia", extra={'modulo': 'M4'})
    return []

def extrair_emendas(binaria):
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    emendas = []
    for cnt in contornos:
        area = cv2.contourArea(cnt)
        if area < CONFIG['area_min_emenda'] or area > CONFIG['area_max_emenda']:
            continue
        perimetro = cv2.arcLength(cnt, True)
        if perimetro == 0:
            continue
        circularidade = 4 * np.pi * area / (perimetro * perimetro)
        if circularidade < CONFIG['circularidade_min']:
            continue
        M = cv2.moments(cnt)
        if M['m00'] != 0:
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            emendas.append((float(cx), float(cy)))
    return to_native(emendas)

def extrair_linhas_do_esqueleto(esqueleto):
    linhas = []
    if esqueleto is None:
        return linhas

    try:
        esqueleto = np.asarray(esqueleto, dtype=np.uint8)
        if esqueleto.ndim == 3:
            esqueleto = cv2.cvtColor(esqueleto, cv2.COLOR_BGR2GRAY)
        if esqueleto.size == 0:
            return linhas

        _, esqueleto = cv2.threshold(esqueleto, 127, 255, cv2.THRESH_BINARY)
        lines = cv2.HoughLinesP(esqueleto, 1, np.pi/180, threshold=20, minLineLength=5, maxLineGap=3)

        if lines is None:
            return linhas

        for line in lines:
            try:
                flat = np.asarray(line, dtype=np.float64).flatten()
                if len(flat) >= 4:
                    x1, y1, x2, y2 = float(flat[0]), float(flat[1]), float(flat[2]), float(flat[3])
                    linhas.append(((x1, y1), (x2, y2)))
            except:
                continue

    except Exception as e:
        logger.error(f"extrair_linhas_do_esqueleto falhou: {e}", extra={'modulo': 'M4'})
        return []

    return to_native(linhas)

@monitorar(modulo='M4')
def detectar_simbolos(imagem_binaria, imagem_original=None):
    if imagem_binaria is None:
        raise ErroExtracao("Imagem binária é None", severidade=Severidade.ALTA)

    h, w = imagem_binaria.shape[:2]
    canvas = (0, 0, w, h)

    logger.info(f">>> Iniciando detecção de símbolos na área {w}x{h}", extra={'modulo': 'M4'})
    
    t0 = time.perf_counter()
    retangulos = extrair_retangulos(imagem_binaria, canvas)
    t1 = time.perf_counter()
    logger.debug(f"[Métrica] extrair_retangulos levou {t1-t0:.2f}s", extra={'modulo': 'M4'})

    logger.info(">>> Iniciando OCR (processo pesado)...", extra={'modulo': 'M4'})
    textos = extrair_textos_ocr(imagem_original if imagem_original is not None else imagem_binaria)
    t2 = time.perf_counter()
    logger.info(f">>> [Métrica Crítica] extrair_textos_ocr levou {t2-t1:.2f}s ({len(textos)} textos)", extra={'modulo': 'M4'})

    curvas = extrair_emendas(imagem_binaria)
    t3 = time.perf_counter()
    logger.debug(f"[Métrica] extrair_emendas levou {t3-t2:.2f}s", extra={'modulo': 'M4'})

    logger.info(f"Símbolos detectados: {len(retangulos)} retângulos, {len(textos)} textos, {len(curvas)} emendas",
                extra={'modulo': 'M4'})

    resultado = {
        'linhas': [],
        'textos': textos,
        'retangulos': retangulos,
        'curvas': curvas,
        'conectores': detectar_conectores(retangulos, textos, []),
        'fios': [],
        'pontes': [],
        'barramentos': [],
        'canvas': canvas,
        'width': w,
        'height': h
    }
    return to_native(resultado)

@monitorar(modulo='M4')
def processar_imagem_restaurada(esqueleto, binaria, original=None):
    logger.info(">>> Iniciando Módulo 4: Processamento de Imagem Restaurada...", extra={'modulo': 'M4'})
    t_inicio = time.perf_counter()
    
    try:
        simbolos = detectar_simbolos(binaria, original)
        
        t_linhas_inicio = time.perf_counter()
        logger.info(">>> Iniciando extração de linhas (HoughLinesP)...", extra={'modulo': 'M4'})
        simbolos['linhas'] = extrair_linhas_do_esqueleto(esqueleto)
        simbolos['conectores'] = detectar_conectores(simbolos.get('retangulos', []), simbolos.get('textos', []), simbolos['linhas'])
        simbolos['fios'] = extrair_atributos_fios(simbolos['linhas'], simbolos.get('textos', []))
        simbolos['conectores'], simbolos['terminais'] = enriquecer_terminais(
            simbolos['conectores'], simbolos['linhas'], simbolos.get('textos', []),
            fios_attrs=simbolos.get('fios', [])
        )
        # Emendas detectadas por forma circular são evidências de junção.
        # Pontes gráficas são mantidas em campo separado e só entram quando
        # um detector futuro confirmar a presença da ponte. Nunca inferimos
        # ponte a partir de uma simples interseção.
        simbolos['emendas'] = list(simbolos.get('curvas', []))
        simbolos.setdefault('pontes', [])
        t_linhas_fim = time.perf_counter()
        logger.debug(f"[Métrica] extrair_linhas_do_esqueleto levou {t_linhas_fim - t_linhas_inicio:.2f}s", extra={'modulo': 'M4'})
        
        resultado_final = to_native(simbolos)
        
        t_total = time.perf_counter() - t_inicio
        logger.info(f">>> Módulo 4 concluído com sucesso em {t_total:.2f}s. "
                    f"Total de Linhas vetorizadas: {len(resultado_final.get('linhas', []))}", extra={'modulo': 'M4'})
        
        return resultado_final
        
    except Exception as e:
        logger.error(f"Erro fatal durante extração no Módulo 4: {e}\n{traceback.format_exc()}", extra={'modulo': 'M4'})
        raise ErroPipeline(
            mensagem="Falha durante a extração de OCR ou Símbolos",
            modulo='M4',
            severidade=Severidade.CRITICA,
            causa=e
        )

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python deteccao_simbolos.py <imagem_restaurada.png>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1], cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("Erro ao carregar imagem.")
        sys.exit(1)

    _, binaria = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    esqueleto = binaria

    resultado = processar_imagem_restaurada(esqueleto, binaria, original=cv2.imread(sys.argv[1]))
    print(f"Linhas: {len(resultado['linhas'])}")
    print(f"Textos: {len(resultado['textos'])}")
    print(f"Retângulos: {len(resultado['retangulos'])}")
    print(f"Emendas: {len(resultado['curvas'])}")

# ---------------------------------------------------------------------------
# Camada PRO: conectores, fios, cores e bitolas
# ---------------------------------------------------------------------------
RE_NUMERO_PIN = re.compile(r'^(?:PIN\s*)?(\d{1,4})$', re.I)
RE_BITOLA_PRO = re.compile(r'^(\d+(?:[.,]\d+)?)\s*MM(?:²|2)?$', re.I)
CORES_FIO = {'BLACK','BROWN','RED','ORANGE','YELLOW','GREEN','BLUE','VIOLET','PURPLE','GREY','GRAY','WHITE','PINK','BROWN/WHITE','BLUE/WHITE','GREEN/WHITE','RED/WHITE','BLACK/WHITE'}

def _dist(a,b):
    return float(np.hypot(float(a[0])-float(b[0]), float(a[1])-float(b[1])))

def _normalizar_numero_terminal(s):
    s = str(s).strip().upper().replace('PIN','').strip()
    s = re.sub(r'^[\[\(\{]+|[\]\)\}]+$', '', s)
    m = re.fullmatch(r'(\d{2,4})', s)
    return int(m.group(1)) if m else None

def _conectores_por_cluster_numerico(textos):
    """Fallback para conectores sem moldura fechada.
    Agrupa terminais numéricos em linhas/colunas próximas e exige pelo menos
    3 terminais de 2-4 dígitos. Não transforma números isolados em conectores.
    """
    pts=[]
    for t in textos:
        n=_normalizar_numero_terminal(t.get('texto',''))
        if n is None: continue
        conf=float(t.get('confianca',100) or 100)
        if conf < 30: continue
        pts.append({'numero':n,'x':float(t.get('x',0)),'y':float(t.get('y',0)),'confianca':conf})
    if len(pts)<3: return []
    grupos=[]
    for p in sorted(pts,key=lambda z:(z['y'],z['x'])):
        melhor=None; score=1e9
        for g in grupos:
            ys=[q['y'] for q in g]; xs=[q['x'] for q in g]
            dy=abs(p['y']-(sum(ys)/len(ys))); dx=abs(p['x']-(sum(xs)/len(xs)))
            if dy<=35 and dx<=900 and dy+0.15*dx<score:
                melhor=g; score=dy+0.15*dx
        if melhor is None: grupos.append([p])
        else: melhor.append(p)
    out=[]
    for i,g in enumerate(grupos,1):
        if len(g)<3: continue
        g=sorted(g,key=lambda z:z['x'])
        out.append({'id':f'CONOCR{i:03d}','tipo':'conector',
                    'terminais':[{k:v for k,v in p.items() if k in ('numero','x','y')} | {'evidencia':'OCR_cluster'} for p in g],
                    'cores_detectadas':[], 'bitolas_detectadas':[],
                    'evidencia':'cluster_de_terminais_numericos',
                    'confianca':round(sum(p['confianca'] for p in g)/len(g)/100,2)})
    return out

def detectar_conectores(retangulos, textos, linhas=None):
    """Identifica conectores por moldura OU por cluster de terminais.
    A segunda via é necessária em diagramas ECU onde o conector é desenhado
    apenas como conjunto de terminais/fios.
    """
    linhas=linhas or []
    conectores=[]
    for idx,r in enumerate(retangulos):
        pins=[]; cores=[]; bitolas=[]
        for t in textos:
            x,y=float(t.get('x',0)),float(t.get('y',0)); raw=str(t.get('texto','')).strip(); up=raw.upper()
            if r['x0']-25<=x<=r['x1']+25 and r['y0']-25<=y<=r['y1']+25:
                n=_normalizar_numero_terminal(raw)
                if n is not None: pins.append({'numero':n,'x':x,'y':y,'evidencia':'OCR'})
                if up in CORES_FIO: cores.append(up)
                if RE_BITOLA_PRO.fullmatch(up): bitolas.append(up.replace('MM',' mm').strip())
        if len(pins)>=2 or (len(pins)>=1 and (cores or bitolas)):
            conectores.append({'id':f'CON{idx+1:03d}','tipo':'conector','retangulo':r,
              'terminais':pins,'cores_detectadas':cores,'bitolas_detectadas':bitolas,
              'evidencia':'retangulo+deteccao_de_terminais','confianca':min(99,55+10*len(pins))})
    existentes={p['numero'] for c in conectores for p in c.get('terminais',[])}
    for c in _conectores_por_cluster_numerico(textos):
        novos=[p for p in c['terminais'] if p['numero'] not in existentes]
        if len(novos)>=3:
            c['terminais']=novos; conectores.append(c); existentes.update(p['numero'] for p in novos)
    return to_native(conectores)



def _texto_atributo_proximo(textos, pos, modo, distancia_max=55.0):
    """Encontra cor ou bitola próxima ao terminal.

    O retorno inclui distância e evidência; a informação nunca é tratada como
    universal: ela é sempre marcada como `fonte=documento`.
    """
    melhor = None
    melhor_d = float('inf')
    px, py = pos
    for t in textos:
        raw = str(t.get('texto', '')).strip()
        up = raw.upper()
        tx, ty = float(t.get('x', 0)), float(t.get('y', 0))
        d = _dist((px, py), (tx, ty))
        if d > distancia_max:
            continue
        if modo == 'cor' and up in CORES_FIO:
            if d < melhor_d:
                melhor = {'valor': up, 'distancia': d, 'texto': raw,
                          'evidencia': 'OCR_documento'}
                melhor_d = d
        elif modo == 'bitola':
            m = RE_BITOLA_PRO.fullmatch(up)
            if m and d < melhor_d:
                melhor = {'valor': m.group(1).replace(',', '.') + ' mm²',
                          'distancia': d, 'texto': raw,
                          'evidencia': 'OCR_documento'}
                melhor_d = d
    return melhor


def _segmentos_proximos(pos, linhas, distancia_max=35.0):
    """Retorna segmentos candidatos ao terminal, ordenados pela distância."""
    candidatos = []
    for idx, (a, b) in enumerate(linhas or []):
        d = _dist_point_segment_local(pos, a, b)
        if d <= distancia_max:
            candidatos.append((d, idx, a, b))
    candidatos.sort(key=lambda x: x[0])
    return candidatos


def _dist_point_segment_local(p, a, b):
    px, py = p
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    den = dx * dx + dy * dy
    if den <= 1e-12:
        return _dist(p, a)
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / den))
    q = (a[0] + t * dx, a[1] + t * dy)
    return _dist(p, q)


def enriquecer_terminais(conectores, linhas, textos, distancia_linha=35.0,
                         distancia_atributo=55.0, fios_attrs=None):
    """Transforma terminais simples em unidades M4 -> M5.

    Cada terminal passa a carregar:
      - conector_id
      - numero
      - coordenada
      - segmento_fio / segmentos_candidatos
      - cor_fio
      - bitola
      - evidencias
      - score_evidencia

    A cor/bitola só vem do documento analisado. Não consulta base de
    programadores nesta etapa.
    """
    enriquecidos = []
    fios_por_segmento = {
        int(f.get('segmento')): f for f in (fios_attrs or [])
        if isinstance(f, dict) and isinstance(f.get('segmento'), (int, float))
    }
    for con in conectores or []:
        cid = con.get('id', 'CON')
        novos = []
        for terminal in con.get('terminais', []) or []:
            try:
                numero = int(terminal.get('numero'))
                pos = (float(terminal.get('x')), float(terminal.get('y')))
            except (TypeError, ValueError):
                continue

            candidatos = _segmentos_proximos(pos, linhas, distancia_linha)
            cor = _texto_atributo_proximo(textos, pos, 'cor', distancia_atributo)
            bit = _texto_atributo_proximo(textos, pos, 'bitola', distancia_atributo)
            # Atributos podem estar escritos próximos ao fio, e não próximos
            # de cada terminal. Se a associação direta falhar, herdamos os
            # atributos já atribuídos ao segmento pelo M4.
            if candidatos:
                seg_attr = fios_por_segmento.get(candidatos[0][1], {})
                if not cor and seg_attr.get('cor'):
                    cor = {'valor': seg_attr.get('cor'), 'distancia': candidatos[0][0],
                           'texto': seg_attr.get('cor'), 'evidencia': 'atributo_segmento'}
                if not bit and seg_attr.get('bitola'):
                    bit = {'valor': seg_attr.get('bitola'), 'distancia': candidatos[0][0],
                           'texto': seg_attr.get('bitola'), 'evidencia': 'atributo_segmento'}

            evid = [{'tipo': 'terminal_ocr', 'valor': numero,
                     'fonte': 'documento', 'confianca': float(terminal.get('confianca', 70) or 70)}]
            if candidatos:
                evid.append({'tipo': 'segmento_geometrico', 'valor': candidatos[0][1],
                             'fonte': 'geometria',
                             'confianca': max(0.0, min(1.0, 1 - candidatos[0][0] / max(distancia_linha, 1)))})
            if cor:
                evid.append({'tipo': 'cor_fio', 'valor': cor['valor'],
                             'fonte': 'documento',
                             'distancia': round(cor['distancia'], 2)})
            if bit:
                evid.append({'tipo': 'bitola', 'valor': bit['valor'],
                             'fonte': 'documento',
                             'distancia': round(bit['distancia'], 2)})

            # Score conservador: identidade + vínculo geométrico + atributos.
            score = 0.45
            if candidatos:
                score += 0.35
            if cor:
                score += 0.10
            if bit:
                score += 0.10
            score = round(min(score, 0.99), 2)

            novo = {
                'numero': numero,
                'x': pos[0],
                'y': pos[1],
                'conector_id': cid,
                'segmento_fio': candidatos[0][1] if candidatos else None,
                'segmentos_candidatos': [
                    {'segmento': c[1], 'distancia': round(c[0], 2)}
                    for c in candidatos[:3]
                ],
                'cor_fio': cor['valor'] if cor else None,
                'bitola': bit['valor'] if bit else None,
                'fonte_cor': 'documento' if cor else None,
                'fonte_bitola': 'documento' if bit else None,
                'evidencias': evid,
                'score_evidencia': score,
                'status': 'vinculado_segmento' if candidatos else 'terminal_sem_fio'
            }
            novos.append(novo)
            enriquecidos.append({**novo})
        con['terminais'] = novos
        # Estrutura semântica do conector/barramento: vários terminais ligados
        # ao mesmo segmento são membros do mesmo barramento. Isso não cria
        # conexão por si só; apenas registra a estrutura para o M5.
        por_seg = {}
        for t in novos:
            sid = t.get('segmento_fio')
            if isinstance(sid, int):
                por_seg.setdefault(sid, []).append(t)
        barramentos = []
        for sid, membros in por_seg.items():
            if len(membros) >= 3:
                bid = f"BUS_{cid}_{sid}"
                numeros = sorted({m['numero'] for m in membros})
                for m in membros:
                    m['barramento_id'] = bid
                    m['evidencias'].append({
                        'tipo':'membro_barramento', 'valor':bid,
                        'fonte':'topologia_m4', 'confianca':0.90
                    })
                barramentos.append({
                    'id':bid, 'segmento_fio':sid, 'pinos':numeros,
                    'quantidade_terminais':len(numeros),
                    'origem':'M4_terminal_segmento'
                })
        con['barramentos'] = barramentos
        con['tipo_estrutura'] = 'conector_terminalizado'
    return to_native(conectores), to_native(enriquecidos)

def extrair_atributos_fios(linhas, textos, distancia=35):
    """Associa cor/bitola a segmentos somente quando o texto está próximo.
    Não usa a biblioteca de programadores; a fonte é o próprio documento.
    """
    out=[]
    for i,(a,b) in enumerate(linhas):
        melhor_cor=None; melhor_cor_d=1e9; melhor_bit=None; melhor_bit_d=1e9
        for t in textos:
            s=str(t.get('texto','')).strip().upper(); p=(float(t.get('x',0)),float(t.get('y',0)))
            d=_dist(p,a)+_dist(p,b)-_dist(a,b)
            d=max(0,d/2)
            if s in CORES_FIO and d<melhor_cor_d and d<=distancia:
                melhor_cor,melhor_cor_d=s,d
            m=RE_BITOLA_PRO.fullmatch(s)
            if m and d<melhor_bit_d and d<=distancia:
                melhor_bit,melhor_bit_d=m.group(1).replace(',','.')+' mm²',d
        if melhor_cor or melhor_bit:
            out.append({'segmento':i,'cor':melhor_cor,'bitola':melhor_bit,'fonte':'documento','confianca':round(max(0.5,1-min(melhor_cor_d if melhor_cor else melhor_bit_d,distancia)/distancia),2)})
    return to_native(out)
