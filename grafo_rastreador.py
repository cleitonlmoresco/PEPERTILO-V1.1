"""M5 PRO - reconstrução topológica de diagramas elétricos.

Regras principais:
- junção T conecta automaticamente;
- cruzamento interior/interior não conecta sem marca de junção;
- ponte pode ser representada por curva/emenda e permanece separada quando não há conexão;
- endpoints são snapados;
- conectores são objetos de primeira classe;
- cor e bitola vêm do documento e acompanham a aresta;
- continuidades entre páginas usam etiquetas de referência quando disponíveis.
"""
from __future__ import annotations
import math, re
from collections import deque
import networkx as nx
from logger_erros import logger, monitorar, ErroGrafo, Severidade, ColetorErros
from topologia import reconstruir_topologia

CONFIG={'dist_max_pino_segmento':45.0,'dist_max_periferico_segmento':35.0,'dist_texto':18.0,'dist_emenda':5.0}
RE_PIN=re.compile(r'^[\[\(\{]?\s*(?:PIN\s*)?(\d{1,4})\s*[\]\)\}]?$',re.I)
RE_CONT=re.compile(r'(?:P[ÁA]G(?:INA)?|FOLHA|SHEET|PAGE|P[.]?)\s*([0-9]+)',re.I)
RE_NET_LABEL=re.compile(r'^(?:NET|REDE|SINAL|CONT|CONTINUIDADE)\s*[:=]\s*([A-Z0-9_./-]{2,40})$', re.I)

