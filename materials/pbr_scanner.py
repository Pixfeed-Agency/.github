# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - PBR Texture Scanner Module
#  Copyright (C) 2025 mvaertan
#
#  Système de scan automatique des textures PBR dans materials/textures/
#  Détecte automatiquement tous les dossiers et génère les presets disponibles
#
#  ✅ CORRIGÉ - Protection contre l'erreur '_RestrictData' lors du register
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import os


def get_brick_preset_items(self, context):
    """Fonction callback pour générer dynamiquement les items de l'EnumProperty
    
    Cette fonction est appelée par Blender chaque fois que le menu déroulant est ouvert.
    Elle combine:
    - Presets procéduraux hardcodés (BRICK_RED, BRICK_ORANGE, etc.)
    - Presets PBR scannés automatiquement depuis materials/textures/
    
    ⚠️ IMPORTANT: Cette fonction peut être appelée pendant register/unregister
    quand bpy.data n'est pas encore disponible. On doit donc gérer ce cas.
    
    Returns:
        list: Liste de tuples (id, name, description, icon, index) pour EnumProperty
    """
    
    # ============================================================
    # 🛡️ PROTECTION: Vérifier que bpy.data est accessible
    # ============================================================
    # Pendant le register/unregister, bpy.data est de type '_RestrictData'
    # et ne permet pas d'accéder aux collections (materials, objects, etc.)
    # On teste donc si bpy.data est disponible avant de scanner les textures
    
    try:
        # Test rapide pour voir si bpy.data est disponible
        _ = bpy.data.filepath
    except AttributeError:
        # bpy.data n'est pas encore disponible (phase de register/unregister)
        # On retourne uniquement les presets procéduraux de base
        print("[HousePBR] ⚠️ bpy.data non disponible, presets PBR désactivés temporairement")
        return [
            ('BRICK_RED', "🧱 Briques rouges", "Briques rouges traditionnelles (shader procédural)", 'MATERIAL', 0),
            ('BRICK_RED_DARK', "🧱 Briques rouges foncées", "Briques rouges sombres (shader procédural)", 'MATERIAL', 1),
            ('BRICK_ORANGE', "🧱 Briques orangées", "Briques orangées/terre cuite (shader procédural)", 'MATERIAL', 2),
            ('BRICK_BROWN', "🧱 Briques brunes", "Briques brunes/chocolat (shader procédural)", 'MATERIAL', 3),
            ('BRICK_YELLOW', "🧱 Briques jaunes", "Briques jaunes type London (shader procédural)", 'MATERIAL', 4),
            ('BRICK_GREY', "🧱 Briques grises", "Briques grises contemporaines (shader procédural)", 'MATERIAL', 5),
        ]
    
    # ============================================================
    # PRESETS PROCÉDURAUX (toujours disponibles, ne nécessitent pas de textures)
    # ============================================================
    procedural_presets = [
        ('BRICK_RED', "🧱 Briques rouges", "Briques rouges traditionnelles (shader procédural)", 'MATERIAL', 0),
        ('BRICK_RED_DARK', "🧱 Briques rouges foncées", "Briques rouges sombres (shader procédural)", 'MATERIAL', 1),
        ('BRICK_ORANGE', "🧱 Briques orangées", "Briques orangées/terre cuite (shader procédural)", 'MATERIAL', 2),
        ('BRICK_BROWN', "🧱 Briques brunes", "Briques brunes/chocolat (shader procédural)", 'MATERIAL', 3),
        ('BRICK_YELLOW', "🧱 Briques jaunes", "Briques jaunes type London (shader procédural)", 'MATERIAL', 4),
        ('BRICK_GREY', "🧱 Briques grises", "Briques grises contemporaines (shader procédural)", 'MATERIAL', 5),
    ]
    
    # ============================================================
    # PRESETS PBR (scannés dynamiquement depuis materials/textures/)
    # ============================================================
    pbr_presets = []
    
    try:
        # Trouver le module materials
        import sys
        materials_dir = None
        
        for module_name in sys.modules:
            if 'materials' in module_name:
                module = sys.modules[module_name]
                if hasattr(module, '__file__') and module.__file__:
                    potential_dir = os.path.dirname(module.__file__)
                    # Vérifier que c'est bien le bon dossier materials
                    if os.path.basename(potential_dir) == 'materials':
                        materials_dir = potential_dir
                        break
        
        if materials_dir:
            textures_dir = os.path.join(materials_dir, "textures")
            
            if os.path.exists(textures_dir):
                # Lister tous les sous-dossiers
                folders = [f for f in os.listdir(textures_dir) 
                          if os.path.isdir(os.path.join(textures_dir, f))]
                
                for idx, folder_name in enumerate(sorted(folders)):
                    folder_path = os.path.join(textures_dir, folder_name)
                    
                    try:
                        files = os.listdir(folder_path)
                        
                        # Vérifier si c'est un preset PBR valide (doit avoir au moins BaseColor)
                        has_base_color = any('basecolor' in f.lower() or 'albedo' in f.lower() 
                                            for f in files if f.endswith(('.jpg', '.png', '.jpeg', '.tga', '.exr')))
                        
                        if has_base_color:
                            # Créer l'ID du preset
                            preset_id = f"PBR_{folder_name.upper()}"
                            
                            # Nom lisible avec emoji
                            preset_name = f"🎨 {folder_name.replace('_', ' ').title()} (PBR)"
                            
                            # Compter les textures
                            num_textures = len([f for f in files if f.endswith(('.jpg', '.png', '.jpeg', '.tga', '.exr'))])
                            preset_desc = f"Textures PBR photo-réalistes - {num_textures} maps disponibles"
                            
                            pbr_presets.append((
                                preset_id,
                                preset_name,
                                preset_desc,
                                'TEXTURE',
                                len(procedural_presets) + idx
                            ))
                    
                    except Exception as e:
                        # Ignorer les dossiers problématiques
                        pass
    
    except Exception as e:
        # En cas d'erreur, on continue sans les presets PBR
        print(f"[HousePBR] ⚠️ Impossible de scanner les textures PBR: {e}")
    
    # Combiner les deux listes
    all_presets = procedural_presets + pbr_presets
    
    # Debug si des presets PBR ont été trouvés
    if len(pbr_presets) > 0:
        print(f"[HousePBR] ✅ {len(pbr_presets)} preset(s) PBR détecté(s)")
        for preset in pbr_presets:
            print(f"[HousePBR]   - {preset[0]}: {preset[1]}")
    
    return all_presets


