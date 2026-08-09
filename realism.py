# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Pack réalisme (textures scannées + HDRI optionnels)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""PACK RÉALISME — le standard Revit/Enscape, en OPTION.

Le socle de House reste 100% procédural (extension légère, autonome).
Mais aucun shader mathématique n'égale une VRAIE surface scannée: les
moteurs pros posent des photos PBR et des ciels HDRI. Ce module branche
ce standard sans alourdir l'extension: l'utilisateur télécharge des
matériaux CC0 GRATUITS (polyhaven.com, ambientcg.com) dans UN dossier,
House le scanne et bascule les matériaux couverts sur les scans.

Structure du dossier (`realism_dir` dans le panneau):
    <dossier>/
        pierre/   ← façades wall_finish=PIERRE
        enduit/   ← façades CREPI_FIN / CREPI_GROS / AUTO
        sol/      ← pelouse/terrain
        tuiles/   ← pans de toit NON couverts de tuiles 3D
        *.hdr|*.exr (à la racine) ← ciel HDRI (remplace Nishita)

Chaque sous-dossier contient un set PBR aux conventions ambientCG ou
Poly Haven (*_Color, *_Roughness, *_NormalGL, *_AmbientOcclusion,
*_Displacement — casse libre). Slot vide/incomplet → matériau
PROCÉDURAL habituel: rien ne casse jamais.
"""

import os

# ordre de test: le premier motif trouvé gagne
MAP_PATTERNS = {
    'color': ('color', 'albedo', 'diff', 'basecolor', 'base_color'),
    'roughness': ('roughness', 'rough'),
    'normal': ('normalgl', 'nor_gl', 'normal'),
    'ao': ('ambientocclusion', 'occlusion', '_ao'),
    'height': ('displacement', 'height', 'disp'),
}
IMG_EXT = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.webp')
SLOTS = ('pierre', 'enduit', 'sol', 'tuiles')
# taille physique couverte par une répétition de texture (m)
SLOT_SIZE = {'pierre': 2.5, 'enduit': 3.0, 'sol': 2.0, 'tuiles': 1.6}


def _scan_set(folder):
    """{map_type: chemin} d'un sous-dossier de textures.
    Tolère UN niveau de sous-dossier (les zips Poly Haven/ambientCG
    s'extraient souvent dans `pierre/old_stone_wall_8k/…`)."""
    try:
        files = sorted(os.listdir(folder))
    except OSError:
        return {}
    out = {}

    def try_file(path, fname):
        low = fname.lower()
        if not low.endswith(IMG_EXT):
            return
        for mtype, pats in MAP_PATTERNS.items():
            if mtype in out:
                continue
            if any(p in low for p in pats):
                out[mtype] = path
                break

    for f in files:
        try_file(os.path.join(folder, f), f)
    if 'color' not in out:
        for f in files:
            sub = os.path.join(folder, f)
            if os.path.isdir(sub):
                try:
                    for g in sorted(os.listdir(sub)):
                        try_file(os.path.join(sub, g), g)
                except OSError:
                    continue
                if 'color' in out:
                    break
    return out


def scan(dirpath):
    """Scanne le dossier réalisme → {'pierre': {...}, 'hdri': path, …}.
    Dossier absent/vide → {} (tout reste procédural)."""
    out = {}
    if not dirpath:
        return out
    dirpath = os.path.expanduser(bpy_abspath(dirpath))
    if not os.path.isdir(dirpath):
        return out
    for slot in SLOTS:
        sub = os.path.join(dirpath, slot)
        if os.path.isdir(sub):
            maps = _scan_set(sub)
            if 'color' in maps:
                out[slot] = maps
    try:
        for f in sorted(os.listdir(dirpath)):
            if f.lower().endswith(('.hdr', '.exr')):
                out['hdri'] = os.path.join(dirpath, f)
                break
    except OSError:
        pass
    return out


def bpy_abspath(path):
    """// de Blender → absolu (sans dépendre d'un .blend sauvé)."""
    try:
        import bpy
        return bpy.path.abspath(path)
    except Exception:
        return path


def active(props):
    """Le scan du dossier utilisateur, ou {} si non configuré."""
    return scan(getattr(props, 'realism_dir', ''))


def maps_for(props, slot):
    """Les maps d'un slot ('pierre'…), ou None → procédural."""
    return active(props).get(slot)


def report(props):
    """Résumé lisible pour l'UI: slots trouvés + hdri."""
    found = active(props)
    if not found:
        return None
    parts = [s for s in SLOTS if s in found]
    if 'hdri' in found:
        parts.append("ciel HDRI")
    return ", ".join(parts)
