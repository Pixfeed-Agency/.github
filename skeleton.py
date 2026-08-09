# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Squelette droit rectiligne (chantier S2, noyau)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""SQUELETTE DROIT RECTILIGNE — le toit déduit du plan, pas codé cas
par cas.

Pour une emprise RECTILIGNE (arêtes alignées sur les axes, le cas de
toutes les emprises House: rectangle, L, T, U), le squelette droit à
pentes égales est le lieu des points équidistants de deux arêtes — le
"feu de prairie" qui avance depuis chaque mur à vitesse 1. Chaque arête
engendre UN pan de toit; les crêtes (faîtages), arêtiers et noues sont
les arcs du squelette; l'altitude d'un point du pan = distance à
l'arête × tan(pente).

Noyau PUR PYTHON (aucun bpy): grille de distance exacte par offsets —
pour un polygone rectiligne, la fonction distance-au-bord est linéaire
par morceaux et le squelette est porté par les bissectrices à 45°.

Implémentation v1 (volontairement contrainte, VALIDÉE par tests):
`faces(poly)` retourne, pour chaque arête, le polygone 2D de son pan
(liste de sommets (x, y, d) où d = distance au bord — l'altitude est
d × tan(pente)). Algorithme: décomposition de l'emprise en cellules de
Voronoï d'arêtes sous métrique L∞ orientée, calculée par clipping
successif de demi-plans (les bissectrices entre arêtes rectilignes
sont des droites verticales, horizontales ou à ±45° — le clipping de
polygones convexes par morceaux suffit).
"""


def _clip(poly, side):
    """Clippe un polygone (liste [(x,y),…]) par le demi-plan
    side(p) >= 0 (Sutherland-Hodgman)."""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        fa, fb = side(a), side(b)
        if fa >= -1e-9:
            out.append(a)
        if (fa > 1e-9 and fb < -1e-9) or (fa < -1e-9 and fb > 1e-9):
            t = fa / (fa - fb)
            out.append((a[0] + t * (b[0] - a[0]),
                        a[1] + t * (b[1] - a[1])))
    # dédoublonnage des sommets confondus
    dedup = []
    for p in out:
        if not dedup or abs(p[0] - dedup[-1][0]) > 1e-7 \
                or abs(p[1] - dedup[-1][1]) > 1e-7:
            dedup.append(p)
    if len(dedup) > 1 and abs(dedup[0][0] - dedup[-1][0]) < 1e-7 \
            and abs(dedup[0][1] - dedup[-1][1]) < 1e-7:
        dedup.pop()
    return dedup


def _edge_dist(edge):
    """Fonction distance SIGNÉE au support de l'arête rectiligne,
    positive du côté intérieur."""
    (x0, y0), (x1, y1) = edge
    if abs(y1 - y0) < 1e-9:      # arête horizontale
        s = 1.0 if x1 > x0 else -1.0   # intérieur au-dessus si +x
        return lambda p, y0=y0, s=s: s * (p[1] - y0)
    s = 1.0 if y1 > y0 else -1.0       # arête verticale
    return lambda p, x0=x0, s=s: -s * (p[0] - x0)


def _seg_dist_fn(edge):
    """Distance L∞ au SEGMENT rectiligne — max de 4 formes linéaires.

    Pour un segment vertical x=a, y∈[y0,y1]:
        L(p) = max(x-a, a-x, y0-y, y-y1)
    (les deux derniers termes sont négatifs dans la bande orthogonale
    → distance à la droite; au-delà des bouts ils prennent le relais
    → cônes de coin à 45°). Idem pour l'horizontal. Pour une emprise
    RECTILIGNE, le diagramme de plus-proche-segment sous cette
    métrique est EXACTEMENT le squelette droit à pentes égales.
    """
    (x0, y0), (x1, y1) = edge
    if abs(y1 - y0) < 1e-9:      # horizontal
        a, b = min(x0, x1), max(x0, x1)
        return lambda p: max(p[1] - y0, y0 - p[1], a - p[0], p[0] - b)
    a, b = min(y0, y1), max(y0, y1)
    return lambda p: max(p[0] - x0, x0 - p[0], a - p[1], p[1] - b)


def _point_in_poly(p, poly):
    """Point dans polygone (ray casting, robuste aux bords rectilignes)."""
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) / (y1 - y0) * (x1 - x0)
            if x < xi:
                inside = not inside
    return inside


def faces(poly):
    """Pans du toit d'une emprise rectiligne CCW — squelette droit EXACT.

    Returns: liste (arête_index, [pièces]) où chaque pièce =
    [(x, y, d), …], d = distance au bord (altitude = d·tan(pente)).
    Un pan peut être fragmenté en plusieurs pièces CONVEXES COPLANAIRES
    (même plan 3D: le plan de l'arête) — sans conséquence en aval.

    Méthode: décomposition de l'emprise en cellules où TOUTES les
    distances-segments sont linéaires (grille des coordonnées de
    sommets + diagonales ±45° par sommet), puis attribution de chaque
    cellule au segment le plus proche (centroïde). Exact car dans
    chaque cellule le min des fonctions linéaires est réalisé par un
    unique segment (les égalités tombent SUR les frontières de
    cellules, qui incluent toutes les bissectrices possibles).
    """
    n = len(poly)
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    seg_d = [_seg_dist_fn(e) for e in edges]

    # Les bissectrices entre formes linéaires ±(x−a) / ±(y−b) sont:
    # verticales x=(a1+a2)/2, horizontales y=(b1+b2)/2, ou diagonales
    # x±y = a±b — il faut TOUTES les combinaisons de coordonnées
    # d'arêtes (les médianes entre murs parallèles ne passent par
    # aucun sommet: c'était le trou de la v1 du noyau).
    bx = sorted({round(p[0], 9) for p in poly})
    by = sorted({round(p[1], 9) for p in poly})
    xs = sorted({round(v, 9) for v in bx}
                | {round((a1 + a2) / 2, 9) for a1 in bx for a2 in bx})
    ys = sorted({round(v, 9) for v in by}
                | {round((b1 + b2) / 2, 9) for b1 in by for b2 in by})
    diag_p = sorted({round(a + b, 9) for a in bx for b in by})  # x+y = c
    diag_m = sorted({round(a - b, 9) for a in bx for b in by})  # x−y = c

    pieces_by_edge = {}
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            rect = [(xs[ix], ys[iy]), (xs[ix + 1], ys[iy]),
                    (xs[ix + 1], ys[iy + 1]), (xs[ix], ys[iy + 1])]
            cx = (xs[ix] + xs[ix + 1]) / 2
            cy = (ys[iy] + ys[iy + 1]) / 2
            if not _point_in_poly((cx, cy), poly):
                continue
            # fragmenter par toutes les diagonales ±45°
            frags = [rect]
            for c in diag_p:
                nxt = []
                for f in frags:
                    a = _clip(f, lambda p, c=c: (p[0] + p[1]) - c)
                    b = _clip(f, lambda p, c=c: c - (p[0] + p[1]))
                    nxt += [g for g in (a, b) if len(g) >= 3]
                frags = nxt
            for c in diag_m:
                nxt = []
                for f in frags:
                    a = _clip(f, lambda p, c=c: (p[0] - p[1]) - c)
                    b = _clip(f, lambda p, c=c: c - (p[0] - p[1]))
                    nxt += [g for g in (a, b) if len(g) >= 3]
                frags = nxt
            for f in frags:
                fx = sum(p[0] for p in f) / len(f)
                fy = sum(p[1] for p in f) / len(f)
                win = min(range(n), key=lambda j: seg_d[j]((fx, fy)))
                dw = seg_d[win]
                pieces_by_edge.setdefault(win, []).append(
                    [(x, y, dw((x, y))) for (x, y) in f])
    return [(i, pieces_by_edge[i]) for i in sorted(pieces_by_edge)]


def ridge_segments(cells, eps=1e-6):
    """Arcs du squelette: frontières partagées par les pans de DEUX
    arêtes différentes (faîtages, arêtiers, noues) — pour poser
    faîtières et bandes de noue. Les frontières internes entre pièces
    d'un même pan sont ignorées (coplanaires)."""
    seen = {}
    segs = []
    for idx, pieces in cells:
        for cell in pieces:
            m = len(cell)
            for k in range(m):
                a, b = cell[k], cell[(k + 1) % m]
                if a[2] < eps and b[2] < eps:
                    continue      # arête au sol (le mur lui-même)
                key = tuple(sorted((tuple(round(v, 6) for v in a),
                                    tuple(round(v, 6) for v in b))))
                if key in seen:
                    if seen[key] != idx:
                        segs.append((a, b, seen[key], idx))
                else:
                    seen[key] = idx
    return segs

