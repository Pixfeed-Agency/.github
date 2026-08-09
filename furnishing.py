# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Aménagement intérieur (niveau rendu client)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""AMÉNAGEMENT — éclairage, cuisine, salle de bain, mobilier.

Le principe est le même que partout dans House: le PROCÉDURAL est le
socle (équipement de base paramétrique, jamais une pièce vide), les
SLOTS D'ASSETS priment quand l'utilisateur y dépose ses propres
meubles (kitchen_asset, bathroom_asset, bed_asset, table_asset,
sofa_asset — y compris ceux créés par lui dans le fichier).

- ÉCLAIRAGE: une suspension par pièce (câble + abat-jour + point
  chaud 2700K), deux dans le séjour — un rendu intérieur EST son
  éclairage.
- CUISINE (mode programme, séjour côté cuisine): linéaire de meubles
  bas + plan de travail + crédence + meubles hauts + évier + plaque.
- SDB: meuble-vasque + miroir + douche (receveur + paroi); WC séparé:
  cuvette + réservoir + lave-mains.
- MOBILIER: lit par chambre, table + canapé au séjour.

Les cellules (chambres/SdB/WC) viennent du programme; hors programme,
l'aménagement équipe les cellules uniformes comme des chambres.
"""

import bpy
import bmesh
from mathutils import Matrix, Vector

from . import norms
from .features import _add_box, _new_mesh_obj, _simple_material


def _cells(props, layout, W, t):
    """[(x0, x1, rôle)] des cellules arrière. Rôles du programme:
    chambres…, 'sdb'×n, 'wc'; sinon tout est 'chambre'."""
    xs = [t] + list(layout.get('x_splits', [])) + [W - t]
    n = len(xs) - 1
    roles = ['chambre'] * n
    if getattr(props, 'programme_active', False):
        nb = int(getattr(props, 'prog_bedrooms', 2))
        nsdb = int(getattr(props, 'prog_bathrooms', 1))
        for i in range(n):
            if i >= nb + nsdb:
                roles[i] = 'wc'
            elif i >= nb:
                roles[i] = 'sdb'
    return [(xs[i], xs[i + 1], roles[i]) for i in range(n)]


def _slot(props, name):
    from . import slots
    return slots.slot_object(props, name)


def _place(asset, name, cx, cy, z, w, d, h, rot_z, collection, part):
    """Asset posé au sol, empreinte ramenée à w×d (hauteur libre —
    on ne déforme pas un meuble), tourné vers la pièce."""
    from . import slots
    lo, hi = slots._bbox(asset)
    size = hi - lo
    if min(size.x, size.y, size.z) < 1e-5:
        return None
    s = min(w / size.x, d / size.y)
    obj = asset.copy()
    obj.name = name
    obj.parent = None
    S = Matrix.Diagonal((s, s, s, 1.0))
    R = Matrix.Rotation(rot_z, 4, 'Z')
    base = Vector((lo.x + size.x / 2, lo.y + size.y / 2, lo.z))
    obj.matrix_world = (Matrix.Translation((cx, cy, z)) @ R @ S
                        @ Matrix.Translation(-base))
    obj["house_part"] = part
    collection.objects.link(obj)
    return obj


# ============================================================
# ÉCLAIRAGE INTÉRIEUR
# ============================================================

def build_lighting(props, collection, layout, wall_depth, fha):
    """Suspensions chaudes par pièce (câble + abat-jour + point 2700K)."""
    W, L = props.house_width, props.house_length
    t = wall_depth
    y_refend = layout['y_refend']
    ceil_z = fha - norms.PLAFOND_EP - 0.02
    mat_shade = _simple_material("House_Lampshade", (0.93, 0.91, 0.86),
                                 roughness=0.6)
    bm = bmesh.new()
    spots = []
    # séjour: deux suspensions réparties
    for fx in (0.3, 0.7):
        spots.append((t + (W - 2 * t) * fx, (t + y_refend) / 2))
    # une par cellule arrière
    for (x0, x1, _r) in _cells(props, layout, W, t):
        spots.append(((x0 + x1) / 2, (y_refend + L - t) / 2))
    made = 0
    for (cx, cy) in spots:
        drop = 0.55
        _add_box(bm, cx - 0.004, cy - 0.004, ceil_z - drop + 0.12,
                 cx + 0.004, cy + 0.004, ceil_z)          # câble
        seg = bmesh.ops.create_cone(bm, cap_ends=False, segments=16,
                                    radius1=0.16, radius2=0.045,
                                    depth=0.16)
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(
                                (cx, cy, ceil_z - drop + 0.10)))
        ld = bpy.data.lights.new("House_Pendant", 'POINT')
        ld.energy = 28.0                        # ~ampoule 800 lm
        ld.color = (1.0, 0.72, 0.48)            # 2700K chaud
        ld.shadow_soft_size = 0.06
        lo = bpy.data.objects.new("House_Pendant", ld)
        lo.location = (cx, cy, ceil_z - drop + 0.04)
        collection.objects.link(lo)
        made += 1
    for f in bm.faces:
        f.smooth = True
    _new_mesh_obj("Interior_Pendants", bm, collection, "lighting",
                  mat_shade)
    print(f"[House] ✓ Éclairage intérieur: {made} suspensions (2700K)")


# ============================================================
# CUISINE (linéaire paramétrique, slot prioritaire)
# ============================================================

def build_kitchen(props, collection, layout, wall_depth, fha):
    W, L = props.house_width, props.house_length
    t = wall_depth
    liner = 0.038
    y_refend = layout['y_refend']
    y0, y1 = t + liner, min(y_refend - 0.9, t + liner + 3.4)
    if y1 - y0 < 1.5:
        print("[House] Cuisine: séjour trop court — non équipée")
        return
    x_face = t + liner                      # mur GAUCHE du séjour
    asset = _slot(props, 'kitchen_asset')
    if asset is not None:
        obj = _place(asset, "Kitchen_Asset", x_face + 0.32,
                     (y0 + y1) / 2, norms.DALLE_EP, 0.65, y1 - y0,
                     0.0, 0.0, collection, "kitchen")
        if obj is not None:
            print("[House] ✓ Cuisine: asset utilisateur posé")
            return
    z0 = norms.DALLE_EP
    d_bas, h_bas = 0.60, 0.90               # meuble bas standard
    mat_c = _simple_material("House_Kitchen", (0.92, 0.92, 0.90),
                             roughness=0.45)
    mat_top = _simple_material("House_Worktop", (0.22, 0.20, 0.19),
                               roughness=0.3)
    mat_inox = _simple_material("House_Inox", (0.75, 0.76, 0.78),
                                roughness=0.25, metallic=0.9)
    bm = bmesh.new()
    n_mod = max(2, int((y1 - y0) / 0.6))
    for i in range(n_mod):                  # caissons + façades
        ya = y0 + (y1 - y0) * i / n_mod + 0.006
        yb = y0 + (y1 - y0) * (i + 1) / n_mod - 0.006
        _add_box(bm, x_face, ya, z0 + 0.10, x_face + d_bas, yb,
                 z0 + h_bas - 0.02)
    _add_box(bm, x_face, y0, z0, x_face + d_bas - 0.06, y1, z0 + 0.10)
    obj = _new_mesh_obj("Kitchen_Base", bm, collection, "kitchen", mat_c)
    bm = bmesh.new()                        # plan de travail + crédence
    _add_box(bm, x_face, y0 - 0.01, z0 + h_bas - 0.02,
             x_face + d_bas + 0.03, y1 + 0.01, z0 + h_bas + 0.02)
    _add_box(bm, x_face, y0, z0 + h_bas + 0.02,
             x_face + 0.012, y1, z0 + h_bas + 0.62)
    _new_mesh_obj("Kitchen_Worktop", bm, collection, "kitchen", mat_top)
    bm = bmesh.new()                        # meubles hauts
    _add_box(bm, x_face, y0, z0 + 1.45, x_face + 0.35, y1, z0 + 2.10)
    _new_mesh_obj("Kitchen_Wall_Units", bm, collection, "kitchen", mat_c)
    bm = bmesh.new()                        # évier + plaque
    ys = y0 + (y1 - y0) * 0.28
    _add_box(bm, x_face + 0.08, ys - 0.25, z0 + h_bas + 0.021,
             x_face + d_bas - 0.08, ys + 0.25, z0 + h_bas + 0.028)
    yp = y0 + (y1 - y0) * 0.72
    _add_box(bm, x_face + 0.06, yp - 0.29, z0 + h_bas + 0.022,
             x_face + d_bas - 0.06, yp + 0.29, z0 + h_bas + 0.026)
    _new_mesh_obj("Kitchen_Sink_Hob", bm, collection, "kitchen", mat_inox)
    print(f"[House] ✓ Cuisine: linéaire {y1 - y0:.1f}m "
          f"({n_mod} caissons, évier, plaque, meubles hauts)")


# ============================================================
# SALLE DE BAIN + WC (paramétrique, slot prioritaire)
# ============================================================

def build_bathroom(props, collection, layout, wall_depth, fha):
    W, L = props.house_width, props.house_length
    t = wall_depth
    y_refend = layout['y_refend']
    yb0, yb1 = y_refend + norms.CLOISON_EP, L - t - 0.04
    z0 = norms.DALLE_EP
    mat_w = _simple_material("House_Sanitaire", (0.96, 0.96, 0.95),
                             roughness=0.15)
    mat_g = _simple_material("House_Verre_Douche", (0.85, 0.90, 0.92),
                             roughness=0.05)
    done = []
    for (x0, x1, role) in _cells(props, layout, W, t):
        if role == 'sdb':
            asset = _slot(props, 'bathroom_asset')
            if asset is not None:
                if _place(asset, "Bathroom_Asset", (x0 + x1) / 2,
                          (yb0 + yb1) / 2, z0, x1 - x0 - 0.2,
                          yb1 - yb0 - 0.2, 0, 0, collection, "bathroom"):
                    done.append('sdb(asset)')
                    continue
            bm = bmesh.new()
            # meuble-vasque contre le refend
            _add_box(bm, x0 + 0.10, yb0 + 0.02, z0 + 0.15,
                     min(x0 + 1.10, x1 - 0.10), yb0 + 0.52, z0 + 0.82)
            _add_box(bm, x0 + 0.14, yb0 + 0.06, z0 + 0.82,
                     min(x0 + 1.06, x1 - 0.14), yb0 + 0.48, z0 + 0.90)
            # miroir
            _add_box(bm, x0 + 0.18, yb0 + 0.005, z0 + 1.10,
                     min(x0 + 1.02, x1 - 0.18), yb0 + 0.02, z0 + 1.85)
            # receveur de douche au fond (90×90) + colonne
            sx1 = x1 - 0.06
            sx0 = max(x0 + 0.10, sx1 - 0.90)
            _add_box(bm, sx0, yb1 - 0.90, z0, sx1, yb1, z0 + 0.06)
            _add_box(bm, sx0 + 0.02, yb1 - 0.06, z0 + 0.06,
                     sx0 + 0.08, yb1 - 0.02, z0 + 2.0)
            ob = _new_mesh_obj("Bathroom_Fixtures", bm, collection,
                               "bathroom", mat_w)
            bm = bmesh.new()                # paroi de douche
            _add_box(bm, sx0 - 0.008, yb1 - 0.92, z0 + 0.06,
                     sx0, yb1, z0 + 2.0)
            _new_mesh_obj("Bathroom_Shower_Glass", bm, collection,
                          "bathroom", mat_g)
            done.append('sdb')
        elif role == 'wc':
            bm = bmesh.new()
            cx = (x0 + x1) / 2
            # cuvette + réservoir contre le mur arrière
            _add_box(bm, cx - 0.19, yb1 - 0.70, z0 + 0.05,
                     cx + 0.19, yb1 - 0.28, z0 + 0.42)
            _add_box(bm, cx - 0.19, yb1 - 0.24, z0 + 0.42,
                     cx + 0.19, yb1 - 0.06, z0 + 0.82)
            # lave-mains d'angle
            _add_box(bm, x0 + 0.06, yb0 + 0.04, z0 + 0.80,
                     x0 + 0.44, yb0 + 0.34, z0 + 0.88)
            _new_mesh_obj("WC_Fixtures", bm, collection, "bathroom",
                          mat_w)
            done.append('wc')
    if done:
        print(f"[House] ✓ Sanitaires: {', '.join(done)}")


# ============================================================
# MOBILIER (slots prioritaires, repli procédural minimal)
# ============================================================

def build_furniture(props, collection, layout, wall_depth, fha):
    W, L = props.house_width, props.house_length
    t = wall_depth
    y_refend = layout['y_refend']
    z0 = norms.DALLE_EP
    yb1 = L - t - 0.05
    mat_bois = _simple_material("House_Furn_Wood", (0.45, 0.32, 0.20),
                                roughness=0.5)
    mat_tissu = _simple_material("House_Furn_Fabric", (0.55, 0.53, 0.48),
                                 roughness=0.9)
    mat_lit = _simple_material("House_Furn_Bed", (0.88, 0.87, 0.84),
                               roughness=0.8)
    # --- LITS: un par chambre, tête contre le mur arrière ---
    bed = _slot(props, 'bed_asset')
    for (x0, x1, role) in _cells(props, layout, W, t):
        if role != 'chambre' or (x1 - x0) < 1.8:
            continue
        cx = (x0 + x1) / 2
        if bed is not None and _place(bed, "Furn_Bed_Asset", cx,
                                      yb1 - 1.0, z0, 1.6, 2.0, 0, 0,
                                      collection, "furniture"):
            continue
        bm = bmesh.new()
        _add_box(bm, cx - 0.75, yb1 - 2.0, z0 + 0.12,
                 cx + 0.75, yb1, z0 + 0.32)                  # sommier
        _add_box(bm, cx - 0.72, yb1 - 1.96, z0 + 0.32,
                 cx + 0.72, yb1 - 0.04, z0 + 0.50)           # matelas
        _add_box(bm, cx - 0.75, yb1 - 0.06, z0 + 0.32,
                 cx + 0.75, yb1, z0 + 1.05)                  # tête
        _new_mesh_obj("Furn_Bed", bm, collection, "furniture", mat_lit)
    # --- SÉJOUR: table + canapé ---
    cxs = t + (W - 2 * t) * 0.62
    cys = (t + y_refend) / 2
    table = _slot(props, 'table_asset')
    if not (table is not None and _place(table, "Furn_Table_Asset",
                                         cxs, cys, z0, 1.6, 0.9, 0, 0,
                                         collection, "furniture")):
        bm = bmesh.new()
        _add_box(bm, cxs - 0.8, cys - 0.45, z0 + 0.72,
                 cxs + 0.8, cys + 0.45, z0 + 0.76)
        for px in (cxs - 0.72, cxs + 0.66):
            for py in (cys - 0.37, cys + 0.31):
                _add_box(bm, px, py, z0, px + 0.06, py + 0.06, z0 + 0.72)
        _new_mesh_obj("Furn_Table", bm, collection, "furniture", mat_bois)
    sofa = _slot(props, 'sofa_asset')
    cxc = t + (W - 2 * t) * 0.62
    cyc = t + 0.55
    if not (sofa is not None and _place(sofa, "Furn_Sofa_Asset",
                                        cxc, cyc, z0, 2.2, 0.95, 0, 0,
                                        collection, "furniture")):
        bm = bmesh.new()
        _add_box(bm, cxc - 1.1, cyc - 0.45, z0 + 0.10,
                 cxc + 1.1, cyc + 0.45, z0 + 0.45)           # assise
        _add_box(bm, cxc - 1.1, cyc - 0.45, z0 + 0.45,
                 cxc + 1.1, cyc - 0.25, z0 + 0.85)           # dossier
        for sx in (-1.1, 0.95):
            _add_box(bm, cxc + sx, cyc - 0.45, z0 + 0.45,
                     cxc + sx + 0.15, cyc + 0.45, z0 + 0.62)  # accoudoirs
        _new_mesh_obj("Furn_Sofa", bm, collection, "furniture", mat_tissu)
    print("[House] ✓ Mobilier: lits, table, canapé (slots prioritaires)")
