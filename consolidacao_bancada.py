"""Camada de consolidação para uso de bancada do PEPERTILO.

Não altera evidências brutas de M5/M6/MPU. Produz uma ficha operacional
consolidada, com rastreabilidade e estado de validação.

Regra de segurança:
- compatibilidade de programador só é "documentada" quando a base contém
  evidência explícita;
- ausência de documentação nunca vira "compatível";
- conflitos M5/M6 permanecem bloqueados para operação automática.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List

from base_programadores import buscar_programadores_por_mcu


def _norm(s):
    return str(s or "").strip().upper().replace("_", "-").replace(" ", "")


def _pin_map(mpu):
    ident = (mpu or {}).get("identificacao") or {}
    return {str(k): v for k, v in (ident.get("pin_map") or {}).items()}


def _programadores(mpu):
    ident = (mpu or {}).get("identificacao") or {}
    return buscar_programadores_por_mcu(
        ident.get("part_number"), ident.get("familia")
    )


def _programmer_cable(rec):
    """Expõe somente cabos documentados no cadastro."""
    out = []
    for cabo in rec.get("cabos", []) or []:
        if cabo.get("status") != "documentado":
            continue
        out.append({
            "id": cabo.get("id"),
            "nome": cabo.get("nome"),
            "interface": cabo.get("interface"),
            "status": "documentado",
            "sinais": deepcopy(cabo.get("sinais", {})),
            "fonte": cabo.get("fonte"),
        })
    return out


def consolidar_bancada(resultado_integracao=None, resultado_mpu=None,
                        resultado_m5=None, resultado_m6=None) -> Dict[str, Any]:
    """Gera ficha única para bancada, sem perder as fontes originais."""
    integ = resultado_integracao or {}
    mpu = resultado_mpu or {}
    ident = mpu.get("identificacao") or {}
    mapa = integ.get("mapa_pinos") or []

    # Indexa o pin-map documental do MCU para completar funções que o M5/M6
    # não conseguiram extrair.
    pmap = _pin_map(mpu)
    by_pin = {}
    for item in mapa:
        p = str(item.get("pino"))
        by_pin[p] = deepcopy(item)

    for p, func in pmap.items():
        if p not in by_pin:
            by_pin[p] = {
                "pino": int(p) if p.isdigit() else p,
                "funcao": func,
                "funcao_mpu": func,
                "status": "somente_MPU",
                "origem_mpu": "pin_map_documental",
            }
        else:
            by_pin[p]["funcao_mpu"] = func

    pinos = [by_pin[k] for k in sorted(by_pin, key=lambda x: int(x) if x.isdigit() else x)]

    # Programadores: nunca converte cadastro de família em compatibilidade
    # específica de part-number.
    programas = []
    for rec in _programadores(mpu):
        item = {
            "id": rec.get("id"),
            "nome": rec.get("nome"),
            "interfaces": rec.get("interfaces", []),
            "familias": rec.get("familias", []),
            "compatibilidade": rec.get("compatibilidade", "nao_confirmada"),
            "status": rec.get("status"),
            "cabos_documentados": _programmer_cable(rec),
        }
        programas.append(item)

    bloqueios = []
    if integ.get("status") == "conflito_requer_revisao":
        bloqueios.append("CONFLITO_M5_M6")
    if ident and ident.get("status_pinmap") != "documental":
        bloqueios.append("PINMAP_NAO_CONFIRMADO")

    return {
        "tipo": "ficha_bancada",
        "status_operacional": "revisao_obrigatoria" if bloqueios else "pronto_para_analise",
        "bloqueios": bloqueios,
        "componente": {
            "part_number": ident.get("part_number"),
            "fabricante": ident.get("fabricante"),
            "familia": ident.get("familia"),
            "encapsulamento": ident.get("encapsulamento"),
            "masksets": ident.get("masksets", []),
            "pinos": ident.get("pinos"),
            "orientacao": mpu.get("orientacao"),
        },
        "pinagem": pinos,
        "programadores": programas,
        "resumo_correlacao": deepcopy(integ.get("resumo", {})),
        "fontes": {
            "M5": deepcopy(resultado_m5) if resultado_m5 is not None else None,
            "M6": deepcopy(resultado_m6) if resultado_m6 is not None else None,
            "MPU": deepcopy(resultado_mpu) if resultado_mpu is not None else None,
            "M5_M6": deepcopy(resultado_integracao) if resultado_integracao is not None else None,
        },
    }


def validar_operacao_programador(ficha, programador_id):
    """Retorna se a ficha possui base documental suficiente para indicar o cabo.

    Não gera pinagem elétrica nem recomenda tensão/corrente sem documentação.
    """
    for p in ficha.get("programadores", []):
        if p.get("id") == programador_id:
            cabos = p.get("cabos_documentados", [])
            return {
                "programador": p,
                "habilitado": bool(cabos) and not ficha.get("bloqueios"),
                "motivo": (
                    "cabo documentado e sem conflitos"
                    if cabos and not ficha.get("bloqueios")
                    else "requer documentação/revisão antes da operação"
                ),
            }
    return {
        "programador": None,
        "habilitado": False,
        "motivo": "programador não cadastrado para o componente",
    }
