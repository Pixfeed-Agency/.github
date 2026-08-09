# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Combles aménagés (chantier volumétrie)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""COMBLES AMÉNAGÉS — le niveau sous rampants des longères.

La règle de construction réelle (le brief type: "2,40 m sous entrait,
mur de 1,00 m sous panne sablière"):
- PLANCHER de combles posé à l'arase des murs (solives + panneaux),
  troué par la TRÉMIE de l'escalier;
- JAMBETTES (murs droits de 1,00 m) là où le rampant devient trop bas;
- RAMPANTS PLÂTRÉS suivant la sous-face du toit entre jambette et
  plafond;
- PLAFOND PLAT à 2,40 m (sous entraits) là où la hauteur le permet;
- ESCALIER continué depuis le RDC (volée calculée sur la hauteur
  d'arase) + garde-corps de trémie;
- option FERMES APPARENTES: entraits + arbalétriers en bois visible.

GABLE uniquement (le comble d'une croupe/mansarde viendra ensuite).
"""

import math

import bmesh
from mathutils import Matrix, Vector

from . import norms
from .features import _add_box, _new_mesh_obj, _simple_material

KNEE_H = 1.00          # jambette (mur sous sablière)
CEIL_H = 2.40          # plafond plat sous entrait
FLOOR_T = 0.18         # plancher de combles (solives + panneaux)
PLASTER_T = 0.04       # rampant plâtré
SOUS_TOIT = 0.22       # réserve verticale sous le PLAN DU TOIT
#                        (chevrons + isolant + plâtre — le rampant fini
#                        est ~22cm sous les tuiles, jamais dedans)


def _wood():
    try:
        from . import look
        return look.wood_material("House_Charpente",
                                  base=(0.42, 0.30, 0.19), rough=0.6)
    except Exception:
        return _simple_material("House_Charpente", (0.42, 0.30, 0.19),
                                roughness=0.6)


def build(props, collection, wall_top, pitch_deg, wall_depth,
          tremie=None):
    """Construit le niveau de combles. Retourne le z du plancher fini."""
    W, L = props.house_width, props.house_length
    t = wall_depth
    slope = math.tan(math.radians(pitch_deg))
    ridge_along_y = L >= W
    span = (W if ridge_along_y else L)
    half = span / 2
    ridge_h = half * slope                    # au-dessus de l'arase
    z0 = wall_top                             # dessous du plancher
    zf = z0 + FLOOR_T                         # sol fini des combles
    plaster = _simple_material("House_Plaster", (0.92, 0.91, 0.88),
                               roughness=0.9)
    parquet = _simple_material("House_Parquet_Combles",
                               (0.62, 0.42, 0.24), roughness=0.5)

    # Le PLAN DU TOIT passe par l'arase (z0) au nu EXTÉRIEUR du mur et
    # monte de `slope`. Le rampant fini est SOUS_TOIT plus bas. Les
    # distances sont donc mesurées depuis le nu extérieur — la première
    # version soustrayait t (nu intérieur) et le plâtre PERÇAIT les
    # tuiles à mi-pente.
    d_knee = (KNEE_H + FLOOR_T + SOUS_TOIT) / slope
    d_ceil = max(d_knee + 0.3, (CEIL_H + FLOOR_T + SOUS_TOIT) / slope)
    usable = half - d_knee
    # il faut ATTEINDRE 2,40 m sous le faîtage (sinon le plafond plat
    # percerait les versants) et garder une largeur de pièce
    if usable < 1.2 or ridge_h < CEIL_H + FLOOR_T + SOUS_TOIT + 0.05:
        print("[House] ⚠️ Combles: pente/portée insuffisantes pour "
              "aménager (augmentez la pente ou le faîtage cible) — "
              "combles non bâtis")
        return None

    # --- PLANCHER (troué par la trémie) ---
    bm = bmesh.new()
    x0, y0, x1, y1 = t, t, W - t, L - t
    if tremie is not None:
        hx0, hy0, hx1, hy1 = tremie
        hx0, hx1 = max(x0, hx0), min(x1, hx1)
        hy0, hy1 = max(y0, hy0), min(y1, hy1)
        boxes = []
        if hx0 > x0:
            boxes.append((x0, y0, hx0, y1))
        if hx1 < x1:
            boxes.append((hx1, y0, x1, y1))
        if hy0 > y0:
            boxes.append((hx0, y0, hx1, hy0))
        if hy1 < y1:
            boxes.append((hx0, hy1, hx1, y1))
        for (bx0, by0, bx1, by1) in boxes:
            _add_box(bm, bx0, by0, z0, bx1, by1, zf)
    else:
        _add_box(bm, x0, y0, z0, x1, y1, zf)
    _new_mesh_obj("Attic_Floor", bm, collection, "floor", parquet)

    # --- JAMBETTES + RAMPANTS + PLAFOND PLAT (selon l'axe du faîtage) --
    bm = bmesh.new()
    bmr = bmesh.new()

    def side_profile(low_at, sign):
        """Jambette + rampant pour UN versant. low_at = coordonnée du
        mur d'égout; sign = +1 si l'intérieur est vers +axe."""
        k = low_at + sign * d_knee            # position de la jambette
        c = low_at + sign * d_ceil            # début du plafond plat
        if ridge_along_y:                     # faîtage Y → versants ±X
            a0, a1 = t, L - t
            _add_box(bm, min(k, k + sign * 0.05), a0, zf,
                     max(k, k + sign * 0.05), a1, zf + KNEE_H)
            # rampant plâtré (quad incliné épais)
            p0 = Vector((k, a0, zf + KNEE_H))
            p1 = Vector((c, a0, zf + CEIL_H))
            for (aa, bb) in ((a0, a1),):
                v = [bmr.verts.new((p0.x, aa, p0.z)),
                     bmr.verts.new((p1.x, aa, p1.z)),
                     bmr.verts.new((p1.x, bb, p1.z)),
                     bmr.verts.new((p0.x, bb, p0.z))]
                bmr.faces.new(v)
        else:                                 # faîtage X → versants ±Y
            a0, a1 = t, W - t
            _add_box(bm, a0, min(k, k + sign * 0.05), zf,
                     a1, max(k, k + sign * 0.05), zf + KNEE_H)
            p0 = Vector((a0, k, zf + KNEE_H))
            p1 = Vector((a0, c, zf + CEIL_H))
            v = [bmr.verts.new((a0, p0.y, p0.z)),
                 bmr.verts.new((a0, p1.y, p1.z)),
                 bmr.verts.new((a1, p1.y, p1.z)),
                 bmr.verts.new((a1, p0.y, p0.z))]
            bmr.faces.new(v)

    if ridge_along_y:
        side_profile(0.0, +1)
        side_profile(W, -1)
        _add_box(bm, max(t, d_ceil), t, zf + CEIL_H,
                 min(W - t, W - d_ceil), L - t, zf + CEIL_H + 0.05)
    else:
        side_profile(0.0, +1)
        side_profile(L, -1)
        _add_box(bm, t, max(t, d_ceil), zf + CEIL_H,
                 W - t, min(L - t, L - d_ceil), zf + CEIL_H + 0.05)
    _new_mesh_obj("Attic_KneeWalls_Ceiling", bm, collection, "wall",
                  plaster)
    _new_mesh_obj("Attic_Rampants", bmr, collection, "wall", plaster)

    # --- FERMES APPARENTES (option) ---
    if getattr(props, 'attic_trusses', False):
        wood = _wood()
        bm = bmesh.new()
        run = (L if ridge_along_y else W)
        n_f = max(2, int(run / 2.4))
        for i in range(n_f):
            a = t + 0.3 + (run - 2 * t - 0.6) * i / max(1, n_f - 1)
            # les abouts s'encastrent de 2cm dans les rampants (pas
            # plus: au-delà ils ressortent à travers les tuiles)
            if ridge_along_y:
                # entrait sous plafond (le long de X)
                _add_box(bm, d_ceil - 0.02, a - 0.07,
                         zf + CEIL_H - 0.16,
                         W - d_ceil + 0.02, a + 0.07,
                         zf + CEIL_H - 0.02)
            else:
                _add_box(bm, a - 0.07, d_ceil - 0.02,
                         zf + CEIL_H - 0.16,
                         a + 0.07, L - d_ceil + 0.02,
                         zf + CEIL_H - 0.02)
        _new_mesh_obj("Attic_Trusses", bm, collection, "roof", wood)
        print(f"[House] ✓ Fermes apparentes: {n_f} entraits")

    # --- ÉCLAIRAGE (les combles n'ont pas de fenêtres: sans
    # suspensions, tout rendu intérieur est noir) ---
    if getattr(props, 'include_interior_lights', False):
        import bpy
        run = (L if ridge_along_y else W)
        mid = (W / 2 if ridge_along_y else L / 2)
        bm = bmesh.new()
        shade = _simple_material("House_Lampshade", (0.93, 0.91, 0.86),
                                 roughness=0.6)
        z_l = zf + CEIL_H - 0.55
        n_l = max(2, int(run / 5))
        for i in range(n_l):
            a = t + 1.0 + (run - 2 * t - 2.0) * i / max(1, n_l - 1)
            cx, cy = (mid, a) if ridge_along_y else (a, mid)
            _add_box(bm, cx - 0.004, cy - 0.004, z_l + 0.10,
                     cx + 0.004, cy + 0.004, zf + CEIL_H)     # câble
            seg = bmesh.ops.create_cone(bm, cap_ends=False, segments=16,
                                        radius1=0.16, radius2=0.045,
                                        depth=0.16)
            bmesh.ops.transform(
                bm, verts=seg['verts'],
                matrix=Matrix.Translation((cx, cy, z_l + 0.10)))
            ld = bpy.data.lights.new("Attic_Pendant", 'POINT')
            ld.energy = 28.0
            ld.color = (1.0, 0.72, 0.48)
            ld.shadow_soft_size = 0.06
            lo = bpy.data.objects.new("Attic_Pendant", ld)
            lo.location = (cx, cy, z_l + 0.04)
            collection.objects.link(lo)
        for f in bm.faces:
            f.smooth = True
        _new_mesh_obj("Attic_Pendants", bm, collection, "lighting", shade)
        print(f"[House] ✓ Éclairage combles: {n_l} suspensions")

    print(f"[House] ✓ Combles aménagés: plancher à {zf:.2f}m, jambettes "
          f"{KNEE_H:.2f}m à {d_knee:.2f}m du mur, plafond {CEIL_H:.2f}m")
    return zf
