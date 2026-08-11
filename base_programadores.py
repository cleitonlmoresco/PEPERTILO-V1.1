"""Registro inicial de programadores preservando a base existente.

IMPORTANTE: os registros abaixo indicam que a ferramenta existe no projeto;
não representam, por si só, compatibilidade confirmada com um part-number.
"""
from copy import deepcopy

BASE_PROGRAMADORES = {
    "CarProg_A10": {
        "nome": "CarProg A10",
        "interfaces": ["BDM", "OBD", "Bench"],
        "familias": ["HC12", "9S12"],
        "status": "cadastrado",
        "cabos": [],
    },
    "UPA_USB": {
        "nome": "UPA-USB",
        "interfaces": ["BDM", "ISP", "Bench"],
        "familias": ["HC12", "9S12"],
        "status": "cadastrado",
        "cabos": [],
    },
    "ST10_Flasher": {
        "nome": "ST10 Flasher",
        "interfaces": ["Bench", "BDM"],
        "familias": ["ST10"],
        "status": "cadastrado",
        "cabos": [],
    },
    "EEPROM_I2C": {
        "nome": "Programador EEPROM I2C",
        "interfaces": ["I2C"],
        "familias": ["EEPROM"],
        "status": "cadastrado",
        "cabos": [],
    },
    "EEPROM_SPI": {
        "nome": "Programador EEPROM SPI",
        "interfaces": ["SPI"],
        "familias": ["EEPROM"],
        "status": "cadastrado",
        "cabos": [],
    },
}


def listar_programadores():
    return deepcopy(BASE_PROGRAMADORES)


def buscar_programadores_por_familia(familia: str):
    familia = (familia or "").upper()
    out = []
    for pid, item in BASE_PROGRAMADORES.items():
        if any(familia == f.upper() or familia in f.upper() for f in item.get("familias", [])):
            out.append({"id": pid, **deepcopy(item)})
    return out

# Dados documentais adicionais. A cor pertence ao cabo A10 do CarProg, não ao chicote da ECU.
BASE_PROGRAMADORES['CarProg_A10']['cabos'] = [{
    'id':'CARPROG_A10_HC12', 'nome':'A10 HC12/9S12', 'interface':'BDM',
    'status':'documentado',
    'sinais': {
        'RESET':'BLUE','GND':'BROWN','BKGD':'GREY','+5V':'RED','+12V':'VIOLET'
    },
    'fonte':'CarProg Motorola HC912/9S12 Programmer Manual'
}]


def buscar_programadores_por_mcu(part_number=None, familia=None):
    pn=(part_number or '').upper(); fam=(familia or '').upper()
    out=[]
    for pid,item in BASE_PROGRAMADORES.items():
        if fam and any(fam in f.upper() or f.upper() in fam for f in item.get('familias',[])):
            rec=deepcopy(item); rec['id']=pid
            # Só marcamos compatibilidade documental quando existe cabo/documentação explícita.
            rec['compatibilidade']='familia_cadastrada'
            if pid=='CarProg_A10' and ('HC12' in fam or '9S12' in fam):
                rec['compatibilidade']='documentado_para_familia'
            out.append(rec)
    return out
