# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Materials Presets Module
#  Copyright (C) 2025 mvaertan
#
#  Gestionnaire centralisé des presets de matériaux procéduraux
#  Architecture modulaire : 1 fichier = 1 preset
#
# ##### END GPL LICENSE BLOCK #####

"""Module de gestion des presets de matériaux procéduraux

Architecture:
- Chaque preset est dans un fichier séparé (ex: brick_red_ultimate.py)
- Fonction principale : get_procedural_material(preset_id)
- Gestion automatique du cache (évite les doublons)
"""

import bpy
from functools import partial
from . import brick_red_ultimate

# ✅ FIX: Chaque preset a maintenant sa propre palette de couleurs
# (avant: tous les presets produisaient des briques rouges!)
# Palette = 5 nuances RGBA du plus foncé au plus clair
PRESET_PALETTES = {
    'BRICK_RED': [  # Rouge traditionnel
        (0.38, 0.10, 0.07, 1.0),
        (0.52, 0.15, 0.10, 1.0),
        (0.61, 0.19, 0.13, 1.0),
        (0.68, 0.24, 0.17, 1.0),
        (0.74, 0.30, 0.21, 1.0),
    ],
    'BRICK_RED_DARK': [  # Rouge foncé
        (0.18, 0.05, 0.04, 1.0),
        (0.26, 0.07, 0.05, 1.0),
        (0.33, 0.09, 0.07, 1.0),
        (0.40, 0.12, 0.09, 1.0),
        (0.47, 0.15, 0.11, 1.0),
    ],
    'BRICK_ORANGE': [  # Orangé / terre cuite
        (0.50, 0.20, 0.07, 1.0),
        (0.62, 0.27, 0.09, 1.0),
        (0.70, 0.32, 0.11, 1.0),
        (0.78, 0.38, 0.14, 1.0),
        (0.85, 0.45, 0.18, 1.0),
    ],
    'BRICK_BROWN': [  # Brun / chocolat
        (0.16, 0.10, 0.06, 1.0),
        (0.23, 0.14, 0.08, 1.0),
        (0.30, 0.18, 0.11, 1.0),
        (0.36, 0.22, 0.14, 1.0),
        (0.43, 0.28, 0.17, 1.0),
    ],
    'BRICK_YELLOW': [  # Jaune (London stock)
        (0.48, 0.38, 0.20, 1.0),
        (0.58, 0.48, 0.27, 1.0),
        (0.67, 0.56, 0.33, 1.0),
        (0.75, 0.64, 0.40, 1.0),
        (0.83, 0.72, 0.47, 1.0),
    ],
    'BRICK_GREY': [  # Gris moderne
        (0.22, 0.22, 0.23, 1.0),
        (0.32, 0.32, 0.33, 1.0),
        (0.42, 0.42, 0.43, 1.0),
        (0.52, 0.52, 0.52, 1.0),
        (0.62, 0.62, 0.61, 1.0),
    ],
}

# Mapping preset_id -> fonction de création (même générateur, palette différente)
PRESET_FUNCTIONS = {
    preset_id: partial(brick_red_ultimate.create_brick_red_ultimate, base_colors=palette)
    for preset_id, palette in PRESET_PALETTES.items()
}


def get_procedural_material(preset_id):
    """Récupère ou crée un matériau procédural selon le preset_id
    
    Gère automatiquement le cache : si le matériau existe déjà dans bpy.data.materials,
    il est réutilisé. Sinon, il est créé.
    
    Args:
        preset_id (str): ID du preset (ex: 'BRICK_RED', 'BRICK_ORANGE')
        
    Returns:
        bpy.types.Material: Le matériau créé ou récupéré du cache
        
    Raises:
        ValueError: Si le preset_id n'existe pas
    """
    
    if preset_id not in PRESET_FUNCTIONS:
        # ✅ FIX: Fallback gracieux au lieu de ValueError — les IDs 'PBR_*'
        # (scannés sur disque) et les IDs inconnus retombent sur BRICK_RED
        # au lieu de faire planter la génération
        print(f"[House] ⚠️ Preset '{preset_id}' inconnu → fallback BRICK_RED")
        preset_id = 'BRICK_RED'
    
    # Nom du matériau dans Blender
    material_name = f"Brick_{preset_id}_Ultimate"
    
    # Vérifier si le matériau existe déjà
    if material_name in bpy.data.materials:
        print(f"[House] ♻️ Matériau {material_name} déjà existant (cache)")
        return bpy.data.materials[material_name]
    
    # Créer le matériau
    print(f"[House] 🎨 Création du matériau {preset_id}...")
    create_func = PRESET_FUNCTIONS[preset_id]
    material = create_func()
    
    # Renommer pour le cache
    material.name = material_name
    
    print(f"[House] ✅ Matériau {material_name} créé avec succès")
    return material


def list_available_presets():
    """Liste tous les presets procéduraux disponibles
    
    Returns:
        list: Liste des IDs de presets disponibles
    """
    return list(PRESET_FUNCTIONS.keys())


def clear_material_cache():
    """Supprime tous les matériaux procéduraux du cache
    
    Utile pour forcer la régénération des matériaux.
    """
    count = 0
    for preset_id in PRESET_FUNCTIONS.keys():
        material_name = f"Brick_{preset_id}_Ultimate"
        if material_name in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[material_name])
            count += 1
    
    print(f"[House] 🗑️ {count} matériau(x) supprimé(s) du cache")


# Pas de classes à enregistrer
classes = []

def register():
    """Enregistrement du module presets"""
    print(f"[House] Module Presets chargé - {len(PRESET_FUNCTIONS)} preset(s) disponible(s)")
    for preset_id in PRESET_FUNCTIONS.keys():
        print(f"[House]   - {preset_id}")


def unregister():
    """Désenregistrement du module presets"""
    pass