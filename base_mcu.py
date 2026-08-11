"""Base documental de MCUs para o Modo MPU PRO.

Os registros representam pinagem documental conhecida; não são inferências de imagem.
"""
from copy import deepcopy

# MC68HC912B32 80-pin QFP. Pin assignments consolidados do datasheet Motorola.
# Sequência por número de pino, conforme figura do datasheet.
B32_80QFP = {
  1:'PP5',2:'PP4',3:'PW3/PP3',4:'PW2/PP2',5:'PW1/PP1',6:'PW0/PP0',7:'IOC0/PT0',8:'IOC1/PT1',9:'IOC2/PT2',10:'VDD',11:'VSS',12:'IOC3/PT3',13:'IOC4/PT4',14:'IOC5/PT5',15:'IOC6/PT6',16:'PAI/IOC7/PT7',17:'SMODN/TAGHI/BKGD',18:'ADDR3/DATA3/PB3',19:'ADDR4/DATA4/PB4',20:'ADDR5/DATA5/PB5',21:'ADDR6/DATA6/PB6',22:'ADDR7/DATA7/PB7',23:'ADDR5/DATA5/PB5',24:'ADDR6/DATA6/PB6',25:'ADDR7/DATA7/PB7',26:'DBE/PE7',27:'MODB/IPIPE1/PE6',28:'MODA/IPIPE0/PE5',29:'ECLK/PE4',30:'VSSX',31:'VDDX',32:'RESET',33:'EXTAL',34:'XTAL',35:'LSTRB/TAGLO/PE3',36:'R/W/PE2',37:'IRQ/VPP/PE1',38:'XIRQ/PE0',39:'PA0/ADDR8/DATA8',40:'PA1/ADDR9/DATA9',41:'PA2/ADDR10/DATA10',42:'PA3/ADDR11/DATA11',43:'PA4/ADDR12/DATA12',44:'PA5/ADDR13/DATA13',45:'PA6/ADDR14/DATA14',46:'PA7/ADDR15/DATA15',47:'VDD',48:'VSS',49:'VRH',50:'VRL',51:'PAD0/AN0',52:'PAD1/AN1',53:'PAD2/AN2',54:'PAD3/AN3',55:'PAD4/AN4',56:'PAD5/AN5',57:'PAD6/AN6',58:'PAD7/AN7',59:'VDDA',60:'VSSA',61:'PS0/RxD',62:'PS1/TxD',63:'PS2',64:'PS3',65:'PS4/SDI/MISO',66:'PS5/SDO/MOSI',67:'PS6/SCK',68:'PS7/CS/SS',69:'VFP',70:'PDLC0/DLCRx',71:'PDLC1/DLCTx',72:'PDLC2',73:'PDLC3',74:'PDLC4',75:'PDLC5',76:'PDLC6',77:'VSSX',78:'VDDX',79:'PP7',80:'PP6'
}


MCUS={
 'MC68HC912B32': {
   'fabricante':'Motorola', 'familia':'HC12', 'encapsulamento':'80-pin QFP', 'pinos':80,
   'interfaces':['BDM'], 'pin_map':B32_80QFP,
   'fontes':['Motorola MC68HC912B32TS/D datasheet']
 },
 'MC68HC912BC32': {
   'fabricante':'Motorola', 'familia':'HC12', 'encapsulamento':'80-pin QFP', 'pinos':80,
   'interfaces':['BDM'], 'pin_map':B32_80QFP,
   'fontes':['Motorola MC68HC912B32TS/D datasheet / família B32']
 }
}

def identificar_mcu(textos):
    blob=' '.join(str(t.get('texto','')) for t in textos).upper()
    for pn in sorted(MCUS,key=len,reverse=True):
        if pn.upper() in blob:
            return pn, deepcopy(MCUS[pn])
    # marcações comuns customizadas; devolve somente candidato, não pin map.
    for t in textos:
        s=str(t.get('texto','')).upper().replace(' ','')
        if s.startswith('N750') or 'EPIC' in s:
            return s, {'fabricante':'Motorola/Freescale','familia':'HC12 (candidato)','encapsulamento':None,'pinos':None,'interfaces':['BDM (provável)'],'pin_map':{},'fontes':['evidência do documento']}
    return None, None

def extrair_masksets(textos):
    blob=' '.join(str(t.get('texto','')) for t in textos).upper()
    pats=['9H91F','4J54E','J64Y','J15G','K25E','K29E','F68K','4F73K','0K75F','0K13J','L26M']
    return [p for p in pats if p in blob]

def coordenadas_pinagem(chip_rect, pinos=80):
    """Posições nominais do package QFP: 20 pinos por lado, CCW a partir do canto superior esquerdo.
    São coordenadas de referência, não substituem a orientação real detectada no desenho.
    """
    if not chip_rect or pinos not in (80,): return {}
    x0,y0,x1,y1=[float(chip_rect[k]) for k in ('x0','y0','x1','y1')]
    out={}; nside=20
    for i in range(nside):
        f=(i+0.5)/nside
        out[i+1]=(x0+(x1-x0)*f,y0,'TOPO')
        out[21+i]=(x1,y0+(y1-y0)*f,'DIREITA')
        out[41+i]=(x1-(x1-x0)*f,y1,'BASE')
        out[61+i]=(x0,y1-(y1-y0)*f,'ESQUERDA')
    return out