def find_texture_files(preset_id):
    """Trouve automatiquement tous les fichiers de texture pour un preset PBR
    
    Cette fonction scanne le dossier materials/textures/[nom_preset]/ et 
    retourne un dictionnaire avec les chemins de toutes les textures trouvées.
    
    Args:
        preset_id (str): ID du preset (ex: 'PBR_BRICK_WORN')
        
    Returns:
        dict: Dictionnaire {type_texture: chemin_complet}
              Types possibles: 'basecolor', 'normal', 'roughness', 'bump', 'cavity', 
                              'specular', 'gloss', 'metallic', 'displacement'
    """
    
    # Si ce n'est pas un preset PBR, retourner vide
    if not preset_id.startswith('PBR_'):
        return {}
    
    # Extraire le nom du dossier depuis l'ID
    # Ex: 'PBR_BRICK_WORN' -> 'brick_worn'
    folder_name = preset_id[4:].lower()
    
    # Trouver le module materials
    import sys
    materials_dir = None
    
    for module_name in sys.modules:
        if 'materials' in module_name:
            module = sys.modules[module_name]
            if hasattr(module, '__file__') and module.__file__:
                potential_dir = os.path.dirname(module.__file__)
                if os.path.basename(potential_dir) == 'materials':
                    materials_dir = potential_dir
                    break
    
    if not materials_dir:
        print(f"[HousePBR] ⚠️ Module materials introuvable")
        return {}
    
    # Chemin vers le dossier de textures
    texture_folder = os.path.join(materials_dir, "textures", folder_name)
    
    if not os.path.exists(texture_folder):
        print(f"[HousePBR] ⚠️ Dossier de textures introuvable: {texture_folder}")
        return {}
    
    # Scanner les fichiers
    try:
        files = os.listdir(texture_folder)
    except Exception as e:
        print(f"[HousePBR] ❌ Erreur lecture dossier: {e}")
        return {}
    
    texture_paths = {}
    
    # Patterns de recherche pour chaque type de texture
    # Chaque type a plusieurs noms possibles
    texture_patterns = {
        'basecolor': ['basecolor', 'albedo', 'diffuse', 'color', 'base'],
        'normal': ['normal', 'norm'],
        'roughness': ['roughness', 'rough'],
        'bump': ['bump', 'height'],
        'cavity': ['cavity', 'ao', 'ambientocclusion', 'ambient'],
        'specular': ['specular', 'spec'],
        'gloss': ['gloss', 'glossiness'],
        'metallic': ['metallic', 'metalness', 'metal'],
        'displacement': ['displacement', 'displace', 'disp'],
    }
    
    # Pour chaque fichier du dossier
    for file in files:
        # Ignorer les fichiers qui ne sont pas des images
        if not file.endswith(('.jpg', '.png', '.jpeg', '.tga', '.exr', '.tif', '.tiff')):
            continue
        
        file_lower = file.lower()
        
        # Essayer de détecter le type de texture
        for tex_type, patterns in texture_patterns.items():
            # Si le type est déjà trouvé, passer au suivant
            if tex_type in texture_paths:
                continue
            
            # Vérifier si un des patterns correspond
            for pattern in patterns:
                if pattern in file_lower:
                    texture_paths[tex_type] = os.path.join(texture_folder, file)
                    break
    
    # Log ce qui a été trouvé
    if texture_paths:
        print(f"[HousePBR] Textures trouvées pour {preset_id}:")
        for tex_type, path in texture_paths.items():
            print(f"[HousePBR]   ✓ {tex_type}: {os.path.basename(path)}")
    
    return texture_paths