"""Integração M5 (topologia) + M6 (pinagem documental).

M5 é a fonte primária para conectividade. M6 é a fonte documental para
função/sinal/descrição de pinos. O módulo apenas correlaciona evidências;
nunca inventa uma conexão para resolver um conflito.
"""
from __future__ import annotations
from collections import defaultdict
import re

# Famílias de sinônimos usadas apenas para detectar equivalência/conflito.
_CANON = {
    'GND': {'GND','VSS','VSSA','VSSX','GROUND','TERRA','0V','KL31'},
    'VDD': {'VDD','VCC','VBAT','5V','+5V','SUPPLY','POWER'},
    'RESET': {'RESET','RST','RES'},
    'BKGD': {'BKGD','BACKGROUND DEBUG','BACKGROUND'},
    'CANH': {'CANH','CAN-H','CAN_H','CAN HIGH'},
    'CANL': {'CANL','CAN-L','CAN_L','CAN LOW'},
    'RX': {'RX','RXD','RECEIVER'},
    'TX': {'TX','TXD','TRANSMITTER'},
}


def _norm_text(value):
    s = str(value or '').upper().strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('_','-')
    return s


def canonical_function(value):
    s = _norm_text(value)
    if not s:
        return None
    for canon, vals in _CANON.items():
        if s in vals:
            return canon
    return s


def _numeric_pin(value):
    s = str(value or '').strip().upper()
    m = re.fullmatch(r'(\d{1,4})', s)
    return int(m.group(1)) if m else None


def _iter_m5_pins(resultado_m5):
    """Expõe cada terminal/pino de M5 de forma uniforme."""
    pins = []
    for conn in resultado_m5.get('conexoes', []) or []:
        tipo = conn.get('tipo') if isinstance(conn, dict) else None
        for p in (conn.get('pinos', []) if isinstance(conn, dict) else []):
            pn = _numeric_pin(p)
            if pn is None:
                continue
            pins.append({
                'pino': pn,
                'tipo_rede': tipo,
                'funcao_m5': conn.get('funcao') if isinstance(conn, dict) else None,
                'cor_fio': conn.get('cor_fio', conn.get('cor')) if isinstance(conn, dict) else None,
                'bitola': conn.get('bitola') if isinstance(conn, dict) else None,
                'paginas': list(conn.get('pagina_origem', []) or []) if isinstance(conn, dict) else [],
                'evidencias_m5': list(conn.get('evidencias', []) or []) if isinstance(conn, dict) else [],
                'status_m5': conn.get('status') if isinstance(conn, dict) else None,
            })

    # Conectores carregam evidência mais fina do terminal e não dependem de a
    # conexão final ter sido consolidada em uma rede com >=2 pontos.
    for con in resultado_m5.get('conectores', []) or []:
        for t in con.get('terminais', []) or []:
            pn = _numeric_pin(t.get('numero', t.get('pino')))
            if pn is None:
                continue
            pins.append({
                'pino': pn,
                'tipo_rede': 'terminal',
                'funcao_m5': t.get('funcao'),
                'cor_fio': t.get('cor_fio'),
                'bitola': t.get('bitola'),
                'paginas': [con.get('pagina')] if con.get('pagina') else [],
                'evidencias_m5': list(t.get('evidencias', []) or []),
                'status_m5': t.get('status'),
            })

    # Consolida observações duplicadas do mesmo pino.
    grouped = defaultdict(list)
    for p in pins:
        grouped[p['pino']].append(p)
    out = []
    for pino, items in sorted(grouped.items()):
        funcs = [i.get('funcao_m5') for i in items if i.get('funcao_m5')]
        colors = [i.get('cor_fio') for i in items if i.get('cor_fio')]
        bits = [i.get('bitola') for i in items if i.get('bitola')]
        pages = sorted({x for i in items for x in i.get('paginas', []) if x is not None})
        out.append({
            'pino': pino,
            'funcao_m5': funcs[0] if funcs else None,
            'funcoes_m5': sorted(set(map(str, funcs))) if funcs else [],
            'cor_fio': sorted(set(map(str, colors))) if colors else [],
            'bitola': sorted(set(map(str, bits))) if bits else [],
            'paginas_m5': pages,
            'evidencias_m5': sorted({e for i in items for e in i.get('evidencias_m5', [])}),
            'status_m5': sorted({str(i.get('status_m5')) for i in items if i.get('status_m5')}),
        })
    return out


