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
from . import brick_red_ultimate

# Mapping preset_id -> fonction de création
PRESET_FUNCTIONS = {
    'BRICK_RED': brick_red_ultimate.create_brick_red_ultimate,
    # Presets par défaut pour les autres couleurs (temporaire)
    'BRICK_RED_DARK': brick_red_ultimate.create_brick_red_ultimate,  # Temporaire
    'BRICK_ORANGE': brick_red_ultimate.create_brick_red_ultimate,     # Temporaire
    'BRICK_BROWN': brick_red_ultimate.create_brick_red_ultimate,      # Temporaire
    'BRICK_YELLOW': brick_red_ultimate.create_brick_red_ultimate,     # Temporaire
    'BRICK_GREY': brick_red_ultimate.create_brick_red_ultimate,       # Temporaire
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
        print(f"[House] ⚠️ Preset '{preset_id}' non trouvé dans PRESET_FUNCTIONS")
        raise ValueError(f"Preset inconnu : {preset_id}")
    
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