def _dist_point_seg(px,py,a,b):
    dx=b[0]-a[0]; dy=b[1]-a[1]
    if dx==0 and dy==0:return math.hypot(px-a[0],py-a[1])
    t=max(0,min(1,((px-a[0])*dx+(py-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(a[0]+t*dx),py-(a[1]+t*dy))

def identificar_ecu(retangulos,canvas):
    if not retangulos:return None,[]
    cx,cy=(canvas[2]-canvas[0])/2,(canvas[3]-canvas[1])/2
    cand=[r for r in retangulos if not (r['x0']<=canvas[0]+2 or r['y0']<=canvas[1]+2 or r['x1']>=canvas[2]-2 or r['y1']>=canvas[3]-2)] or retangulos
    cand=sorted(cand,key=lambda r:r.get('area',0),reverse=True)
    return cand[0],cand[1:]

def _pinos_textuais(textos):
    out=[]
    for t in textos:
        s=str(t.get('texto','')).strip().upper(); m=RE_PIN.fullmatch(s)
        if m: out.append({'numero':int(m.group(1)),'x':float(t.get('x',0)),'y':float(t.get('y',0)),'evidencia':'OCR'})
    return out

def extrair_pinos_ecu(textos, ecu, conectores=None, linhas=None):
    pins=[]
    if conectores:
        for con in conectores:
            for p in con.get('terminais',[]):
                pins.append({'numero':p['numero'],'x':p['x'],'y':p['y'],'conector':con['id'],'evidencia':'conector'})
    pins.extend(_pinos_textuais(textos))
    # dedup espacial
    out=[]; seen=set()
    for p in pins:
        key=(p['numero'],round(p['x']/3),round(p['y']/3))
        if key not in seen: seen.add(key); out.append(p)
    return out

def _attach_nearest(G,label,pos,segments,distmax,tipo='pino',meta=None):
    best=None; bestd=1e99
    for a,b,attrs in segments:
        d=_dist_point_seg(pos[0],pos[1],a,b)
        if d<bestd:best=(a,b,attrs);bestd=d
    if not best or bestd>distmax:return None
    a,b,attrs=best
    dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy or 1
    t=max(0,min(1,((pos[0]-a[0])*dx+(pos[1]-a[1])*dy)/den)); snap=(round(a[0]+t*dx,3),round(a[1]+t*dy,3))
    G.add_node(snap,pos=snap,tipo='nó')
    G.add_node(label,pos=pos,tipo=tipo,**(meta or {}));G.add_edge(label,snap,relacao='conectado')
    return snap

def _build_graph(dados):
    linhas=dados.get('linhas',[]) or []
    topo=reconstruir_topologia(linhas,dados.get('emendas',[]),dados.get('pontes',[]),snap_tol=5.0,cruzamento_tol=3.0)
    G=nx.Graph(); segs=[]
    attrs_by_idx={x.get('segmento'):x for x in dados.get('fios',[]) if isinstance(x,dict)}
    for edge in topo['arestas']:
        a,b=edge['a'],edge['b']; attrs=dict(attrs_by_idx.get(edge.get('segmento_origem'),{}))
        G.add_node(a,pos=a,tipo='nó');G.add_node(b,pos=b,tipo='nó');G.add_edge(a,b,**attrs)
        segs.append((a,b,attrs))
    return G,segs,topo

def _garantir_terminais_m4(dados):
    """Garante o contrato M4 -> M5 para conectores e terminais.

    Para PDFs rasterizados o M4 já entrega a estrutura pronta. Para PDFs
    vetoriais o M2 não passa pelo M4; neste caso usamos as mesmas rotinas do M4
    sobre as primitivas vetoriais, sem OCR adicional, para produzir o mesmo
    contrato semântico.
    """
    linhas = dados.get('linhas', []) or []
    textos = dados.get('textos', []) or []
    conectores = dados.get('conectores', []) or []
    prontos = all(
        isinstance(t, dict) and 'conector_id' in t and 'segmento_fio' in t
        for c in conectores for t in (c.get('terminais', []) or [])
    ) and bool(conectores)
    if prontos:
        return conectores
    try:
        from deteccao_simbolos import detectar_conectores, enriquecer_terminais
        if not conectores:
            conectores = detectar_conectores(
                dados.get('retangulos', []) or [], textos, linhas
            )
        from deteccao_simbolos import extrair_atributos_fios
        fios_attrs = dados.get('fios') or extrair_atributos_fios(linhas, textos)
        dados['fios'] = fios_attrs
        conectores, terminais = enriquecer_terminais(
            conectores, linhas, textos, fios_attrs=fios_attrs
        )
        dados['conectores'] = conectores
        dados['terminais'] = terminais
        return conectores
    except Exception as exc:
        logger.warning(f'Não foi possível terminalizar conectores M4: {exc}', extra={'modulo':'M5'})
        return conectores


def _segment_candidates_from_terminal(term, segs):
    """Retorna os segmentos explicitamente indicados pelo M4."""
    ids=[]
    sid=term.get('segmento_fio')
    if isinstance(sid,int): ids.append(sid)
    for c in term.get('segmentos_candidatos',[]) or []:
        if isinstance(c,dict) and isinstance(c.get('segmento'),int):
            ids.append(c['segmento'])
    out=[]; seen=set()
    for sid in ids:
        if sid in seen or sid<0 or sid>=len(segs): continue
        seen.add(sid); out.append((sid,segs[sid]))
    return out




def _split_graph_edge_at_point(G, point, segmento):
    """Insere um nó de snap no segmento real do grafo, partindo a aresta.
    Isso é necessário porque o M4 encontra o terminal em uma posição interna
    ao segmento, enquanto a topologia inicial só possui os endpoints.
    """
    try:
        from topologia import _on_segment
    except Exception:
        _on_segment = None
    for u, v, d in list(G.edges(data=True)):
        sid = d.get('segmento_origem', d.get('segmento'))
        if sid != segmento:
            continue
        if not isinstance(u, tuple) or not isinstance(v, tuple):
            continue
        if _on_segment and not _on_segment(point, u, v, tol=2.5):
            continue
        if u == point or v == point:
            return True
        attrs = dict(d)
        G.remove_edge(u, v)
        G.add_node(point, pos=point, tipo='nó_fio', segmento=segmento)
        G.add_edge(u, point, **attrs)
        G.add_edge(point, v, **attrs)
        return True
    return False
def _attach_terminal_explicit(G, label, term, segs):
    """Anexa terminal ao segmento indicado pelo M4, sem buscar o segmento
    mais próximo. A relação explícita é a evidência primária."""
    candidatos=_segment_candidates_from_terminal(term,segs)
    if not candidatos:
        return None, None
    sid,(a,b,attrs)=candidatos[0]
    pos=(float(term.get('x',0)),float(term.get('y',0)))
    dx=b[0]-a[0]; dy=b[1]-a[1]; den=dx*dx+dy*dy or 1.0
    t=max(0.0,min(1.0,((pos[0]-a[0])*dx+(pos[1]-a[1])*dy)/den))
    snap=(round(a[0]+t*dx,3),round(a[1]+t*dy,3))
    _split_graph_edge_at_point(G, snap, sid)
    G.add_node(snap,pos=snap,tipo='nó_fio',segmento=sid)
    meta={
        'pino':term.get('numero'),
        'conector':term.get('conector_id'),
        'fonte_vinculo':'M4_terminal_segmento',
        'score_evidencia':term.get('score_evidencia',0.0),
        'cor_fio':term.get('cor_fio'),
        'bitola':term.get('bitola'),
    }
    G.add_node(label,pos=pos,tipo='pino_conector',**meta)
    G.add_edge(label,snap,relacao='terminal_para_segmento',segmento=sid,
               evidencia='M4_terminal_segmento',cor=term.get('cor_fio'),
               bitola=term.get('bitola'))
    # Coloca atributos no segmento original para propagação da rede.
    for u,v,d in G.edges(snap,data=True):
        if sid == d.get('segmento') or d.get('segmento_origem') == sid:
            if term.get('cor_fio') and not d.get('cor'): d['cor']=term['cor_fio']
            if term.get('bitola') and not d.get('bitola'): d['bitola']=term['bitola']
    return snap, sid

def _attach_connectors(G,segs,connectors):
    attached=[]
    for con in connectors or []:
        cid=con.get('id','CON')
        for term in con.get('terminais',[]) or []:
            p=term.get('numero')
            try:
                pos=(float(term.get('x')),float(term.get('y')))
            except (TypeError,ValueError):
                continue
            if p is None: continue

            # Evidência primária: M4 encontrou o segmento associado ao terminal.
            snap,sid=_attach_terminal_explicit(G,f'{cid}:{p}',term,segs)
            if snap is not None:
                attached.append((f'{cid}:{p}',snap,p,cid))
                continue

            # Fallback deliberadamente mais fraco: só quando M4 não conseguiu
            # determinar um segmento candidato. O score fica explicitamente
            # marcado como proximidade, não como vínculo confirmado.
            node=_attach_nearest(G,f'{cid}:{p}',pos,segs,50,'pino_conector',
                                 {'pino':p,'conector':cid,'fonte_vinculo':'proximidade_fallback',
                                  'score_evidencia':0.35})
            if node: attached.append((f'{cid}:{p}',node,p,cid))
    return attached

def _attach_text_pins(G,segs,pins):
    out=[]
    # Terminais já anexados como parte de um conector não são anexados novamente
    # como PIN:xx; isso evita nós duplicados e falsas conexões no grafo.
    vistos=set()
    for p in pins:
        if p.get('conector'):
            continue
        key=(int(p['numero']),round(float(p['x'])/3),round(float(p['y'])/3))
        if key in vistos:
            continue
        vistos.add(key)
        label=f"PIN:{p['numero']}"
        node=_attach_nearest(G,label,(p['x'],p['y']),segs,90,'pino',p)
        if node:out.append((label,node,p['numero'],p.get('conector')))
    return out

def _attach_perifericos(G,segs,textos):
    out=[]
    stop={'ECU','PIN','PINO','CONNECTOR','CONECTOR','GND','VCC','VDD','VSS',
          'BLACK','BROWN','RED','ORANGE','YELLOW','GREEN','BLUE','VIOLET',
          'PURPLE','GREY','GRAY','WHITE','PINK','BROWN/WHITE','BLUE/WHITE',
          'GREEN/WHITE','RED/WHITE','BLACK/WHITE'}
    for t in textos:
        s=str(t.get('texto','')).strip();u=s.upper()
        if len(s)<3 or u in stop or RE_PIN.fullmatch(s):continue
        if re.fullmatch(r'\d+(?:[.,]\d+)?\s*MM(?:²|2)?', u):continue
        if not any(ch.isalpha() for ch in s):continue
        node=_attach_nearest(G,f'PER:{s}',(float(t.get('x',0)),float(t.get('y',0))),segs,40,'periferico',{'rotulo':s})
        if node:out.append((f'PER:{s}',node,s))
    return out

def _normalizar_label_rede(texto):
    s = re.sub(r'\s+', ' ', str(texto or '').strip().upper())
    m = RE_NET_LABEL.fullmatch(s)
    if m:
        return m.group(1).strip()
    # Rótulos de continuidade típicos: TO_GND, NET_GND, GND_NET.
    if re.fullmatch(r'(?:NET|REDE)_[A-Z0-9./-]{2,35}', s, re.I):
        return s.split('_', 1)[1]
    return None


def _extrair_rotulos_rede(textos):
    refs=[]
    for t in textos or []:
        raw=str(t.get('texto','')).strip()
        label=_normalizar_label_rede(raw)
        if label:
            refs.append({
                'label':label,
                'texto':raw,
                'x':float(t.get('x',0)),
                'y':float(t.get('y',0)),
                'confianca':float(t.get('confianca',70) or 70),
            })
    return refs


def _attach_net_labels(G, segs, textos, pagina, distancia=45.0):
    """Anexa rótulos NET/REDE/SINAL a segmentos.

    O rótulo cria um nó semântico ligado ao segmento mais próximo. O nó só
    serve para continuidade entre páginas; ele não transforma texto distante
    em conexão elétrica.
    """
    refs=_extrair_rotulos_rede(textos)
    attached=[]
    for ref in refs:
        pos=(ref['x'],ref['y'])
        best=None; bestd=float('inf')
        for sid,(a,b,attrs) in enumerate(segs):
            d=_dist_point_seg(pos[0],pos[1],a,b)
            if d < bestd:
                bestd=d; best=(sid,a,b,attrs)
        if best is None or bestd>distancia:
            continue
        sid,a,b,attrs=best
        dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy or 1
        t=max(0,min(1,((pos[0]-a[0])*dx+(pos[1]-a[1])*dy)/den))
        snap=(round(a[0]+t*dx,3), round(a[1]+t*dy,3))
        _split_graph_edge_at_point(G,snap,sid)
        node=f"NET:{ref['label']}@P{pagina}:{round(pos[0],2)}:{round(pos[1],2)}"
        G.add_node(node,tipo='net_label',label_rede=ref['label'],pagina=pagina,pos=pos,
                   confianca=ref['confianca']/100.0,distancia_segmento=bestd)
        G.add_edge(node,snap,relacao='rotulo_rede_segmento',segmento=sid,
                   evidencia='texto_rede',score_evidencia=max(0.0,min(1.0,1-bestd/max(distancia,1))))
        attached.append({'label':ref['label'],'node':node,'segmento':sid,'snap':snap,
                         'distancia':bestd,'pagina':pagina})
    return attached


def _unir_continuidades_paginas(GG, net_labels):
    """Liga rótulos de rede idênticos em páginas distintas e retorna os
    terminais envolvidos em cada continuidade.

    A ligação é lógica/documental, não uma linha geométrica inventada.
    """
    by_label={}
    for rec in net_labels:
        by_label.setdefault(rec['label'], []).append(rec)
    links=[]
    for label, items in by_label.items():
        if len(items)<2:
            continue
        pages={i['pagina'] for i in items}
        if len(pages)<2:
            continue

        # Captura os terminais de cada folha antes de unir as folhas.
        terminais_por_pagina={}
        for item in items:
            node=item.get('node')
            if node not in GG:
                continue
            pinos=[]
            for n in nx.node_connected_component(GG,node):
                nd=GG.nodes[n]
                if nd.get('tipo')=='pino_conector':
                    pinos.append({
                        'conector_id':nd.get('conector'),
                        'pino':nd.get('pino'),
                        'pagina':item['pagina'],
                        'cor_fio':nd.get('cor_fio'),
                        'bitola':nd.get('bitola'),
                    })
            terminais_por_pagina.setdefault(item['pagina'], []).extend(pinos)

        # Liga cada ocorrência da rede à seguinte em outra página.
        for a,b in zip(items, items[1:]):
            if a['pagina']==b['pagina']:
                continue
            if a['node'] not in GG or b['node'] not in GG:
                continue
            score=min(float(a.get('confianca',0.7) or 0.7),
                      float(b.get('confianca',0.7) or 0.7))
            GG.add_edge(a['node'], b['node'],
                        relacao='continuidade_entre_paginas',
                        label_rede=label,
                        paginas=[a['pagina'], b['pagina']],
                        evidencia='rotulo_rede_identico',
                        score_evidencia=score)
            terminais=[]
            for vals in terminais_por_pagina.values():
                terminais.extend(vals)
            links.append({
                'label':label,
                'paginas':[a['pagina'],b['pagina']],
                'terminais':terminais,
                'evidencia':'rotulo_rede_identico',
                'score_evidencia':score,
            })
    return links


def _classificar_barramento(G, pin_records, pagina, limiar=3):
    """Marca redes com >=3 terminais como barramento quando a topologia é
    claramente compartilhada. Não cria uma conexão nova: apenas classifica a
    rede e consolida membros/atributos.
    """
    if not pin_records:
        return []
    por_comp={}
    for label,node,pino,con in pin_records:
        if node in G:
            root=next(iter(nx.node_connected_component(G,node)))
            comp=frozenset(nx.node_connected_component(G,node))
            por_comp.setdefault(comp,[]).append((label,node,pino,con))
    out=[]
    for comp,recs in por_comp.items():
        pinos=sorted({r[2] for r in recs}, key=lambda x:int(x) if str(x).isdigit() else str(x))
        if len(pinos)<limiar:
            continue
        cores=[]; bits=[]
        for n in comp:
            for _,_,d in G.edges(n,data=True):
                if d.get('cor'): cores.append(d['cor'])
                if d.get('bitola'): bits.append(d['bitola'])
        def consenso(vals):
            vals=[v for v in vals if v]
            if not vals:return None
            uniq=sorted(set(vals))
            return uniq[0] if len(uniq)==1 else {'valores':uniq,'conflito':True}
        out.append({'tipo':'barramento','pinos':pinos,'pagina_origem':[pagina],
                    'cor_fio':consenso(cores),'bitola':consenso(bits),
                    'quantidade_terminais':len(pinos),
                    'status':'barramento_topologico',
                    'evidencias':['rede_compartilhada','multiplos_terminais']})
    return out


def _gerar_conexoes_por_nets(G, pin_records, pagina):
    """Gera conexões mesmo quando não existe texto periférico: cada componente
    conectado representa uma rede elétrica. Isso evita o falso diagnóstico de
    '0 conexões' em diagramas que só mostram pinos, fios e barramentos."""
    pin_by_node={}
    for label,node,pino,con in pin_records:
        pin_by_node[node]=pino
    visited=set(); out=[]
    for node,pino in pin_by_node.items():
        if node in visited or node not in G: continue
        comp=nx.node_connected_component(G,node); visited.update(comp)
        pinos=sorted({pin_by_node[n] for n in comp if n in pin_by_node}, key=lambda x:int(x) if str(x).isdigit() else str(x))
        if not pinos: continue
        cores=[]; bitolas=[]; funcoes=[]
        for n in comp:
            for _,v,d in G.edges(n,data=True):
                if d.get('cor'): cores.append(d['cor'])
                if d.get('bitola'): bitolas.append(d['bitola'])
            if G.nodes[n].get('tipo')=='periferico': funcoes.append(G.nodes[n].get('rotulo'))
        # Uma conexão elétrica confirmada precisa ligar pelo menos dois pontos
        # (dois pinos/terminais) ou um terminal a um destino semântico identificado.
        # Cor/bitola isoladas NÃO transformam um terminal em conexão. Elas ficam
        # registradas na evidência do terminal/rede.
        if len(pinos) < 2 and not funcoes:
            continue
        terminal_evid=[]
        for n in comp:
            nd=G.nodes[n]
            if nd.get('tipo')=='pino_conector':
                terminal_evid.append({
                    'conector_id':nd.get('conector'),
                    'pino':nd.get('pino'),
                    'cor_fio':nd.get('cor_fio'),
                    'bitola':nd.get('bitola'),
                    'score_evidencia':nd.get('score_evidencia',0.0)
                })
        out.append({'pinos':pinos,'funcao':funcoes[0] if funcoes else None,
                    'cor_fio':cores[0] if cores else None,'bitola':bitolas[0] if bitolas else None,
                    'tipo':'rede','pagina_origem':[pagina],'status':'rede_topologica',
                    'evidencias':['geometria_topologica','terminal_fio'],
                    'terminais':terminal_evid})
    return out

@monitorar(modulo='M5')
def processar_diagrama_multipagina(dados_paginas):
    if not dados_paginas:raise ErroGrafo('Nenhuma página fornecida',severidade=Severidade.CRITICA)
    grafos={}; pin_nodes={}; conectores_total=[]; topo_stats=[]; coletor=ColetorErros()
    for pag,dados in dados_paginas.items():
        try:
            G,segs,topo=_build_graph(dados)
            conns=_garantir_terminais_m4(dados)
            pins=extrair_pinos_ecu(dados.get('textos',[]),None,conns,dados.get('linhas',[]))
            attached=_attach_connectors(G,segs,conns)
            attached+=_attach_text_pins(G,segs,pins)
            perifs=_attach_perifericos(G,segs,dados.get('textos',[]))
            dados['_terminais_fio_m5']=[
                {
                    'conector_id': c.get('id'),
                    'pino': t.get('numero'),
                    'segmento_fio': t.get('segmento_fio'),
                    'cor_fio': t.get('cor_fio'),
                    'bitola': t.get('bitola'),
                    'score_evidencia': t.get('score_evidencia',0.0),
                    'status': t.get('status')
                }
                for c in conns for t in (c.get('terminais',[]) or [])
            ]
            grafos[pag]=G;conectores_total.extend([{**c,'pagina':pag} for c in conns])
            # registra as relações de rede antes de unificar páginas
            net_labels_page=_attach_net_labels(G,segs,dados.get('textos',[]),pag)
            dados['_net_labels_m5']=net_labels_page
            dados['_pin_records_m5']=attached
            dados['_conexoes_rede_m5']=_gerar_conexoes_por_nets(G,attached,pag)
            dados['_barramentos_m5']=_classificar_barramento(G,attached,pag)
            topo_stats.append({'pagina':pag,'juncoes':topo['num_juncoes'],'cruzamentos_sem_conexao':topo['num_cruzamentos_sem_conexao'],'pontes':topo.get('num_pontes',0),'arestas':len(topo['arestas'])})
            for lab,node,pino,con in attached:
                pin_nodes[f'{pag}:{lab}']=node
        except Exception as exc:
            coletor.adicionar_erro(ErroGrafo(f'Página {pag}: {exc}',causa=exc),severidade=Severidade.MEDIA)
    if not grafos:raise ErroGrafo('Nenhuma página pôde ser processada',dados_extra=coletor.resumo())
    # Grafo global preserva a origem da página; continuidade semântica é anexada como metadado.
    GG=nx.Graph()
    for pag,G in grafos.items():
        mp={}
        for n,d in G.nodes(data=True):
            nn=f'p{pag}:{repr(n)}';mp[n]=nn;attrs=dict(d);attrs['pagina']=pag;GG.add_node(nn,**attrs)
        for u,v,d in G.edges(data=True):GG.add_edge(mp[u],mp[v],**d)
    conexoes=[]
    net_labels=[]
    barramentos=[]
    # Redes elétricas da página: principal saída para diagramas sem nomes periféricos.
    for pag,dados in dados_paginas.items():
        for c in dados.get('_conexoes_rede_m5',[]):
            conexoes.append(c)
        for rec in (dados.get('_net_labels_m5',[]) or []):
            rr=dict(rec)
            # O grafo global prefixa nós com p{pagina}:; remapear aqui mantém
            # a identidade do rótulo entre folhas.
            local_node=rec.get('node')
            rr['node']=f'p{pag}:{repr(local_node)}'
            net_labels.append(rr)
        barramentos.extend(dados.get('_barramentos_m5',[]) or [])

    continuidade_links=_unir_continuidades_paginas(GG,net_labels)
    # Depois da continuidade, reclassifica redes que agora atravessam páginas.
    for link in continuidade_links:
        terminais=link.get('terminais',[]) or []
        pinos=sorted({t.get('pino') for t in terminais if t.get('pino') is not None},
                     key=lambda x:int(x) if str(x).isdigit() else str(x))
        cores=sorted({t.get('cor_fio') for t in terminais if t.get('cor_fio')})
        bits=sorted({t.get('bitola') for t in terminais if t.get('bitola')})
        conexoes.append({'tipo':'continuidade','funcao':link['label'],
                         'pinos':pinos,
                         'cor_fio':cores[0] if len(cores)==1 else (cores if cores else None),
                         'bitola':bits[0] if len(bits)==1 else (bits if bits else None),
                         'terminais':terminais,
                         'pagina_origem':link['paginas'],
                         'status':'continuidade_entre_paginas',
                         'evidencias':['rotulo_rede_identico']})

    # Barramentos substituem a rede genérica equivalente para evitar dupla
    # contagem. O barramento é uma classificação mais específica da mesma rede.
    bus_keys=set()
    for b in barramentos:
        bus_keys.add((tuple(b.get('pinos',[])), tuple(b.get('pagina_origem',[]))))
    if bus_keys:
        conexoes=[c for c in conexoes if not (
            c.get('tipo')=='rede' and
            (tuple(c.get('pinos',[])), tuple(c.get('pagina_origem',[]))) in bus_keys
        )]
    conexoes.extend(barramentos)
    for key,start in list(pin_nodes.items()):
        if start not in GG:continue
        alvo=None; fila=deque([start]);vis={start}
        while fila and alvo is None:
            n=fila.popleft()
            if GG.nodes[n].get('tipo')=='periferico':alvo=GG.nodes[n].get('rotulo');dest=n;break
            for v in GG.neighbors(n):
                if v not in vis:vis.add(v);fila.append(v)
        if alvo:
            pag=int(key.split(':',1)[0]); pino=key.split(':',1)[1].replace('PIN:','')
            conexoes.append({'pino':pino,'destino':alvo,'cor':'','bitola':'','pagina_origem':[pag],'status':'rastreada_topologicamente'})
    logger.info(f'Processamento concluído: {len(conexoes)} conexões, {sum(len(g) for g in grafos.values())} nós, {len(conectores_total)} conectores em {len(grafos)} páginas',extra={'modulo':'M5'})
    return conexoes,GG,pin_nodes,{'conectores':conectores_total,'topologia':topo_stats,
        'continuidade_paginas':continuidade_links,'barramentos':barramentos,'rotulos_rede':net_labels}

def processar_diagrama(dados_pagina):return processar_diagrama_multipagina({1:dados_pagina})