def _m6_by_pin(resultado_m6):
    out = defaultdict(list)
    registros = resultado_m6.get('registros', []) if isinstance(resultado_m6, dict) else []
    # Também aceita o formato antigo {"34":"RESET"}.
    if not registros and isinstance(resultado_m6, dict):
        for pino, func in resultado_m6.get('funcoes', resultado_m6).items():
            pn = _numeric_pin(pino)
            if pn is not None:
                out[pn].append({'pino': pn, 'sinal': '', 'funcao': str(func), 'descricao': '', 'pagina': None, 'origem': 'M6_legacy', 'confianca': 0.70})
        return out
    for r in registros:
        pn = _numeric_pin(r.get('pino'))
        if pn is None:
            continue
        out[pn].append(r)
    return out


def correlacionar_m5_m6(resultado_m5, resultado_m6):
    """Correlaciona topologia e documentação por número de pino.

    Retorna concordâncias, conflitos, pinos sem documentação e um mapa final
    por pino. Conflitos permanecem explícitos; o módulo não escolhe uma fonte
    contra a outra automaticamente.
    """
    m5 = _iter_m5_pins(resultado_m5 or {})
    m6 = _m6_by_pin(resultado_m6 or {})
    m5_by = {p['pino']: p for p in m5}

    mapa = []
    concordancias = []
    conflitos = []
    sem_m6 = []
    sem_m5 = []

    for pino, p5 in sorted(m5_by.items()):
        docs = m6.get(pino, [])
        func_m5 = canonical_function(p5.get('funcao_m5'))
        if not docs:
            mapa.append({
                'pino': pino,
                'funcao': p5.get('funcao_m5'),
                'cor_fio': p5.get('cor_fio', []),
                'bitola': p5.get('bitola', []),
                'fonte': 'M5',
                'status': 'sem_correspondencia_M6',
                'paginas_m5': p5.get('paginas_m5', []),
                'evidencias': p5.get('evidencias_m5', []),
            })
            sem_m6.append(pino)
            continue

        # Melhor registro documental = maior confiança, depois maior riqueza textual.
        doc = sorted(docs, key=lambda r: (float(r.get('confianca', 0) or 0), len(str(r.get('descricao', '')))), reverse=True)[0]
        func_m6_raw = doc.get('funcao') or doc.get('sinal') or doc.get('descricao')
        func_m6 = canonical_function(func_m6_raw)

        item = {
            'pino': pino,
            'funcao_m5': p5.get('funcao_m5'),
            'funcao_m6': func_m6_raw,
            'funcao_normalizada_m5': func_m5,
            'funcao_normalizada_m6': func_m6,
            'sinal_m6': doc.get('sinal'),
            'descricao_m6': doc.get('descricao'),
            'cor_fio': p5.get('cor_fio', []),
            'bitola': p5.get('bitola', []),
            'pagina_m5': p5.get('paginas_m5', []),
            'pagina_m6': doc.get('pagina'),
            'confianca_m6': doc.get('confianca', 0),
            'evidencias_m5': p5.get('evidencias_m5', []),
            'origem_m6': doc.get('origem'),
        }

        if func_m5 and func_m6:
            if func_m5 == func_m6:
                item['status'] = 'concordante'
                item['funcao'] = func_m6_raw or p5.get('funcao_m5')
                concordancias.append(item)
            else:
                item['status'] = 'CONFLITO'
                item['funcao'] = None
                conflitos.append(item)
        else:
            item['status'] = 'documental_complementar'
            item['funcao'] = func_m6_raw or p5.get('funcao_m5')
            concordancias.append(item)
        mapa.append(item)

    for pino in sorted(set(m6.keys()) - set(m5_by.keys())):
        docs = m6[pino]
        doc = sorted(docs, key=lambda r: float(r.get('confianca', 0) or 0), reverse=True)[0]
        sem_m5.append(pino)
        mapa.append({
            'pino': pino,
            'funcao': doc.get('funcao') or doc.get('sinal') or doc.get('descricao'),
            'sinal_m6': doc.get('sinal'),
            'descricao_m6': doc.get('descricao'),
            'pagina_m6': doc.get('pagina'),
            'origem_m6': doc.get('origem'),
            'confianca_m6': doc.get('confianca', 0),
            'status': 'somente_M6',
        })

    return {
        'tipo': 'integracao_m5_m6',
        'status': 'conflito_requer_revisao' if conflitos else 'validado_sem_conflitos',
        'mapa_pinos': mapa,
        'concordancias': concordancias,
        'conflitos': conflitos,
        'pinos_somente_m5': sem_m6,
        'pinos_somente_m6': sem_m5,
        'resumo': {
            'pinos_m5': len(m5_by),
            'pinos_m6': len(m6),
            'concordancias': len(concordancias),
            'conflitos': len(conflitos),
            'somente_m5': len(sem_m6),
            'somente_m6': len(sem_m5),
        }
    }
