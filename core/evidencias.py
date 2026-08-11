from __future__ import annotations
from collections import defaultdict
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Tuple
from .modelos import Evidencia, Conexao

FUNC_ALIASES = {
    "VSS": "GND", "VSSX": "GND", "VSSR": "GND", "VSSPLL": "GND",
    "VSS1": "GND", "VSS2": "GND", "GROUND": "GND", "TERRA": "GND",
    "VCC": "VDD", "+5V": "VDD", "VDDX": "VDD", "VDDR": "VDD",
    "VDDPLL": "VDD", "RESET": "RESET", "RST": "RESET",
    "CANH": "CAN_H", "CANL": "CAN_L", "CAN-H": "CAN_H", "CAN-L": "CAN_L",
}

COLORS = {
    "BLACK", "PRETO", "BROWN", "MARROM", "RED", "VERMELHO", "BLUE", "AZUL",
    "WHITE", "BRANCO", "GREEN", "VERDE", "YELLOW", "AMARELO", "ORANGE",
    "LARANJA", "GRAY", "GREY", "CINZA", "PURPLE", "ROXO", "VIOLET", "VIOLETA"
}

STOPWORDS_PIN = {"PIN", "PINO", "NUMBER", "NO", "N", "SIGNAL", "FUNCTION", "DESCRIPTION", "NAME"}


def canon_funcao(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return None
    s = str(valor).strip().upper().replace(" ", "_")
    return FUNC_ALIASES.get(s, s)


def parece_cor(valor: Optional[str]) -> bool:
    return bool(valor) and str(valor).strip().upper() in COLORS


def validar_pino(valor) -> bool:
    if valor is None:
        return False
    s = str(valor).strip().upper()
    if not s or s in STOPWORDS_PIN or parece_cor(s):
        return False
    # Números puros e padrões comuns; não aceitar texto livre.
    if s.isdigit():
        return 0 < int(s) <= 2000
    if len(s) <= 8 and any(ch.isdigit() for ch in s) and all(ch.isalnum() or ch in "_-" for ch in s):
        return True
    return False


def normalizar_m11(resultado: Dict) -> Dict:
    """Converte o retorno legado do M11 em semântica explícita."""
    fios, mcus, mascaras, funcoes, pinos = [], [], [], {}, []
    if not isinstance(resultado, dict):
        return {"fios": [], "mcus": [], "mascaras": [], "funcoes": {}, "pinos": []}

    for item in resultado.get("fios", []) or []:
        if isinstance(item, dict):
            fios.append(item)
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            fios.append({"cor": item[0], "funcao": item[1], "origem": "M11"})

    for item in resultado.get("mcus", []) or []:
        if isinstance(item, dict):
            mcus.append(item)
        else:
            mcus.append({"modelo": str(item)})

    mascaras = list(resultado.get("mascaras", []) or [])
    funcoes_in = resultado.get("funcoes", {}) or {}
    if isinstance(funcoes_in, dict):
        for chave, valor in funcoes_in.items():
            if validar_pino(chave):
                funcoes[str(chave)] = valor
            elif str(chave).upper() in FUNC_ALIASES:
                funcoes[str(chave)] = valor

    # Não transforma cor em pino.
    for chave, valor in funcoes.items():
        if validar_pino(chave) and not parece_cor(chave):
            pinos.append({"pino": chave, "funcao": canon_funcao(valor) or value_as_funcao(valor)})

    return {"fios": fios, "mcus": mcus, "mascaras": mascaras, "funcoes": funcoes, "pinos": pinos}


def value_as_funcao(value):
    return canon_funcao(value) or str(value).strip()


def agrupar_conexoes(conexoes: Iterable[Conexao]) -> List[Conexao]:
    grupos = {}
    for c in conexoes:
        func = canon_funcao(c.funcao) or "DESCONHECIDA"
        cor = (c.cor_fio or "").upper() or None
        tipo = c.tipo or "desconhecido"
        key = (func, cor, tipo)
        if key not in grupos:
            grupos[key] = Conexao(funcao=func, cor_fio=cor, tipo=tipo, status=c.status)
        g = grupos[key]
        g.pinos.extend(c.pinos)
        g.pagina_origem.extend(c.pagina_origem)
        g.evidencias.extend(c.evidencias)
        g.observacoes.extend(c.observacoes)
        g.score_evidencia = max(g.score_evidencia, c.score_evidencia)
    for g in grupos.values():
        g.pinos = sorted({str(p) if not isinstance(p, int) else p for p in g.pinos}, key=str)
        g.pagina_origem = sorted(set(g.pagina_origem))
        g.evidencias = sorted(set(g.evidencias))
        g.observacoes = sorted(set(g.observacoes))
    return list(grupos.values())
