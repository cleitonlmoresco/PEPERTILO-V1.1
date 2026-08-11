"""PEPERTILO PRO - DEBUG/REGRESSION SUITE
Executa testes sem depender da interface Flask.
"""
from pathlib import Path
import json, traceback

BASE = Path('/mnt/data/PEPERTILO_SIMULACAO_INTERNET')
SIM = Path('/mnt/data/PEPERTILO_SIMULACAO')

PASS = 0; FAIL = 0; WARN = 0
REPORT=[]

def test(name, fn):
    global PASS, FAIL
    try:
        value = fn()
        PASS += 1
        REPORT.append({'teste':name,'status':'PASS','detalhes':value})
        print(f'[PASS] {name}: {value}')
    except AssertionError as e:
        FAIL += 1; REPORT.append({'teste':name,'status':'FAIL','detalhes':str(e)})
        print(f'[FAIL] {name}: {e}')
    except Exception as e:
        FAIL += 1; REPORT.append({'teste':name,'status':'ERROR','detalhes':f'{type(e).__name__}: {e}'})
        print(f'[ERROR] {name}: {type(e).__name__}: {e}')


def main():
    from classificador import classificar_arquivo
    from extracao_vetorial import extrair_primitivas_vetorial
    from roteador import rotear_arquivo
    from extracao_datasheet import extrair_datasheet
    from extracao_carprog import extrair_carprog
    from topologia import reconstruir_topologia
    from grafo_rastreador import processar_diagrama
    from deteccao_simbolos import detectar_conectores, enriquecer_terminais, extrair_atributos_fios
    from modo_mpu import processar_modo_mpu
    import cv2
    from restauracao_img import restaurar_imagem
    from deteccao_simbolos import processar_imagem_restaurada

    test('M1 classifica PDF vetorial', lambda: classificar_arquivo(str(BASE/'03_teste_vetorial_local.pdf')) == 'pdf_vetorial')
    test('M2 extrai página vetorial', lambda: len(extrair_primitivas_vetorial(str(BASE/'03_teste_vetorial_local.pdf'))) == 1)

    def t_topology():
        r=reconstruir_topologia([((0,0),(10,0)),((5,0),(5,10))],snap_tol=2,cruzamento_tol=1.5)
        assert r['num_juncoes']==1 and r['num_cruzamentos_sem_conexao']==0 and len(r['arestas'])==3, r
        return r
    test('M5 junção T', t_topology)

    def t_cross():
        r=reconstruir_topologia([((0,5),(10,5)),((5,0),(5,10))],snap_tol=2,cruzamento_tol=1.5)
        assert r['num_juncoes']==0 and r['num_cruzamentos_sem_conexao']==1 and len(r['arestas'])==2, r
        return r
    test('M5 cruzamento sem conexão', t_cross)

    def t_dot():
        r=reconstruir_topologia([((0,5),(10,5)),((5,0),(5,10))],emendas=[(5,5)],snap_tol=2,cruzamento_tol=1.5)
        assert r['num_juncoes']==1 and len(r['arestas'])==4, r
        return r
    test('M5 cruzamento com junção', t_dot)

    def t_connector():
        img=cv2.imread(str(BASE/'01_ECU_Delphi_MT20U.webp')); e,b=restaurar_imagem(img); d=processar_imagem_restaurada(e,b,original=img)
        nums=[p['numero'] for c in d['conectores'] for p in c.get('terminais',[])]
        assert len(d['conectores'])>=1 and len(nums)>=3, {'conectores':d['conectores']}
        return {'conectores':len(d['conectores']),'terminais':nums}
    test('M4 conector sem moldura', t_connector)

    def t_terminal_segment_network():
        linhas=[((0,0),(100,0)),((100,0),(200,0))]
        textos=[
            {'x':10,'y':0,'texto':'34','confianca':95},
            {'x':90,'y':0,'texto':'46','confianca':95},
            {'x':20,'y':12,'texto':'BROWN','confianca':95},
            {'x':35,'y':14,'texto':'0.50 MM2','confianca':95},
            {'x':200,'y':0,'texto':'SENSOR','confianca':95},
        ]
        fios=[{'segmento':0,'cor':'BROWN','bitola':'0.50 mm²','fonte':'documento','confianca':.9}]
        con=[{'id':'CON1','tipo':'conector','terminais':[{'numero':34,'x':10,'y':0},{'numero':46,'x':90,'y':0}]}]
        con,terms=enriquecer_terminais(con,linhas,textos,fios_attrs=fios)
        assert all(t['segmento_fio']==0 for t in terms), terms
        assert all(t['cor_fio']=='BROWN' and t['bitola']=='0.50 mm²' for t in terms), terms
        dados={'linhas':linhas,'textos':textos,'retangulos':[],'curvas':[],'emendas':[], 'fios':fios,'conectores':con}
        conex,*_=processar_diagrama(dados)
        assert any(c.get('pinos')==[34,46] and c.get('cor_fio')=='BROWN' and c.get('bitola')=='0.50 mm²' for c in conex), conex
        return {'pinos':[34,46],'rede':'segmento_0','cor':'BROWN','bitola':'0.50 mm²'}
    test('M4→M5 terminal→segmento→rede', t_terminal_segment_network)

    def t_real_connector_contract():
        img=cv2.imread(str(BASE/'01_ECU_Delphi_MT20U.webp')); e,b=restaurar_imagem(img); d=processar_imagem_restaurada(e,b,original=img)
        terms=d.get('terminais',[])
        assert len(terms)>=3, {'terminais':terms,'conectores':d.get('conectores')}
        assert all('conector_id' in t and 'segmento_fio' in t for t in terms), terms[:5]
        return {'terminais':len(terms),'com_segmento':sum(t.get('segmento_fio') is not None for t in terms),'conectores':len(d.get('conectores',[]))}
    test('M4 real: contrato terminal/fio', t_real_connector_contract)

    def t_mpu():
        img=cv2.imread(str(BASE/'02_MC68HC912BC32_pinout.png')); e,b=restaurar_imagem(img); d=processar_imagem_restaurada(e,b,original=img); r=processar_modo_mpu(d)
        assert r['identificacao']['part_number']=='MC68HC912BC32'
        assert r['identificacao']['encapsulamento']=='80-pin QFP'
        assert r['num_pinos']==80
        assert r['identificacao']['status_pinmap']=='documental'
        return {'part':r['identificacao']['part_number'],'orientacao':r['orientacao'],'pinos':r['num_pinos']}
    test('MPU PRO pin map documental', t_mpu)

    def t_m6_limit():
        p=str(SIM/'05_teste_integrado_4_paginas.pdf')
        one=extrair_datasheet(p,1); two=extrair_datasheet(p,2)
        assert len(one)==0 and len(two)>=len(one), {'one':len(one),'two':len(two)}
        return {'limite1':len(one),'limite2':len(two)}
    test('M6 respeita limite_paginas', t_m6_limit)

    def t_m11():
        r=extrair_carprog(str(BASE/'05_manual_carprog_local.pdf'),0)
        assert r['status']=='ok' and len(r['fios'])>=4 and len(r['mcus'])>=1
        return {'fios':len(r['fios']),'mcus':len(r['mcus']),'mascaras':len(r['mascaras'])}
    test('M11 separa fios/MCU/máscaras', t_m11)

    def t_route():
        r=rotear_arquivo(str(BASE/'03_teste_vetorial_local.pdf'))
        assert r['resultado']['status'] in ('ok','erro') and 'tipo' in r
        return {'tipo':r['tipo'],'status':r['resultado']['status'],'modulo':r['resultado'].get('modulo')}
    test('Roteador contrato de saída', t_route)

    print(f'\nRESULTADO: PASS={PASS} FAIL={FAIL}')
    out={'pass':PASS,'fail':FAIL,'tests':REPORT}
    Path('DEBUG_REGRESSION_REPORT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    return 1 if FAIL else 0

if __name__=='__main__':
    raise SystemExit(main())
