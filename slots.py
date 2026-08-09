# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Slots d'assets (chantier qualité n°7)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""SLOTS D'ASSETS — optionnels, JAMAIS obligatoires.

L'utilisateur peut brancher ses propres objets (fenêtre, porte, volet,
tuile) à la place des menuiseries procédurales — importés de l'Asset
Browser, d'un .blend lié, ou modélisés dans le fichier. Slot vide ou
défaillant → House construit sa version PROCÉDURALE comme toujours:
le procédural est le socle, l'asset est un habillage au choix.

Placement: l'asset est copié (mesh partagé), sa boîte englobante est
mise à l'échelle sur les dimensions de l'ouverture, orienté par la
matrice du mur, et lié à la collection House (donc estampillé par
l'étape et nettoyé aux régénérations — l'ORIGINAL n'est jamais touché).
"""

import bpy
from mathutils import Matrix, Vector


def slot_object(props, name):
    """Objet du slot `name`, ou None si vide/inutilisable."""
    obj = getattr(props, name, None)
    if obj is None:
        return None
    try:
        if obj.type != 'MESH' or obj.data is None:
            return None
        # Jamais un objet GÉNÉRÉ par House: il serait supprimé à la
        # prochaine régénération (l'instance pointerait dans le vide)
        if "house_step" in obj.keys() or obj.get("house_part"):
            print(f"[House] Slot {name}: objet généré par House ignoré "
                  f"(choisissez un asset importé)")
            return None
    except ReferenceError:
        return None
    return obj


def _bbox(obj):
    pts = [Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts),
                 min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts),
                 max(p.z for p in pts)))
    return lo, hi


def place_asset(asset, name, width, height, location, rot_matrix,
                collection, part, depth=None, anchor='center'):
    """Copie liée de l'asset, bbox → (width × [depth] × height).

    anchor='center': location = centre de la bbox (convention fenêtres)
    anchor='corner': location = coin min de la bbox (convention portes)
    depth=None → profondeur proportionnée à la moyenne des 2 échelles.
    Retourne l'objet ou None (le caller replie sur le procédural).
    """
    lo, hi = _bbox(asset)
    size = hi - lo
    if min(size.x, size.y, size.z) < 1e-5:
        print(f"[House] Slot {name}: asset plat/vide, repli procédural")
        return None
    sx = width / size.x
    sz = height / size.z
    sy = (depth / size.y) if depth else (sx + sz) / 2
    obj = asset.copy()          # mesh PARTAGÉ (léger), original intact
    obj.name = name
    obj.parent = None
    S = Matrix.Diagonal((sx, sy, sz, 1.0))
    R = rot_matrix.to_4x4() if len(rot_matrix) == 3 else rot_matrix.copy()
    origin = (lo + hi) / 2 if anchor == 'center' else lo
    obj.matrix_world = (Matrix.Translation(location) @ R @ S
                        @ Matrix.Translation(-origin))
    obj["house_part"] = part
    collection.objects.link(obj)
    return obj


def normalized_mesh_copy(asset, target_x, target_y, target_z=None):
    """Mesh COPIÉ et normalisé: coin min à l'origine, x→target_x,
    y→target_y, z proportionnel (ou target_z). Pour les masters
    d'instanciation (tuiles) et les volets (charnière à l'origine)."""
    lo, hi = _bbox(asset)
    size = hi - lo
    if min(size.x, size.y, size.z) < 1e-5:
        return None
    sx = target_x / size.x
    sy = target_y / size.y
    sz = (target_z / size.z) if target_z else (sx + sy) / 2
    me = asset.data.copy()
    for v in me.vertices:
        v.co = Vector(((v.co.x - lo.x) * sx,
                       (v.co.y - lo.y) * sy,
                       (v.co.z - lo.z) * sz))
    me.update()
    return me
