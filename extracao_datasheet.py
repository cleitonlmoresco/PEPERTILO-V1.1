"""M6 - Extração robusta de tabelas de datasheets.

Mantém compatibilidade com a API antiga (dict {pino: função}) e oferece
uma saída detalhada com linhas/colunas/evidências quando detalhado=True.
"""
from __future__ import annotations

import re
import os
import tempfile
import unicodedata
from collections import defaultdict

import pdfplumber

from logger_erros import logger, monitorar, ErroOCR, ErroPipeline, Severidade, tratar_erro_controlado, ColetorErros

SINONIMOS_PINO = ['pin', 'terminal', 'pino', 'pin no', 'pin number', 'nº', 'no.', 'terminal no', 'connector pin', 'terminal number']
SINONIMOS_SINAL = ['signal', 'sinal', 'name', 'nome', 'designation', 'net', 'rede']
SINONIMOS_FUNCAO = ['função', 'funcao', 'function', 'descrição', 'descricao', 'description', 'function/name', 'purpose']
SINONIMOS_TIPO = ['type', 'tipo', 'i/o', 'io', 'direction', 'direção', 'direcao']

MAPA_SIGLAS = {
    'VDD': 'Alimentação positiva', 'VCC': 'Alimentação', 'VSS': 'Terra', 'GND': 'Terra',
    'CAN_H': 'Comunicação CAN High', 'CAN_L': 'Comunicação CAN Low', 'CAN H': 'Comunicação CAN High',
    'CAN L': 'Comunicação CAN Low', 'K-LINE': 'Diagnóstico K-Line', 'K LINE': 'Diagnóstico K-Line',
    'IGN': 'Ignição (15)', 'BAT': 'Bateria (30)', 'BAT+': 'Bateria (30)', 'KL15': 'Ignição (15)',
    'KL30': 'Bateria (30)', 'KL31': 'Terra (31)', 'MISO': 'Comunicação SPI (MISO)',
    'MOSI': 'Comunicação SPI (MOSI)', 'SCLK': 'Comunicação SPI (Clock)', 'SCK': 'Comunicação SPI (Clock)',
    'CS': 'Chip Select (SPI)', 'SDA': 'Comunicação I2C (Dados)', 'SCL': 'Comunicação I2C (Clock)',
    'TX': 'Transmissão Serial', 'RX': 'Recepção Serial', 'RST': 'Reset', 'RESET': 'Reset',
    'BOOT': 'Bootloader', 'VPP': 'Tensão de programação', 'VREF': 'Tensão de referência'
}

RE_PINO = re.compile(r'^(?:\d{1,4}|[A-Z]{1,4}\d{1,4}|[A-Z]{1,5}[-_]?\d{1,4}|\d{1,4}[A-Z]?)$')
RE_PINO_LIMPO = re.compile(r'[^A-Z0-9_-]')
RE_BITOLA = re.compile(r'(?i)\b(?:0[.,]\d+|\d+(?:[.,]\d+)?)\s*(?:mm2|mm²|mm\^2|awg\s*\d+|mil)\b')


