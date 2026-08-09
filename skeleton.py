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


def faces(poly):
    """Pans du toit d'une emprise rectiligne CCW.

    Returns: liste (arête_index, polygone) où polygone = [(x, y, d),…],
    d = distance au bord (altitude = d·tan(pente)). Chaque cellule est
    l'ensemble des points strictement plus proches de SON arête que de
    toute autre (métrique par fonctions de distance d'arêtes) — pour
    une emprise rectiligne à pentes égales c'est exactement le pan du
    squelette droit.
    """
    n = len(poly)
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    dists = [_edge_dist(e) for e in edges]
    out = []
    for i, e in enumerate(edges):
        cell = [tuple(p) for p in poly]
        di = dists[i]
        for j in range(n):
            if j == i:
                continue
            dj = dists[j]
            cell = _clip(cell, lambda p, di=di, dj=dj: dj(p) - di(p))
            if not cell:
                break
        if len(cell) >= 3:
            out.append((i, [(x, y, di((x, y))) for (x, y) in cell]))
    return out


def ridge_segments(cells, eps=1e-6):
    """Arcs du squelette: arêtes partagées par deux cellules (faîtages,
    arêtiers, noues) — utile pour poser faîtières et bandes de noue."""
    seen = {}
    segs = []
    for idx, cell in cells:
        m = len(cell)
        for k in range(m):
            a, b = cell[k], cell[(k + 1) % m]
            if a[2] < eps and b[2] < eps:
                continue          # arête au sol (le mur lui-même)
            key = tuple(sorted((tuple(round(v, 6) for v in a),
                                tuple(round(v, 6) for v in b))))
            if key in seen:
                segs.append((a, b, seen[key], idx))
            else:
                seen[key] = idx
    return segs


# ÉTAT S2 (noyau): carré et rectangle EXACTS (pans, aires, faîtages);
# emprise en L: couverture et altitudes exactes (75/75), mais les
# arêtes en about (bouts du L) n'ont pas encore leur pan propre — il
# faut le clipping supplémentaire par les BISSECTRICES DE COINS aux
# extrémités de chaque arête (coins convexes: 45°; coins rentrants:
# événement de split). C'est la prochaine étape avant le branchement
# sur les builders de toit (GABLE = squelette + pignons forcés,
# HIP = squelette pur, ailes = natif).
