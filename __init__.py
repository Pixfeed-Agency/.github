# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Automatic and Manual House Generation for Blender
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "House",
    "author": "mvaertan",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > House",
    "description": "Automatic and manual house generation with floor plans support",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

import bpy
from bpy.props import PointerProperty

# ✅ BONNES PRATIQUES BLENDER 4.2 : Imports au niveau du module
from . import (
    preferences,
    properties,
    materials,
    ui_panels,
    operators_auto,
    operators_manual,
    utils,
)

# Liste des modules à recharger (pour le développement)
modules = [
    preferences,
    properties,
    materials,
    ui_panels,
    operators_auto,
    operators_manual,
    utils,
]

# Classes à enregistrer
classes = []

def register_classes():
    """Collecte les classes des modules QUI N'ONT PAS leur propre register()"""
    global classes
    classes.clear()
    
    # SEULEMENT les opérateurs (operators_auto, operators_manual)
    # Les autres modules (properties, ui_panels, etc.) ont leur propre register()
    for module in [operators_auto, operators_manual]:
        if hasattr(module, 'classes'):
            classes.extend(module.classes)

def register():
    """Enregistrement de l'extension"""
    
    # Recharger les modules en mode développement
    if "bpy" in locals():
        import importlib
        for module in modules:
            importlib.reload(module)
    
    # Enregistrer les modules qui ont leur propre register()
    preferences.register()
    properties.register()
    materials.register()
    ui_panels.register()
    utils.register()
    
    # Collecter et enregistrer les classes des opérateurs
    register_classes()
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"[House] Erreur lors de l'enregistrement de {cls}: {e}")
    
    print("[House] ✅ Extension chargée avec succès!")

def unregister():
    """Désenregistement de l'extension"""
    
    # Désenregistrer les classes dans l'ordre inverse
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"[House] Erreur lors du désenregistrement de {cls}: {e}")
    
    # Désenregistrer les modules dans l'ordre inverse
    utils.unregister()
    ui_panels.unregister()
    materials.unregister()
    properties.unregister()
    preferences.unregister()
    
    print("[House] Extension déchargée!")

if __name__ == "__main__":
    register()