"""Núcleo topológico PRO do PEPERTILO.

Regras:
- T-junction conecta.
- Cruzamento interior/interior NÃO conecta por padrão.
- Emenda/ponto explícito conecta.
- Ponte gráfica explícita mantém os ramos separados.
- Endpoints muito próximos podem ser agrupados (snap).
- Barramentos são uma propriedade semântica da rede, não uma conexão
  automática de qualquer texto próximo.
"""
from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on_segment(p: Point, a: Point, b: Point, tol=1.5) -> bool:
    return (
        min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol
        and abs(_cross(a, b, p)) <= tol * max(1.0, math.hypot(b[0]-a[0], b[1]-a[1]))
    )


def _near_point(p: Point, pts, tol):
    return any(math.hypot(p[0]-q[0], p[1]-q[1]) <= tol for q in pts)


def _endpoint(p: Point, s: Segment, tol=2.0):
    return (
        math.hypot(p[0]-s[0][0], p[1]-s[0][1]) <= tol
        or math.hypot(p[0]-s[1][0], p[1]-s[1][1]) <= tol
    )


def _intersection(a: Point, b: Point, c: Point, d: Point):
    r = (b[0]-a[0], b[1]-a[1])
    s = (d[0]-c[0], d[1]-c[1])
    den = r[0]*s[1] - r[1]*s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0]-a[0])*s[1] - (c[1]-a[1])*s[0]) / den
    u = ((c[0]-a[0])*r[1] - (c[1]-a[1])*r[0]) / den
    if -0.02 <= t <= 1.02 and -0.02 <= u <= 1.02:
        return (a[0]+t*r[0], a[1]+t*r[1])
    return None


def reconstruir_topologia(
    linhas: List[Segment],
    emendas=None,
    pontes=None,
    snap_tol=4.0,
    cruzamento_tol=2.0,
) -> Dict[str, Any]:
    """Reconstrói segmentos e classifica interseções.

    ``pontes`` é uma lista de pontos de cruzamento explicitamente identificados
    como ponte gráfica. Eles NÃO conectam os segmentos.
    """
    emendas = [tuple(map(float, e[:2])) for e in (emendas or [])
               if isinstance(e, (list, tuple)) and len(e) >= 2]
    pontes = [tuple(map(float, p[:2])) for p in (pontes or [])
              if isinstance(p, (list, tuple)) and len(p) >= 2]

    segs = []
    for item in linhas or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        a, b = item[:2]
        if len(a) >= 2 and len(b) >= 2:
            segs.append((tuple(map(float, a)), tuple(map(float, b))))

    intersecoes = []
    for i in range(len(segs)):
        for j in range(i+1, len(segs)):
            p = _intersection(*segs[i], *segs[j])
            if p is None:
                continue

            explicit_bridge = _near_point(p, pontes, snap_tol)
            marked = _near_point(p, emendas, snap_tol)
            endpoint_a = _endpoint(p, segs[i], cruzamento_tol)
            endpoint_b = _endpoint(p, segs[j], cruzamento_tol)

            if explicit_bridge:
                tipo = 'ponte_grafica'
                conecta = False
            elif marked:
                tipo = 'junção'
                conecta = True
            elif endpoint_a or endpoint_b:
                tipo = 'junção_T'
                conecta = True
            else:
                tipo = 'cruzamento_sem_conexao'
                conecta = False

            intersecoes.append({
                'ponto': p,
                'tipo': tipo,
                'conecta': conecta,
                'segmentos': (i, j),
            })

    cuts = [set([s[0], s[1]]) for s in segs]
    for item in intersecoes:
        if item['conecta']:
            p = item['ponto']
            i, j = item['segmentos']
            cuts[i].add(p)
            cuts[j].add(p)

    # Snap apenas pontos de corte/endpoints; pontes não introduzem ponto de corte.
    all_pts = [p for c in cuts for p in c]
    clusters = []
    for p in all_pts:
        found = False
        for cl in clusters:
            if math.hypot(p[0]-cl[0][0], p[1]-cl[0][1]) <= snap_tol:
                cl.append(p)
                found = True
                break
        if not found:
            clusters.append([p])

    centers = {}
    for cl in clusters:
        center = (
            sum(p[0] for p in cl) / len(cl),
            sum(p[1] for p in cl) / len(cl),
        )
        for p in cl:
            centers[p] = center

    edges = []
    for idx, c in enumerate(cuts):
        pts = list(c)
        a, b = segs[idx]
        dx, dy = b[0]-a[0], b[1]-a[1]
        den = dx*dx + dy*dy or 1
        pts.sort(key=lambda p: ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / den)
        pts = [centers.get(p, p) for p in pts]
        for p, q in zip(pts, pts[1:]):
            if math.hypot(p[0]-q[0], p[1]-q[1]) > 0.5:
                edges.append({
                    'a': p,
                    'b': q,
                    'segmento_origem': idx,
                })

    return {
        'segmentos_originais': segs,
        'arestas': edges,
        'intersecoes': intersecoes,
        'emendas': emendas,
        'pontes': pontes,
        'num_juncoes': sum(1 for x in intersecoes if x['conecta']),
        'num_cruzamentos_sem_conexao': sum(
            1 for x in intersecoes if x['tipo'] == 'cruzamento_sem_conexao'
        ),
        'num_pontes': sum(1 for x in intersecoes if x['tipo'] == 'ponte_grafica'),
    }
