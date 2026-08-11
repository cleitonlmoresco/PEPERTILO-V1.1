"""M11 - Parser semântico de manuais CarProg.

Não trata cor de fio como pino. Retorna entidades separadas: fios, MCUs,
máscaras, pinos e funções. A compatibilidade de programador é responsabilidade
da base de programadores, não deste parser.
"""
import re
import pymupdf
from logger_erros import logger

RE_FIO=re.compile(r'\b(BLUE|BROWN|GREY|GRAY|RED|VIOLET|WHITE|GREEN|ORANGE|YELLOW|BLACK|PURPLE|PINK)\s*[-–:]\s*([^\r\n;]+)',re.I)
RE_MCU=re.compile(r'\b(MC68HC912(?:B32|BC32|BD32|D60)(?:CF?U8|CF?U)?|MC68HC912B32CFU8)\b',re.I)
RE_MASK=re.compile(r'\b(4C11W|F68K|4F73K|0K75F|0K13J|L26M|9H91F|J15G|K29E|3K85K)\b',re.I)
RE_PIN=re.compile(r'\b(?:PIN|PINO)\s*(?:NO\.?\s*)?(\d{1,4})\s*[-–:]\s*([^\r\n;]+)',re.I)
RE_PIN2=re.compile(r'^\s*(\d{1,4})\s*[-–:]\s*(RESET|BKGD|GND|VSS|VDD|VCC|CANH|CANL|RXD|TXD|IRQ|XIRQ|BOOT|VREF)\s*$',re.I|re.M)


def extrair_carprog(caminho_pdf, limite_paginas=0):
    logger.info(f'[M11] Iniciando extração CarProg: {caminho_pdf}',extra={'modulo':'M11'})
    try: doc=pymupdf.open(caminho_pdf)
    except Exception as e:
        logger.error(f'[M11] Erro ao abrir PDF: {e}',extra={'modulo':'M11'}); return {}
    total=min(len(doc),limite_paginas) if limite_paginas>0 else len(doc)
    paginas=[]
    try:
        for i in range(total): paginas.append(doc[i].get_text('text') or '')
    finally: doc.close()
    texto='\n'.join(paginas)
    out={'status':'ok' if texto.strip() else 'incompleto','fios':[],'mcus':[],'mascaras':[],
         'pinos':[],'funcoes':{},'num_paginas':total,'modulo':'M11'}
    if not texto.strip(): return out

    for m in RE_FIO.finditer(texto):
        out['fios'].append({'cor':m.group(1).upper(),'funcao':m.group(2).strip(),'fonte':'M11'})
    modelos=[]
    for m in RE_MCU.finditer(texto):
        modelo=m.group(1).upper()
        if modelo not in modelos: modelos.append(modelo)
    masks=[]
    for m in RE_MASK.finditer(texto):
        mask=m.group(1).upper()
        if mask not in masks: masks.append(mask)
    out['mascaras']=masks
    out['mcus']=[{'modelo':m,'mascara':None,'fonte':'M11'} for m in modelos]
    if modelos and masks:
        # associação é marcada como provável, não confirmada, pois o documento
        # pode conter vários modelos/máscaras.
        for m in out['mcus']:
            m['mascara_candidata']=masks[0]

    for m in RE_PIN.finditer(texto):
        p=int(m.group(1)); fn=m.group(2).strip()
        out['pinos'].append({'pino':p,'funcao':fn,'fonte':'M11'})
        out['funcoes'][str(p)]=fn
    for m in RE_PIN2.finditer(texto):
        p=int(m.group(1)); fn=m.group(2).upper()
        out['pinos'].append({'pino':p,'funcao':fn,'fonte':'M11'})
        out['funcoes'][str(p)]=fn

    # Deduplica por pino/função e preserva múltiplas ocorrências como evidência.
    seen=set(); uniq=[]
    for p in out['pinos']:
        k=(p['pino'],p['funcao'].upper())
        if k not in seen: seen.add(k); uniq.append(p)
    out['pinos']=uniq
    logger.info(f"[M11] fios={len(out['fios'])}, mcus={len(out['mcus'])}, máscaras={len(out['mascaras'])}, pinos={len(out['pinos'])}",extra={'modulo':'M11'})
    return out
