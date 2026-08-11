"""Base documental inicial para memórias seriais usadas em bancada."""
from copy import deepcopy

MEMORIAS={
 'M95160': {
  'fabricante':'STMicroelectronics','familia':'SPI EEPROM','capacidade':'16 Kbit (2048 x 8)','interface':'SPI',
  'packages':['SO8','TSSOP8','UFDFPN8','WLCSP'],
  'pin_map': {1:'S/CS',2:'Q/DO',3:'W/WP',4:'VSS',5:'D/DI',6:'C/CLK',7:'HOLD',8:'VCC'},
  'fonte':'STMicroelectronics M95160 datasheet',
  'observacao':'A função exata dos pinos deve ser conferida na variante/package do componente.'
 }
}

def buscar_memoria(part_number):
    s=(part_number or '').upper()
    for k,v in MEMORIAS.items():
        if k in s:return {'part_number':k,**deepcopy(v)}
    return None
