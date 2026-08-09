# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Plan 2D unifié (chantier S1, noyau)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""PLAN 2D UNIFIÉ — l'emprise de la maison est UN contour, pas des
boîtes accolées.

`union_rects(rects)` fait l'union de rectangles alignés (maison +
ailes + garage) et retourne le contour extérieur CCW — la vérité 2D
unique consommée par:
- S1: les murs extrudés manifold (un seul volume par niveau),
- S2: le toit par squelette droit (skeleton.faces sur CE contour).

Python pur (aucun bpy). Méthode robuste: grille des coordonnées,
cellules couvertes, arêtes de frontière (exactement un côté couvert),
chaînage en boucle, fusion des colinéaires.
"""


def union_rects(rects, eps=1e-9):
    """Union de rectangles (x0, y0, x1, y1) → contour extérieur CCW.

    Hypothèses (garanties par House): l'union est CONNEXE et SANS TROU
    (les ailes touchent la maison). Lève ValueError sinon.
    """
    rects = [(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
             for (x0, y0, x1, y1) in rects]
    xs = sorted({round(v, 9) for r in rects for v in (r[0], r[2])})
    ys = sorted({round(v, 9) for r in rects for v in (r[1], r[3])})

    def covered(ix, iy):
        cx = (xs[ix] + xs[ix + 1]) / 2
        cy = (ys[iy] + ys[iy + 1]) / 2
        return any(r[0] - eps < cx < r[2] + eps
                   and r[1] - eps < cy < r[3] + eps for r in rects)

    cov = [[covered(ix, iy) for iy in range(len(ys) - 1)]
           for ix in range(len(xs) - 1)]

    # Arêtes de frontière ORIENTÉES (intérieur à gauche → contour CCW)
    edges = {}   # départ → arrivée

    def add(a, b):
        if a in edges:
            raise ValueError("emprise non simple (sommet partagé)")
        edges[a] = b

    nx, ny = len(xs) - 1, len(ys) - 1
    for ix in range(nx):
        for iy in range(ny):
            if not cov[ix][iy]:
                continue
            x0, x1 = xs[ix], xs[ix + 1]
            y0, y1 = ys[iy], ys[iy + 1]
            if iy == 0 or not cov[ix][iy - 1]:      # bord bas → +x
                add((x0, y0), (x1, y0))
            if iy == ny - 1 or not cov[ix][iy + 1]:  # bord haut → -x
                add((x1, y1), (x0, y1))
            if ix == 0 or not cov[ix - 1][iy]:      # bord gauche → -y
                add((x0, y1), (x0, y0))
            if ix == nx - 1 or not cov[ix + 1][iy]:  # bord droit → +y
                add((x1, y0), (x1, y1))

    if not edges:
        raise ValueError("emprise vide")

    # Chaînage en boucle unique
    start = min(edges)      # sommet bas-gauche
    loop = [start]
    cur = edges.pop(start)
    while cur != start:
        loop.append(cur)
        if cur not in edges:
            raise ValueError("contour ouvert (emprise non connexe?)")
        cur = edges.pop(cur)
    if edges:
        raise ValueError("emprise non connexe ou trouée "
                         f"({len(edges)} arête(s) restante(s))")

    # Fusion des sommets colinéaires (les coupes de grille internes)
    out = []
    m = len(loop)
    for i in range(m):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % m]
        colin = (abs(a[0] - b[0]) < eps and abs(b[0] - c[0]) < eps) or \
                (abs(a[1] - b[1]) < eps and abs(b[1] - c[1]) < eps)
        if not colin:
            out.append(b)
    return out


def house_footprint(props, wings=None):
    """Emprise maison + ailes/garage sous forme de rectangles, puis
    contour unifié. Les repères d'ailes (volumes.wing_frame) donnent
    leur rectangle MONDE via footprint (fp = x0, y0, x1, y1)."""
    rects = [(0.0, 0.0, props.house_width, props.house_length)]
    for wing in (wings or []):
        fp = wing.get('footprint')
        if fp:
            rects.append(tuple(fp))
    return union_rects(rects)
