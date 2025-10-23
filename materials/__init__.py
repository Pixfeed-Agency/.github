# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Materials Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""Module de gestion des matériaux pour House Generator

Architecture:
- brick.py : Logique de création des matériaux (orchestre presets et PBR)
- brick_geometry.py : Génération de la géométrie 3D des murs
- pbr_scanner.py : Scan automatique des textures PBR
- presets/ : Matériaux procéduraux modulaires (1 fichier = 1 preset)
"""

from . import brick
from . import brick_geometry
from . import pbr_scanner
from . import presets

# Liste des modules de matériaux
__all__ = ['brick', 'brick_geometry', 'pbr_scanner', 'presets']


def register():
    """Enregistrement du module materials"""
    # Enregistrer le module presets
    presets.register()
    
    print("[House] Module Materials chargé")
    print("[House]   - brick.py (logique matériaux)")
    print("[House]   - brick_geometry.py (géométrie 3D)")
    print("[House]   - pbr_scanner.py (scan automatique textures PBR)")
    print("[House]   - presets/ (matériaux procéduraux modulaires)")


def unregister():
    """Désenregistrement du module materials"""
    # Désenregistrer le module presets
    presets.unregister()
    
    print("[House] Module Materials déchargé")