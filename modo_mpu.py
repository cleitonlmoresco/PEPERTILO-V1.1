"""Modo MPU PRO: identificação documental de MCU e mapeamento de pinagem.

A posição geométrica nunca é usada para inventar um número de pino. Primeiro
identificamos part-number/package/maskset; só depois projetamos o pin-map
oficial para as coordenadas do desenho, quando a orientação puder ser inferida.
"""
from __future__ import annotations
import re
from logger_erros import logger, monitorar, ErroExtracao, Severidade, ColetorErros
from utils import to_native
from base_mcu import identificar_mcu, extrair_masksets, coordenadas_pinagem, MCUS
from base_programadores import buscar_programadores_por_mcu

CONFIG_MPU={'margem_borda':30,'confianca_minima':50}

@monitorar(modulo='MPU')
def identificar_documentacao_mcu(dados_pagina):
    textos=dados_pagina.get('textos',[]) if dados_pagina else []
    part, spec=identificar_mcu(textos)
    masks=extrair_masksets(textos)
    if not part:
        return {'identificado':False,'part_number':None,'masksets':masks,'evidencias':[]}
    return {
      'identificado': True,
      'part_number': part,
      'fabricante': spec.get('fabricante'),
      'familia': spec.get('familia'),
      'encapsulamento': spec.get('encapsulamento'),
      'pinos': spec.get('pinos'),
      'interfaces': spec.get('interfaces',[]),
      'masksets': masks,
      'pin_map': {str(k):v for k,v in spec.get('pin_map',{}).items()},
      'fontes': spec.get('fontes',[]),
      'status_pinmap': 'documental' if spec.get('pin_map') else 'sem_pinmap_confirmado'
    }

def detectar_chip_rect(dados_pagina):
    rects=dados_pagina.get('retangulos',[]) if dados_pagina else []
    if not rects: return None
    # Prefere retângulo que contenha part-number ou tenha alta densidade de textos no perímetro.
    textos=dados_pagina.get('textos',[])
    candidatos=[]
    for r in rects:
        n=0
        for t in textos:
            x,y=float(t.get('x',0)),float(t.get('y',0))
            perto=(r['x0']-CONFIG_MPU['margem_borda']<=x<=r['x1']+CONFIG_MPU['margem_borda'] and
                   r['y0']-CONFIG_MPU['margem_borda']<=y<=r['y1']+CONFIG_MPU['margem_borda'])
            if perto: n+=1
        candidatos.append((n,r))
    return max(candidatos,key=lambda x:x[0])[1]

def _inferir_orientacao(textos, chip_rect):
    # Só declara orientação se houver evidência de PIN 1/marking; caso contrário permanece desconhecida.
    for t in textos:
        s=str(t.get('texto','')).strip().upper().replace(' ','')
        if s in {'1','PIN1','PIN.1'}:
            x,y=float(t.get('x',0)),float(t.get('y',0))
            if chip_rect and x < (chip_rect['x0']+chip_rect['x1'])/2 and y < (chip_rect['y0']+chip_rect['y1'])/2:
                return 'PIN1_SUPERIOR_ESQUERDO'
    return 'DESCONHECIDA'

@monitorar(modulo='MPU')
def processar_modo_mpu(dados_pagina, ferramenta='CarProg_A10'):
    if not dados_pagina:
        return {'modo':'erro','mensagem':'dados_pagina vazio','pinos':[],'num_pinos':0}
    doc=identificar_documentacao_mcu(dados_pagina)
    chip=detectar_chip_rect(dados_pagina)
    if not doc.get('identificado'):
        return {'modo':'normal','mensagem':'MCU não identificada documentalmente','pinos':[],'num_pinos':0,'identificacao':doc}
    orient=_inferir_orientacao(dados_pagina.get('textos',[]),chip)
    coords=coordenadas_pinagem(chip,doc.get('pinos')) if orient!='DESCONHECIDA' else {}
    pinos=[]
    for num,funcao in doc.get('pin_map',{}).items():
        c=coords.get(int(num)) if coords else None
        pinos.append({'pino':int(num),'funcao':funcao,'coordenada':({'x':c[0],'y':c[1],'lado':c[2]} if c else None),
                      'origem':'pin_map_documental','confianca':100})
    ferramentas=buscar_programadores_por_mcu(doc.get('part_number'),doc.get('familia'))
    return to_native({
      'modo':'mpu','mensagem':'MCU identificada por documentação; pinagem não foi estimada por geometria',
      'identificacao':doc,'chip':chip,'orientacao':orient,'pinos':pinos,'num_pinos':len(pinos),
      'ferramenta':ferramenta,'programadores':ferramentas,
      'regra':'part_number → encapsulamento → pin 1/orientação → pin map → coordenadas'
    })
