from grafo_rastreador import processar_diagrama
from topologia import reconstruir_topologia
from deteccao_simbolos import enriquecer_terminais

PASS=FAIL=0

def test(name, fn):
    global PASS,FAIL
    try:
        r=fn(); PASS+=1; print(f'[PASS] {name}: {r}')
    except Exception as e:
        FAIL+=1; print(f'[FAIL] {name}: {type(e).__name__}: {e}')

def t_bridge():
    lines=[((0,5),(10,5)),((5,0),(5,10))]
    r=reconstruir_topologia(lines,pontes=[(5,5)])
    assert r['num_pontes']==1
    assert r['num_juncoes']==0
    assert r['num_cruzamentos_sem_conexao']==0
    assert len(r['arestas'])==2
    return {'pontes':r['num_pontes'],'arestas':len(r['arestas'])}

def t_cross_no_bridge():
    r=reconstruir_topologia([((0,5),(10,5)),((5,0),(5,10))])
    assert r['num_juncoes']==0 and r['num_cruzamentos_sem_conexao']==1
    return r['intersecoes']

def t_bus_contract():
    # M4 mantém os terminais; o barramento é consolidado pelo M5 pela rede,
    # portanto não exige que todos os terminais estejam no mesmo segmento bruto.
    lines=[((0,0),(100,0)),((20,0),(20,20)),((50,0),(50,20)),((80,0),(80,20))]
    con=[{'id':'CON1','terminais':[{'numero':1,'x':20,'y':20},{'numero':2,'x':50,'y':20},{'numero':3,'x':80,'y':20}]}]
    con,terms=enriquecer_terminais(con,lines,[],fios_attrs=[{'segmento':0,'cor':'BROWN','bitola':'0.50 mm²'}])
    assert all(t.get('segmento_fio') in (1,2,3) for t in terms), terms
    return {'terminais':len(terms),'segmentos':[t['segmento_fio'] for t in terms]}

def t_multipage_continuity():
    # Página 1: NET:GND liga pino 34 ao rótulo.
    # Página 2: mesmo NET:GND liga pino 46 ao rótulo. O resultado precisa
    # carregar a continuidade entre páginas.
    p1={
        'linhas': [((0,0),(100,0))],
        'textos': [
            {'texto':'34','x':0,'y':0,'confianca':99},
            {'texto':'NET:GND','x':90,'y':0,'confianca':99},
        ],
        'retangulos':[],'emendas':[],'pontes':[],'conectores':[
            {'id':'CON1','terminais':[{'numero':34,'x':0,'y':0}]}
        ],'fios':[{'segmento':0,'cor':'BROWN','bitola':'0.50 mm²'}]
    }
    p2={
        'linhas': [((0,0),(100,0))],
        'textos': [
            {'texto':'46','x':0,'y':0,'confianca':99},
            {'texto':'NET:GND','x':90,'y':0,'confianca':99},
        ],
        'retangulos':[],'emendas':[],'pontes':[],'conectores':[
            {'id':'CON2','terminais':[{'numero':46,'x':0,'y':0}]}
        ],'fios':[{'segmento':0,'cor':'BROWN','bitola':'0.50 mm²'}]
    }
    conns,GG,pins,meta=__import__('grafo_rastreador').processar_diagrama_multipagina({1:p1,2:p2})
    assert meta['continuidade_paginas'], meta
    assert any(x.get('status')=='continuidade_entre_paginas' for x in conns), conns
    assert any(e.get('label_rede')=='GND' for _,_,e in GG.edges(data=True) if e.get('relacao')=='continuidade_entre_paginas')
    return {'continuidade':meta['continuidade_paginas'],'edges':GG.number_of_edges()}

def t_no_false_connection_single_terminal():
    data={'linhas':[ ((0,0),(100,0)) ],'textos':[{'texto':'34','x':0,'y':0}],
          'retangulos':[],'emendas':[],'pontes':[],'conectores':[{'id':'CON1','terminais':[{'numero':34,'x':0,'y':0}]}],
          'fios':[{'segmento':0,'cor':'BROWN','bitola':'0.50 mm²'}]}
    conns,_,_,_=processar_diagrama(data)
    assert not any(c.get('pinos')==[34] for c in conns), conns
    return {'conexoes':len(conns)}

def t_bus_graph():
    lines=[((0,0),(100,0)),((20,0),(20,20)),((50,0),(50,20)),((80,0),(80,20))]
    data={'linhas':lines,'textos':[
        {'texto':'1','x':20,'y':20},{'texto':'2','x':50,'y':20},{'texto':'3','x':80,'y':20}],
        'retangulos':[],'emendas':[],'pontes':[],
        'conectores':[{'id':'CON1','terminais':[{'numero':1,'x':20,'y':20},{'numero':2,'x':50,'y':20},{'numero':3,'x':80,'y':20}]}],
        'fios':[{'segmento':0,'cor':'RED','bitola':'0.50 mm²'}]}
    conns,_,_,meta=processar_diagrama(data)
    assert any(c.get('tipo')=='barramento' and c.get('pinos')==[1,2,3] for c in conns), conns
    return {'barramentos':meta['barramentos']}

for n,f in [
 ('ponte gráfica',t_bridge),('cruzamento sem ponte',t_cross_no_bridge),
 ('contrato M4 de barramento',t_bus_contract),('continuidade entre páginas',t_multipage_continuity),
 ('não criar conexão com terminal isolado',t_no_false_connection_single_terminal),
 ('barramento no M5',t_bus_graph)]: test(n,f)
print(f'RESULTADO V6: PASS={PASS} FAIL={FAIL}')
raise SystemExit(1 if FAIL else 0)