def normalizar_cabecalho(s):
    s = '' if s is None else str(s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', s.lower().strip())


def limpar_pino(v):
    s = RE_PINO_LIMPO.sub('', str(v or '').strip().upper())
    return s


def pino_valido(v):
    s = limpar_pino(v)
    return bool(s and RE_PINO.match(s))


def expandir_siglas(texto):
    if not texto:
        return ''
    out = str(texto)
    for sigla, traducao in sorted(MAPA_SIGLAS.items(), key=lambda x: len(x[0]), reverse=True):
        out = re.sub(r'(?<![A-Z0-9_])' + re.escape(sigla) + r'(?![A-Z0-9_])', traducao, out, flags=re.I)
    return out


def _cabecalho_indices(header):
    norm = [normalizar_cabecalho(x) for x in header]
    def find(syns):
        for i, h in enumerate(norm):
            if any(h == s or s in h for s in syns):
                return i
        return None
    return find(SINONIMOS_PINO), find(SINONIMOS_SINAL), find(SINONIMOS_FUNCAO), find(SINONIMOS_TIPO)


def _score_header(row):
    if not row:
        return -1
    idx = _cabecalho_indices(row)
    score = 0
    if idx[0] is not None: score += 4
    if idx[1] is not None: score += 2
    if idx[2] is not None: score += 4
    if idx[3] is not None: score += 1
    return score


def _clean_cell(v):
    if v is None: return ''
    return re.sub(r'\s+', ' ', str(v).replace('\n', ' ').strip())


def _merge_continuations(rows, idx_pin, idx_func, idx_signal=None):
    """Une linhas quebradas: linha sem pino herda o último pino."""
    merged = []
    current = None
    for row in rows:
        row = [_clean_cell(x) for x in row]
        pin = row[idx_pin] if idx_pin is not None and idx_pin < len(row) else ''
        has_pin = pino_valido(pin)
        if has_pin:
            if current: merged.append(current)
            current = row
            continue
        if current is None:
            continue
        # continuação: agrega campos textuais, sem duplicar
        for i, val in enumerate(row):
            if not val: continue
            if i >= len(current): current.extend([''] * (i + 1 - len(current)))
            if i == idx_pin: continue
            if val not in current[i]:
                current[i] = (current[i] + ' ' + val).strip()
    if current: merged.append(current)
    return merged


def _rows_to_records(rows, page_no, bbox=None, source='pdfplumber', inherited_header=None):
    if not rows and not inherited_header: return [], None
    # Procura o melhor cabeçalho entre as primeiras 8 linhas; se a página
    # continuar uma tabela, reutiliza o cabeçalho anterior.
    best_i, best_score = None, -1
    for i, r in enumerate(rows[:8]):
        s = _score_header(r)
        if s > best_score:
            best_i, best_score = i, s
    if best_i is None or best_score < 6:
        if inherited_header:
            header = list(inherited_header)
            best_i, best_score = -1, 6
        else:
            return [], None
    else:
        header = [_clean_cell(x) for x in rows[best_i]]
    idx_pin, idx_signal, idx_func, idx_type = _cabecalho_indices(header)
    data_rows = rows[best_i + 1:] if best_i >= 0 else rows
    data = _merge_continuations(data_rows, idx_pin, idx_func, idx_signal)
    records = []
    for row in data:
        if idx_pin is None or idx_pin >= len(row): continue
        pin = limpar_pino(row[idx_pin])
        if not pino_valido(pin): continue
        signal = _clean_cell(row[idx_signal]) if idx_signal is not None and idx_signal < len(row) else ''
        func = _clean_cell(row[idx_func]) if idx_func is not None and idx_func < len(row) else signal
        tipo = _clean_cell(row[idx_type]) if idx_type is not None and idx_type < len(row) else ''
        desc = ''
        # Se houver descrição em coluna distinta, preserva no registro.
        desc_idx = next((i for i,h in enumerate(header) if normalizar_cabecalho(h) in ('descricao','description')), None)
        if desc_idx is not None and desc_idx < len(row): desc = _clean_cell(row[desc_idx])
        if not func and desc: func = desc
        records.append({
            'pino': pin, 'sinal': signal, 'funcao': func, 'tipo': tipo, 'descricao': desc,
            'pagina': page_no, 'origem': source, 'cabecalho': header,
            'confianca': round((0.96 if source == 'pdfplumber' else 0.78) + (0.02 if best_score >= 10 else 0.0), 2), 'bbox': bbox,
        })
    return records, {'header': header, 'score': best_score, 'indices': {'pino': idx_pin, 'sinal': idx_signal, 'funcao': idx_func, 'tipo': idx_type}}


def _extract_tables_variants(page):
    variants = [
        {},
        {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
        {'vertical_strategy': 'text', 'horizontal_strategy': 'text', 'snap_tolerance': 4, 'join_tolerance': 4, 'intersection_tolerance': 6},
        {'vertical_strategy': 'text', 'horizontal_strategy': 'lines', 'snap_tolerance': 4, 'join_tolerance': 4},
    ]
    seen = set()
    for settings in variants:
        try:
            tables = page.extract_tables(table_settings=settings)
        except Exception:
            continue
        for t in tables or []:
            key = repr(t[:3]) + str(len(t))
            if key not in seen:
                seen.add(key); yield t


def _extract_positional(page, page_no, inherited_header=None):
    """Reconstrói tabela sem linhas usando posições X/Y dos words."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
    if not words: return []
    # agrupa por linha usando altura do texto, não pixels fixos
    rows = []
    for w in sorted(words, key=lambda z: (z['top'], z['x0'])):
        h = max(1.0, w['bottom'] - w['top'])
        tol = max(2.5, h * 0.65)
        placed = None
        for row in reversed(rows[-3:]):
            if abs(row['y'] - w['top']) <= tol:
                placed = row; break
        if placed is None:
            placed = {'y': w['top'], 'words': []}; rows.append(placed)
        placed['words'].append(w)
    text_rows = [[w['text'] for w in sorted(r['words'], key=lambda z:z['x0'])] for r in rows]
    # Somente transforma se encontrar cabeçalho forte.
    out, _ = _rows_to_records(text_rows, page_no, source='posicional', inherited_header=inherited_header)
    return out


def _extrair_com_pdfplumber_detalhado(caminho_pdf, limite_paginas=0):
    records, tables_info = [], []
    with pdfplumber.open(caminho_pdf) as pdf:
        inherited_header = None
        for i, page in enumerate(pdf.pages):
            if limite_paginas > 0 and i >= limite_paginas: break
            page_records = []
            for tabela in _extract_tables_variants(page):
                recs, info = _rows_to_records(tabela, i + 1, source='pdfplumber', inherited_header=inherited_header)
                if recs:
                    page_records.extend(recs)
                    inherited_header = info['header']
                    tables_info.append({'pagina': i + 1, 'linhas': len(tabela), 'colunas': max(map(len, tabela)), 'cabecalho': info['header'], 'score': info['score'], 'continua': False})
            # remove duplicatas do mesmo pino, priorizando a tabela com maior confiança
            if not page_records:
                page_records = _extract_positional(page, i + 1, inherited_header=inherited_header)
            records.extend(page_records)
    return _dedupe_records(records), tables_info


def _dedupe_records(records):
    best = {}
    for r in records:
        key = (r.get('pagina'), r.get('pino'))
        old = best.get(key)
        if old is None or (r.get('confianca', 0), len(r.get('descricao',''))) > (old.get('confianca', 0), len(old.get('descricao',''))):
            best[key] = r
    return list(best.values())


def _extrair_com_ocr(caminho_pdf, limite_paginas=0):
    """OCR estruturado: Paddle quando disponível; fallback Tesseract posicional."""
    try:
        import pymupdf as fitz
        doc = fitz.open(caminho_pdf)
    except Exception as e:
        raise ErroOCR(f'Não foi possível abrir PDF: {e}', causa=e)
    try:
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='en')
            backend = 'paddleocr'
        except Exception:
            ocr = None; backend = 'tesseract'
        records = []
        for i, page in enumerate(doc):
            if limite_paginas > 0 and i >= limite_paginas: break
            pix = page.get_pixmap(dpi=300, alpha=False)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                path = tmp.name; pix.save(path)
            try:
                if ocr is not None:
                    result = ocr.ocr(path, cls=True)
                    words = []
                    for block in result or []:
                        for line in block or []:
                            if len(line) < 2: continue
                            box, data = line[0], line[1]
                            words.append({'text': data[0], 'x0': min(p[0] for p in box), 'top': min(p[1] for p in box), 'bottom': max(p[1] for p in box)})
                    # agrupa OCR em linhas e usa o mesmo reconstruidor
                    rows=[]
                    for w in sorted(words,key=lambda z:(z['top'],z['x0'])):
                        row=next((r for r in reversed(rows[-3:]) if abs(r['y']-w['top'])<=max(6,(w['bottom']-w['top'])*.7)),None)
                        if row is None: row={'y':w['top'],'words':[]}; rows.append(row)
                        row['words'].append(w)
                    text_rows=[[w['text'] for w in sorted(r['words'],key=lambda z:z['x0'])] for r in rows]
                    recs,_=_rows_to_records(text_rows,i+1,source=backend)
                    records.extend(recs)
                else:
                    import pytesseract
                    from PIL import Image
                    data=pytesseract.image_to_data(Image.open(path),config='--psm 6',output_type=pytesseract.Output.DICT)
                    words=[]
                    for j,t in enumerate(data['text']):
                        if not t.strip(): continue
                        words.append({'text':t,'x0':data['left'][j],'top':data['top'][j],'bottom':data['top'][j]+data['height'][j]})
                    rows=[]
                    for w in sorted(words,key=lambda z:(z['top'],z['x0'])):
                        row=next((r for r in reversed(rows[-3:]) if abs(r['y']-w['top'])<=max(8,(w['bottom']-w['top'])*.8)),None)
                        if row is None: row={'y':w['top'],'words':[]}; rows.append(row)
                        row['words'].append(w)
                    text_rows=[[w['text'] for w in sorted(r['words'],key=lambda z:z['x0'])] for r in rows]
                    recs,_=_rows_to_records(text_rows,i+1,source='tesseract')
                    records.extend(recs)
            finally:
                try: os.remove(path)
                except OSError: pass
        return _dedupe_records(records)
    finally:
        doc.close()


def extrair_datasheet_detalhado(caminho_pdf, limite_paginas=0):
    if not caminho_pdf: raise ErroPipeline('Caminho do datasheet não informado', modulo='M6', severidade=Severidade.ALTA)
    warnings=[]
    records=[]; tables=[]
    try:
        records,tables=_extrair_com_pdfplumber_detalhado(caminho_pdf,limite_paginas)
    except Exception as e:
        warnings.append(f'PDF/table extraction: {e}')
    if not records:
        try: records=_extrair_com_ocr(caminho_pdf,limite_paginas)
        except Exception as e: warnings.append(f'OCR: {e}')
    # Normalização sem perder o texto original.
    for r in records:
        r['funcao_expandida']=expandir_siglas(r.get('sinal') or r.get('funcao') or r.get('descricao'))
        r['bitolas']=RE_BITOLA.findall(' '.join(str(r.get(k,'')) for k in ('sinal','funcao','descricao')))
    return {
        'tipo': 'datasheet_tabela',
        'registros': records,
        'tabelas': tables,
        'paginas_processadas': sorted(set(r['pagina'] for r in records)),
        'total_registros': len(records),
        'avisos': warnings,
        'backend': records[0]['origem'] if records else None,
    }


@monitorar(modulo='M6')
def extrair_datasheet(caminho_pdf, limite_paginas=0, detalhado=False):
    resultado = extrair_datasheet_detalhado(caminho_pdf, limite_paginas)
    if detalhado:
        return resultado
    pin_func={}
    for r in resultado['registros']:
        pin=r['pino']; func=r.get('funcao') or r.get('sinal') or r.get('descricao')
        if pin and func:
            # preserva compatibilidade antiga: última ocorrência da mesma página não apaga função melhor.
            pin_func[pin]=expandir_siglas(func)
    logger.info(f"Datasheet processado: {len(pin_func)} funções extraídas; {resultado['total_registros']} registros estruturados", extra={'modulo':'M6'})
    return pin_func


if __name__ == '__main__':
    import sys, json
    if len(sys.argv)<2:
        print('Uso: python extracao_datasheet.py <datasheet.pdf> [--detalhado]'); raise SystemExit(1)
    detalhado='--detalhado' in sys.argv
    print(json.dumps(extrair_datasheet(sys.argv[1],detalhado=detalhado),ensure_ascii=False,indent=2))
