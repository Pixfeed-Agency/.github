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
    "version": (1, 9, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > House",
    "description": "Automatic and manual house generation with floor plans support",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

import bpy

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

    # ✅ FIX: Suppression du bloc de rechargement mort ('"bpy" in locals()'
    # n'était jamais vrai dans register()) et de l'import inutilisé
    # PointerProperty.

    # Enregistrer les modules qui ont leur propre register()
    preferences.register()
    properties.register()
    materials.register()
    ui_panels.register()
    utils.register()

    # Collecter et enregistrer les classes des opérateurs
    register_classes()

    # ✅ FIX: Message final honnête — avant, un échec d'enregistrement
    # affichait quand même "chargée avec succès"
    failures = []
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            failures.append(cls.__name__)
            print(f"[House] Erreur lors de l'enregistrement de {cls}: {e}")

    if failures:
        print(f"[House] ⚠️ Extension chargée avec {len(failures)} erreur(s): {', '.join(failures)}")
    else:
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