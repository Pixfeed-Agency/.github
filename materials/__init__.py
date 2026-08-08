# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Materials Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""Module de gestion des matériaux pour House Generator

Architecture:
- brick_geometry.py : Génération de la géométrie 3D des murs + matériaux
- pbr_scanner.py : Scan automatique des textures PBR
- presets/ : Matériaux procéduraux modulaires (1 fichier = 1 preset)

✅ Note: brick.py a été supprimé — c'était un doublon périmé de
brick_geometry.py, jamais appelé, avec des imports cassés
(from .materials import brick) et des API Blender dépréciées.
"""

from . import brick_geometry
from . import brick_geonodes
from . import pbr_scanner
from . import presets

# Liste des modules de matériaux
__all__ = ['brick_geometry', 'brick_geonodes', 'pbr_scanner', 'presets']


def register():
    """Enregistrement du module materials"""
    # Enregistrer le module presets
    presets.register()

    print("[House] Module Materials chargé")
    print("[House]   - brick_geometry.py (géométrie 3D + matériaux)")
    print("[House]   - pbr_scanner.py (scan automatique textures PBR)")
    print("[House]   - presets/ (matériaux procéduraux modulaires)")


def unregister():
    """Désenregistrement du module materials"""
    # Désenregistrer le module presets
    presets.unregister()
    
    print("[House] Module Materials déchargé")