# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Brick Geometry Generator (ULTIMATE - PBR Textures 4K + UV Fix)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math
import random
import os

# ✅ AJOUT: Import du scanner PBR
from . import pbr_scanner
from . import presets as material_presets  # ✅ CORRECTION: Presets procéduraux (on est déjà dans materials)


# ============================================================
# CONFIGURATION DES BRIQUES
# ============================================================

# Dimensions standard d'une brique européenne (en mètres)
BRICK_LENGTH = 0.22      # 22cm
BRICK_HEIGHT = 0.065     # 6.5cm
BRICK_DEPTH = 0.10       # 10cm (épaisseur du mur)

# Espacement mortier
MORTAR_GAP = 0.012       # 12mm entre les briques (épaisseur des joints)
MORTAR_THICKNESS = 0.006 # 6mm d'épaisseur de mortier de chaque côté

# ✅ FIX SHED ROOF: Le toit est une DALLE épaisse. Sa face inférieure est
# ROOF_THICKNESS_PITCHED plus bas que sa face supérieure. Les briques doivent
# s'arrêter SOUS la face inférieure, sinon elles transpercent la dalle!
ROOF_THICKNESS_PITCHED = 0.15  # Doit correspondre à operators_auto.ROOF_THICKNESS_PITCHED
ROOF_CLEARANCE = 0.02          # Gap de sécurité sous la face inférieure du toit
ROOF_GAP = ROOF_THICKNESS_PITCHED + ROOF_CLEARANCE  # Marge totale sous la ligne de toit

# ✅ FIX: Constante des linteaux (sa définition avait disparu lors de la
# réécriture des linteaux en soldats → NameError à la génération!)
LINTEL_OVERHANG = 0.15  # Appui du linteau de chaque côté de l'ouverture
# ============================================================
# GÉNÉRATION DES MURS DE LA MAISON EN BRIQUES (OPTIMISÉ)
# ============================================================

def generate_house_walls_bricks(
    house_width,
    house_length,
    total_height,
    collection,
    quality='MEDIUM',
    openings=None,
    brick_material_mode='PRESET',
    brick_color=None,
    brick_preset='BRICK_RED',
    custom_material=None,
    roof_type='GABLE',
    roof_pitch=35.0,
    mortar_color=None,  # ✅ NOUVEAU: Couleur personnalisable du mortier
    bonding_pattern='RUNNING'  # ✅ NOUVEAU: Pattern d'appareillage des briques
):
    """Génère les 4 murs extérieurs d'une maison en briques 3D avec instancing

    Args:
        house_width (float): Largeur de la maison (axe X)
        house_length (float): Longueur de la maison (axe Y)
        total_height (float): Hauteur totale des murs (tous les étages)
        collection: Collection Blender où ajouter les objets
        quality (str): 'LOW', 'MEDIUM', 'HIGH'
        openings (list): Liste de dictionnaires définissant les ouvertures
        brick_material_mode (str): 'COLOR', 'PRESET', 'CUSTOM'
        brick_color (tuple): Couleur RGB/RGBA pour mode COLOR
        brick_preset (str): Type de preset pour mode PRESET
        custom_material: Matériau custom pour mode CUSTOM
        roof_type (str): Type de toit ('GABLE', 'SHED', etc.)
        roof_pitch (float): Pente du toit en degrés

    Returns:
        tuple: (liste des objets murs, hauteur réelle des murs en m)
    """

    print("\n" + "="*70)
    print("[BrickGeometry] GÉNÉRATION MAISON EN BRIQUES (VERSION ULTIMATE)")
    print("="*70)
    print(f"[BrickGeometry] Dimensions: {house_width}m x {house_length}m x {total_height}m")
    print(f"[BrickGeometry] Qualité: {quality}")
    print(f"[BrickGeometry] Mode matériau: {brick_material_mode}")
    print(f"[BrickGeometry] Type de toit: {roof_type}")

    # ✅ FIX: TOUJOURS utiliser l'instancing, pour toutes les qualités.
    # La brique maître supporte déjà les 3 niveaux (LOW/MEDIUM/HIGH:
    # chanfreins + variations), et l'ancien chemin "géométrie complète"
    # cumulait plusieurs bugs (dalle de mortier bouchant les fenêtres,
    # couleur mortier et pattern d'appareillage ignorés, murs hors
    # emprise). Il est conservé ci-dessous uniquement pour référence.
    print(f"[BrickGeometry] Mode: INSTANCING (qualité {quality})")
    return generate_walls_with_instancing(
        house_width, house_length, total_height, collection, quality, openings,
        brick_material_mode, brick_color, brick_preset, custom_material,
        roof_type, roof_pitch, mortar_color, bonding_pattern
    )


def create_brick_master(collection, quality, brick_material_mode='PRESET',
                        brick_color=None, brick_preset='BRICK_RED',
                        custom_material=None, mortar_color=None):
    """✅ REFACTOR: Crée la brique maître avec ses 2 matériaux (partagé
    entre le moteur instancing et le moteur Geometry Nodes)

    Slot 0 = Matériau brique, Slot 1 = Matériau mortier
    """
    print("\n[BrickGeometry] Création de la brique maître...")

    brick_master = create_single_brick_mesh(quality)
    brick_master.name = "Brick_Master"

    # IMPORTANT : Linker AVANT de cacher
    collection.objects.link(brick_master)
    # ✅ FIX: hide_viewport (niveau datablock) au lieu de hide_set qui lève
    # RuntimeError si la collection n'est pas dans le view layer actif
    brick_master.hide_viewport = True
    brick_master.hide_render = True

    # Obtenir le matériau brique
    if brick_material_mode == 'COLOR':
        brick_mat = create_brick_material_solid_color(brick_color)
    elif brick_material_mode == 'PRESET':
        brick_mat = create_brick_material_preset(brick_preset)
    elif brick_material_mode == 'CUSTOM' and custom_material:
        brick_mat = custom_material
    else:
        # Fallback
        brick_mat = create_brick_material_preset('BRICK_RED')

    # Obtenir le matériau mortier avec couleur personnalisable
    mortar_mat = create_mortar_material(color=mortar_color)

    # Assigner les matériaux aux slots
    brick_master.data.materials.clear()
    brick_master.data.materials.append(brick_mat)   # Slot 0
    brick_master.data.materials.append(mortar_mat)  # Slot 1

    print(f"[BrickGeometry] ✓ Brique maître créée: {BRICK_LENGTH*100:.1f}cm x {BRICK_DEPTH*100:.1f}cm x {BRICK_HEIGHT*100:.1f}cm")
    print(f"[BrickGeometry] ✓ Matériau appliqué: {brick_material_mode}")

    return brick_master


def compute_real_wall_height(total_height):
    """✅ Hauteur RÉELLE des murs = nombre entier de rangées de briques.
    Helper UNIQUE (le calcul était dupliqué à 3 endroits)."""
    num_rows = int(total_height / (BRICK_HEIGHT + MORTAR_GAP))
    return num_rows * (BRICK_HEIGHT + MORTAR_GAP), num_rows


def compute_all_brick_positions(house_width, house_length, total_height,
                                openings=None, roof_type='GABLE',
                                roof_pitch=35.0, bonding_pattern='RUNNING'):
    """✅ REFACTOR: Calcule TOUTES les positions de briques (4 murs adaptés
    au toit + linteaux) — logique PARTAGÉE entre le moteur instancing et
    le moteur Geometry Nodes.

    Returns:
        list[(Vector, Euler)]: positions et rotations de chaque brique
    """
    # ✅ FIX COHÉRENCE: Le TOIT est posé à la hauteur RÉELLE des murs
    # (nombre entier de rangées, jusqu'à 7.6cm sous la hauteur demandée).
    # Toutes les collisions briques/toit doivent utiliser cette MÊME base,
    # sinon les briques du haut peuvent mordre la dalle de ~5cm.
    roof_base, _rows = compute_real_wall_height(total_height)

    # ✅ ROOF-AWARE: Calculer les hauteurs/formes des murs selon le toit
    # (math importé au niveau module)
    if roof_type == 'SHED':
        pitch_rad = math.radians(roof_pitch)
        roof_height = house_width * math.tan(pitch_rad)
        print(f"[BrickGeometry] ✓ SHED ROOF: hauteur additionnelle = {roof_height:.3f}m (pente {roof_pitch}°)")
    else:
        roof_height = 0

    # ✅ NOUVEAU: PIGNONS MAÇONNÉS sous toit GABLE — les murs pignons
    # suivent le triangle du toit (le faîtage court le long de la plus
    # grande dimension, même logique que _create_gable_roof)
    gable_ridge_along_y = house_length >= house_width
    if roof_type == 'GABLE':
        pitch_rad = math.radians(roof_pitch)
        if gable_ridge_along_y:
            gable_peak = (house_width / 2) * math.tan(pitch_rad)
            print(f"[BrickGeometry] ✓ GABLE: pignons avant/arrière maçonnés (faîtage +{gable_peak:.2f}m)")
        else:
            gable_peak = (house_length / 2) * math.tan(pitch_rad)
            print(f"[BrickGeometry] ✓ GABLE: pignons gauche/droit maçonnés (faîtage +{gable_peak:.2f}m)")
    else:
        gable_peak = 0

    # ✅ Pour les toits en pente, les murs SOUS LES ÉGOUTS s'arrêtent sous
    # la face inférieure de la dalle (sinon ils la transpercent aux égouts)
    pitched = roof_type in ('GABLE', 'HIP', 'GAMBREL', 'SHED')
    eave_capped_height = roof_base - (ROOF_GAP if pitched else 0)

    print("\n[BrickGeometry] Calcul des positions des briques...")

    # Calculer les positions de toutes les briques pour les 4 murs
    brick_positions = []

    # MUR AVANT (Y=0)
    print("[BrickGeometry] → Mur AVANT (façade)...")
    front_openings = [o for o in (openings or []) if o.get('wall') == 'front']
    if roof_type == 'SHED':
        # Hauteur variable selon X (rampant monopente)
        front_positions = calculate_brick_positions_for_wall_sloped(
            house_width, roof_base, roof_height,
            start_pos=Vector((0, 0, 0)),
            direction='X',
            openings=front_openings,
            bonding_pattern=bonding_pattern
        )
    elif roof_type == 'GABLE' and gable_ridge_along_y:
        # ✅ Pignon triangulaire maçonné
        front_positions = calculate_brick_positions_for_wall_gable(
            house_width, roof_base, gable_peak,
            start_pos=Vector((0, 0, 0)),
            direction='X',
            openings=front_openings,
            bonding_pattern=bonding_pattern
        )
    else:
        front_positions = calculate_brick_positions_for_wall(
            house_width, eave_capped_height,
            start_pos=Vector((0, 0, 0)),
            direction='X',
            openings=front_openings,
            bonding_pattern=bonding_pattern
        )
    brick_positions.extend(front_positions)
    print(f"[BrickGeometry]   {len(front_positions)} briques")

    # MUR ARRIÈRE (Y=length)
    # ✅ FIX: Décaler le départ vers l'INTÉRIEUR — à y=house_length, les
    # briques (épaisseur 11.2cm) débordaient hors de l'emprise de la maison
    print("[BrickGeometry] → Mur ARRIÈRE...")
    back_start = Vector((0, house_length - (BRICK_DEPTH + MORTAR_GAP), 0))
    back_openings = [o for o in (openings or []) if o.get('wall') == 'back']
    if roof_type == 'SHED':
        back_positions = calculate_brick_positions_for_wall_sloped(
            house_width, roof_base, roof_height,
            start_pos=back_start,
            direction='X',
            openings=back_openings,
            bonding_pattern=bonding_pattern
        )
    elif roof_type == 'GABLE' and gable_ridge_along_y:
        back_positions = calculate_brick_positions_for_wall_gable(
            house_width, roof_base, gable_peak,
            start_pos=back_start,
            direction='X',
            openings=back_openings,
            bonding_pattern=bonding_pattern
        )
    else:
        back_positions = calculate_brick_positions_for_wall(
            house_width, eave_capped_height,
            start_pos=back_start,
            direction='X',
            openings=back_openings,
            bonding_pattern=bonding_pattern
        )
    brick_positions.extend(back_positions)
    print(f"[BrickGeometry]   {len(back_positions)} briques")

    # MUR GAUCHE (X=0)
    print("[BrickGeometry] → Mur GAUCHE...")
    left_openings = [o for o in (openings or []) if o.get('wall') == 'left']
    # ✅ FIX: La rotation 90° projette l'épaisseur de la brique vers -X ;
    # partir de x=BRICK_DEPTH+MORTAR_GAP garde le mur DANS l'emprise
    left_start = Vector((BRICK_DEPTH + MORTAR_GAP, 0, 0))
    if roof_type == 'GABLE' and not gable_ridge_along_y:
        # ✅ Pignon maçonné côté gauche (faîtage le long de X)
        left_positions = calculate_brick_positions_for_wall_gable(
            house_length, roof_base, gable_peak,
            start_pos=left_start,
            direction='Y',
            openings=left_openings,
            bonding_pattern=bonding_pattern
        )
    else:
        # SHED: côté bas → sous la dalle; autres toits en pente: idem
        left_positions = calculate_brick_positions_for_wall(
            house_length, eave_capped_height,
            start_pos=left_start,
            direction='Y',
            openings=left_openings,
            bonding_pattern=bonding_pattern
        )
    brick_positions.extend(left_positions)
    print(f"[BrickGeometry]   {len(left_positions)} briques")

    # MUR DROIT (X=width)
    print("[BrickGeometry] → Mur DROIT...")
    right_openings = [o for o in (openings or []) if o.get('wall') == 'right']
    if roof_type == 'SHED':
        # Monopente: mur haut, sous la dalle
        right_wall_height = roof_base + roof_height - ROOF_GAP
        print(f"[BrickGeometry]   Hauteur adaptée (sous dalle toit): {right_wall_height:.3f}m")
        right_positions = calculate_brick_positions_for_wall(
            house_length, right_wall_height,
            start_pos=Vector((house_width, 0, 0)),
            direction='Y',
            openings=right_openings,
            bonding_pattern=bonding_pattern
        )
    elif roof_type == 'GABLE' and not gable_ridge_along_y:
        right_positions = calculate_brick_positions_for_wall_gable(
            house_length, roof_base, gable_peak,
            start_pos=Vector((house_width, 0, 0)),
            direction='Y',
            openings=right_openings,
            bonding_pattern=bonding_pattern
        )
    else:
        right_positions = calculate_brick_positions_for_wall(
            house_length, eave_capped_height,
            start_pos=Vector((house_width, 0, 0)),
            direction='Y',
            openings=right_openings,
            bonding_pattern=bonding_pattern
        )
    brick_positions.extend(right_positions)
    print(f"[BrickGeometry]   {len(right_positions)} briques")

    # ✅ NOUVEAU: Calculer les lintaux au-dessus des ouvertures
    print("\n[BrickGeometry] Calcul des lintaux (briques de support au-dessus des ouvertures)...")

    # Lintaux pour chaque mur (avec vérification collision toit)
    front_lintels = calculate_lintel_positions(openings, 'front', house_width, house_length, roof_type, roof_pitch, roof_base)
    brick_positions.extend(front_lintels)

    back_lintels = calculate_lintel_positions(openings, 'back', house_width, house_length, roof_type, roof_pitch, roof_base)
    brick_positions.extend(back_lintels)

    left_lintels = calculate_lintel_positions(openings, 'left', house_width, house_length, roof_type, roof_pitch, roof_base)
    brick_positions.extend(left_lintels)

    right_lintels = calculate_lintel_positions(openings, 'right', house_width, house_length, roof_type, roof_pitch, roof_base)
    brick_positions.extend(right_lintels)

    total_lintels = len(front_lintels) + len(back_lintels) + len(left_lintels) + len(right_lintels)
    print(f"[BrickGeometry] ✓ {total_lintels} briques de linteau ajoutées")

    print(f"\n[BrickGeometry] Total positions calculées: {len(brick_positions)}")

    return brick_positions


def generate_walls_with_instancing(
    house_width,
    house_length,
    total_height,
    collection,
    quality,
    openings=None,
    brick_material_mode='PRESET',
    brick_color=None,
    brick_preset='BRICK_RED',
    custom_material=None,
    roof_type='GABLE',
    roof_pitch=35.0,
    mortar_color=None,  # ✅ NOUVEAU: Couleur personnalisable du mortier
    bonding_pattern='RUNNING'  # ✅ NOUVEAU: Pattern d'appareillage
):
    """Génère les murs avec instancing pour optimiser les performances

    Murs adaptés au toit: rampants SHED, pignons GABLE maçonnés,
    murs capés sous les égouts pour tous les toits en pente.
    """

    walls = []

    brick_master = create_brick_master(
        collection, quality, brick_material_mode, brick_color,
        brick_preset, custom_material, mortar_color)

    # ✅ REFACTOR: Positions calculées par la logique partagée
    brick_positions = compute_all_brick_positions(
        house_width, house_length, total_height,
        openings=openings, roof_type=roof_type,
        roof_pitch=roof_pitch, bonding_pattern=bonding_pattern)

    
    # Créer toutes les instances
    print("\n[BrickGeometry] Création des instances de briques...")
    
    for i, (pos, rot) in enumerate(brick_positions):
        instance = bpy.data.objects.new(f"Brick_Instance_{i}", brick_master.data)
        instance.location = pos
        instance.rotation_euler = rot
        instance["house_part"] = "wall"
        collection.objects.link(instance)
        walls.append(instance)
        
        # Variation de couleur légère par instance (via custom properties)
        if quality == 'MEDIUM':
            instance["color_variation"] = random.uniform(0.9, 1.1)
    
    print(f"[BrickGeometry] ✓ {len(brick_positions)} instances créées")

    # Note: Le mortier est maintenant INTÉGRÉ à chaque brique, pas besoin de mortier séparé!

    # ✅ FIX : Calculer la hauteur RÉELLE des murs (pour positionner le toit correctement)
    real_wall_height, num_rows = compute_real_wall_height(total_height)

    print("\n" + "="*70)
    print("[BrickGeometry] ✅ MAISON EN BRIQUES GÉNÉRÉE AVEC SUCCÈS!")
    print("="*70)
    print(f"[BrickGeometry] Briques+mortier:   {len(brick_positions):,} instances")
    print(f"[BrickGeometry] Mortier:           INTÉGRÉ (chaque brique a son mortier)")
    print(f"[BrickGeometry] Total objets:      {len(walls) + 1:,}")
    print(f"[BrickGeometry] Murs:              4 (tous générés)")
    print(f"[BrickGeometry] Hauteur demandée:  {total_height:.3f}m")
    print(f"[BrickGeometry] Hauteur réelle:    {real_wall_height:.3f}m ({num_rows} rangées)")
    print(f"[BrickGeometry] Ouvertures:        {len(openings or [])} exclues")
    print(f"[BrickGeometry] Matériau brique:   {brick_material_mode}")
    print(f"[BrickGeometry] Matériau mortier:  Gris clair (automatique)")
    print("="*70 + "\n")

    return walls, real_wall_height


def generate_walls_full_geometry(
    house_width,
    house_length,
    total_height,
    collection,
    quality,
    openings=None,
    brick_material_mode='PRESET',
    brick_color=None,
    brick_preset='BRICK_RED',
    custom_material=None,
    roof_type='GABLE',
    roof_pitch=35.0
):
    """Génère les murs avec géométrie complète (HIGH quality)

    NOTE: Cette fonction utilise encore l'ancien système (briques + mortier séparés).
    Pour bénéficier du nouveau système (mortier intégré), utilisez quality='MEDIUM' ou 'LOW'.

    NOTE 2: Le support SHED roof n'est pas implémenté en mode HIGH quality.
    Utilisez MEDIUM ou LOW pour le shed roof avec murs adaptés.
    """

    if roof_type == 'SHED':
        print("[BrickGeometry] AVERTISSEMENT: SHED roof non supporté en qualité HIGH")
        print("[BrickGeometry] Utilisez qualité MEDIUM ou LOW pour murs adaptés")

    walls = []
    
    # === MUR AVANT (FAÇADE) ===
    print("[BrickGeometry] Mur avant (façade)...")
    wall_front_bricks, wall_front_mortar = generate_brick_wall(
        house_width, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'front']
    )
    wall_front_bricks.name = "Wall_Front_Bricks"
    wall_front_mortar.name = "Wall_Front_Mortar"
    
    wall_front_bricks.location = Vector((0, 0, 0))
    wall_front_mortar.location = Vector((0, 0, 0))
    wall_front_bricks.rotation_euler = Euler((0, 0, 0), 'XYZ')
    wall_front_mortar.rotation_euler = Euler((0, 0, 0), 'XYZ')
    
    # ✅ APPLIQUER LE MATÉRIAU
    apply_brick_material_to_object(
        wall_front_bricks, 
        brick_material_mode, 
        brick_color, 
        brick_preset, 
        custom_material
    )
    apply_mortar_material_to_object(wall_front_mortar)
    
    wall_front_bricks["house_part"] = "wall"
    wall_front_mortar["house_part"] = "wall"
    collection.objects.link(wall_front_bricks)
    collection.objects.link(wall_front_mortar)
    walls.extend([wall_front_bricks, wall_front_mortar])
    
    # === MUR ARRIÈRE ===
    print("[BrickGeometry] Mur arrière...")
    wall_back_bricks, wall_back_mortar = generate_brick_wall(
        house_width, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'back']
    )
    wall_back_bricks.name = "Wall_Back_Bricks"
    wall_back_mortar.name = "Wall_Back_Mortar"
    
    wall_back_bricks.location = Vector((0, house_length, 0))
    wall_back_mortar.location = Vector((0, house_length, 0))
    wall_back_bricks.rotation_euler = Euler((0, 0, 0), 'XYZ')
    wall_back_mortar.rotation_euler = Euler((0, 0, 0), 'XYZ')
    
    # ✅ APPLIQUER LE MATÉRIAU
    apply_brick_material_to_object(
        wall_back_bricks, 
        brick_material_mode, 
        brick_color, 
        brick_preset, 
        custom_material
    )
    apply_mortar_material_to_object(wall_back_mortar)
    
    wall_back_bricks["house_part"] = "wall"
    wall_back_mortar["house_part"] = "wall"
    collection.objects.link(wall_back_bricks)
    collection.objects.link(wall_back_mortar)
    walls.extend([wall_back_bricks, wall_back_mortar])
    
    # === MUR GAUCHE ===
    print("[BrickGeometry] Mur gauche...")
    wall_left_bricks, wall_left_mortar = generate_brick_wall(
        house_length, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'left']
    )
    wall_left_bricks.name = "Wall_Left_Bricks"
    wall_left_mortar.name = "Wall_Left_Mortar"
    
    wall_left_bricks.location = Vector((0, 0, 0))
    wall_left_mortar.location = Vector((0, 0, 0))
    wall_left_bricks.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    wall_left_mortar.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    
    # ✅ APPLIQUER LE MATÉRIAU
    apply_brick_material_to_object(
        wall_left_bricks, 
        brick_material_mode, 
        brick_color, 
        brick_preset, 
        custom_material
    )
    apply_mortar_material_to_object(wall_left_mortar)
    
    wall_left_bricks["house_part"] = "wall"
    wall_left_mortar["house_part"] = "wall"
    collection.objects.link(wall_left_bricks)
    collection.objects.link(wall_left_mortar)
    walls.extend([wall_left_bricks, wall_left_mortar])
    
    # === MUR DROIT ===
    print("[BrickGeometry] Mur droit...")
    wall_right_bricks, wall_right_mortar = generate_brick_wall(
        house_length, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'right']
    )
    wall_right_bricks.name = "Wall_Right_Bricks"
    wall_right_mortar.name = "Wall_Right_Mortar"
    
    wall_right_bricks.location = Vector((house_width, 0, 0))
    wall_right_mortar.location = Vector((house_width, 0, 0))
    wall_right_bricks.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    wall_right_mortar.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    
    # ✅ APPLIQUER LE MATÉRIAU
    apply_brick_material_to_object(
        wall_right_bricks, 
        brick_material_mode, 
        brick_color, 
        brick_preset, 
        custom_material
    )
    apply_mortar_material_to_object(wall_right_mortar)
    
    wall_right_bricks["house_part"] = "wall"
    wall_right_mortar["house_part"] = "wall"
    collection.objects.link(wall_right_bricks)
    collection.objects.link(wall_right_mortar)
    walls.extend([wall_right_bricks, wall_right_mortar])
    
    # Calculer statistiques
    total_bricks = calculate_brick_count(house_width, total_height) * 2 + \
                   calculate_brick_count(house_length, total_height) * 2

    # ✅ FIX: Calculer la hauteur RÉELLE des murs (pour positionner le toit correctement)
    num_rows = int(total_height / (BRICK_HEIGHT + MORTAR_GAP))
    real_wall_height = num_rows * (BRICK_HEIGHT + MORTAR_GAP)

    print(f"[BrickGeometry] ✅ Maison en briques créée!")
    print(f"[BrickGeometry]    Total briques: ~{total_bricks}")
    print(f"[BrickGeometry]    Objets créés: {len(walls)}")
    print(f"[BrickGeometry]    Ouvertures exclues: {len(openings or [])}")
    print(f"[BrickGeometry]    Matériau: {brick_material_mode}")
    print(f"[BrickGeometry]    Hauteur réelle: {real_wall_height:.3f}m ({num_rows} rangées)")

    return walls, real_wall_height


# ============================================================
# SYSTÈME DE MATÉRIAUX
# ============================================================

def apply_brick_material_to_object(obj, mode, color, preset, custom_mat):
    """Applique le matériau aux briques selon le mode choisi
    
    Args:
        obj: Objet Blender
        mode (str): 'COLOR', 'PRESET', 'CUSTOM'
        color (tuple): Couleur RGB/RGBA pour mode COLOR
        preset (str): Type de preset pour mode PRESET
        custom_mat: Matériau custom pour mode CUSTOM
    """
    
    if mode == 'COLOR':
        # Mode couleur unie
        mat = create_brick_material_solid_color(color)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        print(f"[BrickGeometry]   ✓ Matériau couleur unie appliqué")
        
    elif mode == 'PRESET':
        # Mode preset réaliste
        mat = create_brick_material_preset(preset)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        print(f"[BrickGeometry]   ✓ Matériau preset appliqué: {preset}")
        
    elif mode == 'CUSTOM':
        # Mode matériau custom
        if custom_mat:
            obj.data.materials.clear()
            obj.data.materials.append(custom_mat)
            print(f"[BrickGeometry]   ✓ Matériau custom appliqué: {custom_mat.name}")
        else:
            # Fallback sur preset si pas de custom
            mat = create_brick_material_preset('BRICK_RED')
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            print(f"[BrickGeometry]   ⚠ Pas de matériau custom, preset par défaut")


def create_brick_material_solid_color(color):
    """Crée un matériau brique couleur unie
    
    Args:
        color (tuple): RGB (3) ou RGBA (4)
        
    Returns:
        bpy.types.Material: Matériau créé
    """
    
    # ✅ CORRECTION : Gérer None, RGB (3) et RGBA (4)
    if color is None:
        rgba_color = (0.65, 0.25, 0.15, 1.0)  # Fallback rouge classique
    elif len(color) == 3:
        rgba_color = (*color, 1.0)
    elif len(color) == 4:
        rgba_color = tuple(color)  # Déjà RGBA, convertir en tuple standard
    else:
        rgba_color = (0.65, 0.25, 0.15, 1.0)  # Fallback rouge classique
    
    mat_name = f"Brick_SolidColor_{int(rgba_color[0]*255)}_{int(rgba_color[1]*255)}_{int(rgba_color[2]*255)}"
    
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    # Principled BSDF
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (0, 0)
    principled.inputs["Base Color"].default_value = rgba_color  # ✅ CORRIGÉ
    principled.inputs["Roughness"].default_value = 0.8
    
    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (300, 0)
    
    mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    
    return mat


# ============================================================
# ✅ NOUVEAU : MATÉRIAU PBR AVEC TEXTURES 4K
# ============================================================



def create_brick_material_pbr_textured(preset_name='BRICK_WORN_PBR'):
    """Crée un matériau brique avec textures PBR (SYSTÈME DYNAMIQUE)
    
    ✅ NOUVEAU: Utilise pbr_scanner.find_texture_files() pour trouver automatiquement
    les textures au lieu de chemins hardcodés
    
    Args:
        preset_name (str): ID du preset (ex: 'PBR_BRICK_WORN')
        
    Returns:
        bpy.types.Material: Matériau avec textures PBR
    """
    
    mat_name = f"Brick_PBR_{preset_name}"
    
    # Vérifier si existe déjà
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    
    print(f"\n[BrickPBR] Création matériau PBR: {preset_name}")
    
    # ✅ NOUVEAU: Utiliser find_texture_files() au lieu de chemins hardcodés
    texture_files = pbr_scanner.find_texture_files(preset_name)
    
    if not texture_files:
        print(f"[BrickPBR] ⚠ Aucune texture trouvée, fallback preset procédural")
        return create_brick_material_preset('BRICK_RED')
    
    print(f"[BrickPBR] {len(texture_files)} texture(s) trouvée(s)")
    
    # Créer le matériau
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    # ============================================================
    # PRINCIPLED BSDF
    # ============================================================
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (300, 300)
    
    # ============================================================
    # TEXTURE COORDINATE + MAPPING
    # ============================================================
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-1200, 0)
    
    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-1000, 0)
    
    mat.node_tree.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    
    # ============================================================
    # BASE COLOR (Albedo)
    # ============================================================
    if 'basecolor' in texture_files:
        tex_base = nodes.new(type='ShaderNodeTexImage')
        tex_base.location = (-600, 500)
        tex_base.label = "Base Color"
        tex_base.image = bpy.data.images.load(texture_files['basecolor'], check_existing=True)
        tex_base.image.colorspace_settings.name = 'sRGB'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_base.inputs["Vector"])
        print(f"[BrickPBR]   ✓ Base Color: {os.path.basename(texture_files['basecolor'])}")
    
    # ============================================================
    # ROUGHNESS
    # ============================================================
    if 'roughness' in texture_files:
        tex_rough = nodes.new(type='ShaderNodeTexImage')
        tex_rough.location = (-600, 200)
        tex_rough.label = "Roughness"
        tex_rough.image = bpy.data.images.load(texture_files['roughness'], check_existing=True)
        tex_rough.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_rough.inputs["Vector"])
        mat.node_tree.links.new(tex_rough.outputs["Color"], principled.inputs["Roughness"])
        print(f"[BrickPBR]   ✓ Roughness: {os.path.basename(texture_files['roughness'])}")
    elif 'gloss' in texture_files:
        # Si pas de roughness mais gloss, inverser
        tex_gloss = nodes.new(type='ShaderNodeTexImage')
        tex_gloss.location = (-600, 200)
        tex_gloss.label = "Gloss"
        tex_gloss.image = bpy.data.images.load(texture_files['gloss'], check_existing=True)
        tex_gloss.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_gloss.inputs["Vector"])
        
        invert = nodes.new(type='ShaderNodeInvert')
        invert.location = (-300, 200)
        mat.node_tree.links.new(tex_gloss.outputs["Color"], invert.inputs["Color"])
        mat.node_tree.links.new(invert.outputs["Color"], principled.inputs["Roughness"])
        print(f"[BrickPBR]   ✓ Gloss (inversé): {os.path.basename(texture_files['gloss'])}")
    
    # ============================================================
    # NORMAL MAP
    # ============================================================
    normal_map_node = None
    if 'normal' in texture_files:
        tex_normal = nodes.new(type='ShaderNodeTexImage')
        tex_normal.location = (-600, -100)
        tex_normal.label = "Normal"
        tex_normal.image = bpy.data.images.load(texture_files['normal'], check_existing=True)
        tex_normal.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_normal.inputs["Vector"])
        
        normal_map_node = nodes.new(type='ShaderNodeNormalMap')
        normal_map_node.location = (-200, -100)
        normal_map_node.inputs["Strength"].default_value = 1.0
        
        mat.node_tree.links.new(tex_normal.outputs["Color"], normal_map_node.inputs["Color"])
        mat.node_tree.links.new(normal_map_node.outputs["Normal"], principled.inputs["Normal"])
        print(f"[BrickPBR]   ✓ Normal: {os.path.basename(texture_files['normal'])}")
    
    # ============================================================
    # BUMP MAP
    # ============================================================
    if 'bump' in texture_files:
        tex_bump = nodes.new(type='ShaderNodeTexImage')
        tex_bump.location = (-600, -400)
        tex_bump.label = "Bump"
        tex_bump.image = bpy.data.images.load(texture_files['bump'], check_existing=True)
        tex_bump.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_bump.inputs["Vector"])
        
        bump_node = nodes.new(type='ShaderNodeBump')
        bump_node.location = (-200, -400)
        bump_node.inputs["Strength"].default_value = 0.3
        bump_node.inputs["Distance"].default_value = 0.001
        
        mat.node_tree.links.new(tex_bump.outputs["Color"], bump_node.inputs["Height"])
        
        # Combiner avec Normal si présent
        if normal_map_node:
            mat.node_tree.links.new(normal_map_node.outputs["Normal"], bump_node.inputs["Normal"])
            mat.node_tree.links.new(bump_node.outputs["Normal"], principled.inputs["Normal"])
        else:
            mat.node_tree.links.new(bump_node.outputs["Normal"], principled.inputs["Normal"])
        
        print(f"[BrickPBR]   ✓ Bump: {os.path.basename(texture_files['bump'])}")
    
    # ============================================================
    # CAVITY (Ambient Occlusion)
    # ============================================================
    if 'cavity' in texture_files and 'basecolor' in texture_files:
        tex_cavity = nodes.new(type='ShaderNodeTexImage')
        tex_cavity.location = (-900, 500)
        tex_cavity.label = "Cavity (AO)"
        tex_cavity.image = bpy.data.images.load(texture_files['cavity'], check_existing=True)
        tex_cavity.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_cavity.inputs["Vector"])
        
        # Mixer avec Base Color
        mix_ao = nodes.new(type='ShaderNodeMix')
        mix_ao.location = (-300, 500)
        mix_ao.data_type = 'RGBA'
        mix_ao.blend_type = 'MULTIPLY'
        mix_ao.inputs[0].default_value = 0.5
        
        mat.node_tree.links.new(tex_base.outputs["Color"], mix_ao.inputs[6])
        mat.node_tree.links.new(tex_cavity.outputs["Color"], mix_ao.inputs[7])
        mat.node_tree.links.new(mix_ao.outputs[2], principled.inputs["Base Color"])
        print(f"[BrickPBR]   ✓ Cavity: {os.path.basename(texture_files['cavity'])}")
    elif 'basecolor' in texture_files:
        # Pas d'AO, juste la base color
        mat.node_tree.links.new(tex_base.outputs["Color"], principled.inputs["Base Color"])
    
    # ============================================================
    # SPECULAR
    # ============================================================
    if 'specular' in texture_files:
        tex_spec = nodes.new(type='ShaderNodeTexImage')
        tex_spec.location = (-600, -700)
        tex_spec.label = "Specular"
        tex_spec.image = bpy.data.images.load(texture_files['specular'], check_existing=True)
        tex_spec.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_spec.inputs["Vector"])
        mat.node_tree.links.new(tex_spec.outputs["Color"], principled.inputs["Specular IOR Level"])
        print(f"[BrickPBR]   ✓ Specular: {os.path.basename(texture_files['specular'])}")
    
    # ============================================================
    # METALLIC
    # ============================================================
    if 'metallic' in texture_files:
        tex_metal = nodes.new(type='ShaderNodeTexImage')
        tex_metal.location = (-600, -1000)
        tex_metal.label = "Metallic"
        tex_metal.image = bpy.data.images.load(texture_files['metallic'], check_existing=True)
        tex_metal.image.colorspace_settings.name = 'Non-Color'
        mat.node_tree.links.new(mapping.outputs["Vector"], tex_metal.inputs["Vector"])
        mat.node_tree.links.new(tex_metal.outputs["Color"], principled.inputs["Metallic"])
        print(f"[BrickPBR]   ✓ Metallic: {os.path.basename(texture_files['metallic'])}")
    
    # ============================================================
    # OUTPUT
    # ============================================================
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (600, 300)
    
    mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    
    print(f"[BrickPBR] ✅ Matériau PBR créé: {mat_name}\n")
    
    return mat




def create_brick_material_preset(preset_type):
    """Crée un matériau brique selon le preset (UTILISE materials.presets)
    
    ✅ CORRECTION: Utilise le nouveau système modulaire materials/presets/
    au lieu de code hardcodé.
    
    Args:
        preset_type (str): ID du preset ('BRICK_RED', 'BRICK_ORANGE', etc.)
        
    Returns:
        bpy.types.Material: Matériau créé ou récupéré du cache
    """
    
    # Si c'est un preset PBR, utiliser la fonction PBR
    if preset_type.startswith('PBR_'):
        return create_brick_material_pbr_textured(preset_type)
    
    # Sinon, utiliser le système de presets procéduraux
    try:
        material = material_presets.get_procedural_material(preset_type)
        print(f"[BrickGeometry] ✅ Matériau preset '{preset_type}' chargé")
        return material
    except ValueError as e:
        print(f"[BrickGeometry] ⚠️  Preset '{preset_type}' inconnu: {e}")
        print(f"[BrickGeometry] → Fallback sur BRICK_RED")
        return material_presets.get_procedural_material('BRICK_RED')


def create_mortar_material(color=None):
    """Crée ou récupère le matériau mortier

    Args:
        color (tuple): Couleur RGB/RGBA optionnelle. Si None, utilise blanc cassé par défaut.

    Returns:
        bpy.types.Material: Matériau mortier
    """

    # Couleur par défaut: blanc cassé / crème clair (très contrasté avec briques)
    if color is None:
        color = (0.92, 0.92, 0.90, 1.0)
    elif len(color) == 3:
        color = (*color, 1.0)  # Ajouter alpha si RGB
    elif len(color) != 4:
        # ✅ FIX: Séquence invalide → fallback (évite un crash à l'assignation)
        color = (0.92, 0.92, 0.90, 1.0)

    mat_name = f"Mortar_Material_{int(color[0]*255)}_{int(color[1]*255)}_{int(color[2]*255)}"

    # Vérifier si déjà existant (cache)
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]

    # Créer nouveau matériau
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    # Principled BSDF
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (0, 0)
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = 0.9  # Très rugueux

    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (300, 0)

    mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return mat


def apply_mortar_material_to_object(obj):
    """Applique le matériau mortier à un objet (rétrocompatibilité)"""
    mat = create_mortar_material()
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ============================================================
# ✅ HELPER: Création d'une dalle de mortier
# ============================================================

def _add_mortar_slab(bm, x, y, z, width, depth, height):
    """Ajoute une dalle de mortier au bmesh

    Args:
        bm: BMesh
        x, y, z: Position du coin inférieur
        width, depth, height: Dimensions de la dalle

    Returns:
        list: Liste des faces créées (pour assignation material slot)
    """

    # 8 vertices pour un cube
    v1 = bm.verts.new((x, y, z))
    v2 = bm.verts.new((x + width, y, z))
    v3 = bm.verts.new((x + width, y + depth, z))
    v4 = bm.verts.new((x, y + depth, z))

    v5 = bm.verts.new((x, y, z + height))
    v6 = bm.verts.new((x + width, y, z + height))
    v7 = bm.verts.new((x + width, y + depth, z + height))
    v8 = bm.verts.new((x, y + depth, z + height))

    # 6 faces
    faces = []
    faces.append(bm.faces.new([v1, v2, v3, v4]))  # Bas
    faces.append(bm.faces.new([v5, v8, v7, v6]))  # Haut
    faces.append(bm.faces.new([v1, v5, v6, v2]))  # Face Y-
    faces.append(bm.faces.new([v2, v6, v7, v3]))  # Face X+
    faces.append(bm.faces.new([v3, v7, v8, v4]))  # Face Y+
    faces.append(bm.faces.new([v4, v8, v5, v1]))  # Face X-

    return faces


# ============================================================
# ✅ CRÉATION BRIQUE AVEC UV MAPPING + DÉTAILS
# ============================================================

def create_single_brick_mesh(quality='MEDIUM'):
    """Crée UNE brique avec son mortier intégré (approche architecturale réaliste)

    Architecture:
    - Chaque brique inclut SON mortier (cadre autour)
    - 2 material slots: 0=brique, 1=mortier
    - Dimensions totales incluent le mortier

    Args:
        quality (str): 'LOW', 'MEDIUM', 'HIGH'
        - LOW: Géométrie simple
        - MEDIUM: Chanfreins sur la brique
        - HIGH: Chanfreins + détails (frog, relief, faces bombées)

    Returns:
        bpy.types.Object: Objet brique+mortier avec 2 material slots
    """

    mesh = bpy.data.meshes.new("Brick_Master_Mesh")
    bm = bmesh.new()

    try:
        # ============================================================
        # ÉTAPE 1: CRÉER LA BRIQUE CENTRALE (sans mortier)
        # ============================================================

        print(f"[BrickGeometry]   → Création brique centrale...")

        # Créer un cube pour la brique
        bmesh.ops.create_cube(bm, size=1.0)

        # Mise à l'échelle aux dimensions de la brique (100%, pas de BRICK_SCALE)
        scale_matrix = Matrix.Diagonal((BRICK_LENGTH, BRICK_DEPTH, BRICK_HEIGHT, 1.0))
        bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)

        # ✅ FIX CRITIQUE: La brique doit être décalée de MORTAR_THICKNESS
        # pour s'insérer DANS son cadre de mortier. Sans ce décalage, la
        # brique recouvrait le mortier bas/gauche/avant (invisible) et
        # laissait un vide de 6mm côté haut/droit/arrière — d'où l'impression
        # que "le mortier a la couleur de la brique".
        center_offset = Vector((
            MORTAR_THICKNESS + BRICK_LENGTH/2,
            MORTAR_THICKNESS + BRICK_DEPTH/2,
            MORTAR_THICKNESS + BRICK_HEIGHT/2
        ))
        bmesh.ops.translate(bm, verts=bm.verts, vec=center_offset)
        
        # Marquer toutes les faces actuelles comme "brique" (material slot 0)
        brick_faces = list(bm.faces)

        # ============================================================
        # ÉTAPE 2: AJOUTER LE CADRE DE MORTIER AUTOUR
        # ============================================================

        print(f"[BrickGeometry]   → Ajout du cadre de mortier...")

        # Dimensions totales (brique + mortier)
        total_length = BRICK_LENGTH + MORTAR_GAP
        total_depth = BRICK_DEPTH + MORTAR_GAP
        total_height = BRICK_HEIGHT + MORTAR_GAP

        # Créer les 6 plans de mortier autour de la brique
        mortar_faces = []

        # MORTIER BAS (sous la brique)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=0, y=0, z=0,
            width=total_length, depth=total_depth, height=MORTAR_THICKNESS
        ))

        # MORTIER HAUT (au-dessus de la brique)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=0, y=0, z=BRICK_HEIGHT + MORTAR_THICKNESS,
            width=total_length, depth=total_depth, height=MORTAR_THICKNESS
        ))

        # MORTIER AVANT (face Y=0)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=0, y=0, z=MORTAR_THICKNESS,
            width=total_length, depth=MORTAR_THICKNESS, height=BRICK_HEIGHT
        ))

        # MORTIER ARRIÈRE (face Y=max)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=0, y=BRICK_DEPTH + MORTAR_THICKNESS, z=MORTAR_THICKNESS,
            width=total_length, depth=MORTAR_THICKNESS, height=BRICK_HEIGHT
        ))

        # MORTIER GAUCHE (face X=0)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=0, y=MORTAR_THICKNESS, z=MORTAR_THICKNESS,
            width=MORTAR_THICKNESS, depth=BRICK_DEPTH, height=BRICK_HEIGHT
        ))

        # MORTIER DROIT (face X=max)
        mortar_faces.extend(_add_mortar_slab(
            bm,
            x=BRICK_LENGTH + MORTAR_THICKNESS, y=MORTAR_THICKNESS, z=MORTAR_THICKNESS,
            width=MORTAR_THICKNESS, depth=BRICK_DEPTH, height=BRICK_HEIGHT
        ))

        print(f"[BrickGeometry]   ✓ {len(mortar_faces)} faces de mortier ajoutées")

        # ============================================================
        # ÉTAPE 3: DÉTAILS SELON QUALITÉ (appliqués seulement à la brique)
        # ============================================================

        vertex_count = len(bm.verts)

        if quality == 'LOW':
            # LOW: Géométrie simple, pas de détails
            print(f"[BrickGeometry]   ✓ LOW quality: {vertex_count} vertices (géométrie simple)")

        elif quality == 'MEDIUM':
            # MEDIUM: Chanfreins sur les arêtes de la brique uniquement
            bevel_amount = 0.001  # 1mm
            segments = 1

            # Sélectionner seulement les arêtes de la brique (pas du mortier)
            brick_edges = []
            for face in brick_faces:
                if face.is_valid:
                    for edge in face.edges:
                        if edge not in brick_edges:
                            brick_edges.append(edge)

            if brick_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=brick_edges,
                    offset=bevel_amount,
                    segments=segments,
                    profile=0.5,
                    affect='EDGES'
                )
                vertex_count = len(bm.verts)
                print(f"[BrickGeometry]   ✓ MEDIUM quality: {vertex_count} vertices (chanfreins {bevel_amount*1000:.1f}mm sur brique)")
        
        elif quality == 'HIGH':
            # HIGH: Chanfreins + Subdivision + détails (seulement sur la brique)

            # ========== Étape 1 : Chanfreins (brique seulement) ==========
            bevel_amount = 0.0015  # 1.5mm
            segments = 2

            # Sélectionner seulement les arêtes de la brique
            brick_edges = []
            for face in brick_faces:
                if face.is_valid:
                    for edge in face.edges:
                        if edge not in brick_edges:
                            brick_edges.append(edge)

            if brick_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=brick_edges,
                    offset=bevel_amount,
                    segments=segments,
                    profile=0.5,
                    affect='EDGES'
                )
            
            # ========== Étape 2 : Légères variations géométriques ==========
            # ✅ FIX: Ne déformer QUE les faces de la brique — déformer le
            # cadre de mortier cassait le pavage parfait entre instances
            # (fissures visibles entre briques voisines)
            brick_verts = {v for f in brick_faces if f.is_valid for v in f.verts}
            for vert in brick_verts:
                vert.co.x += random.uniform(-0.0005, 0.0005)
                vert.co.y += random.uniform(-0.0005, 0.0005)
                vert.co.z += random.uniform(-0.0003, 0.0003)

            vertex_count_final = len(bm.verts)
            print(f"[BrickGeometry]   ✓ HIGH quality: {vertex_count_final} vertices (chanfreins + variations)")
        
        # ============================================================
        # ✅ UV MAPPING (Box Projection - Optimal pour briques)
        # ============================================================
        print(f"[BrickGeometry]   → Création UV mapping...")
        
        # Créer UV layer
        uv_layer = bm.loops.layers.uv.verify()
        
        # Box Projection manuelle pour chaque face
        uv_count = 0
        
        # ✅ FIX: Normalisation SANS modulo — le "% 1.0" faisait retomber les
        # verts au bord exact (x = BRICK_LENGTH → u = 0.0 au lieu de 1.0),
        # écrasant les UV de chaque face en quads dégénérés (textures étalées)
        cell_l = BRICK_LENGTH + MORTAR_GAP
        cell_d = BRICK_DEPTH + MORTAR_GAP
        cell_h = BRICK_HEIGHT + MORTAR_GAP

        for face in bm.faces:
            # Déterminer l'orientation de la face via sa normale
            normal = face.normal

            for loop in face.loops:
                vert = loop.vert

                # Projection selon l'axe dominant de la normale
                if abs(normal.z) > 0.5:
                    # Face horizontale (haut/bas) → Projection XY
                    u = vert.co.x / cell_l
                    v = vert.co.y / cell_d

                elif abs(normal.x) > 0.5:
                    # Face perpendiculaire X (côtés gauche/droit) → Projection YZ
                    u = vert.co.y / cell_d
                    v = vert.co.z / cell_h

                else:
                    # Face perpendiculaire Y (avant/arrière) → Projection XZ
                    u = vert.co.x / cell_l
                    v = vert.co.z / cell_h

                loop[uv_layer].uv = (min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0))
                uv_count += 1
        
        print(f"[BrickGeometry]   ✓ UV mapping créé: {uv_count} loops (box projection)")

        # Recalculer les normales pour un rendu lisse
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # ============================================================
        # ÉTAPE 4: ASSIGNER LES MATERIAL SLOTS
        # ============================================================

        print(f"[BrickGeometry]   → Assignation des material slots...")

        # Vérifier que le mesh a au moins 2 material slots
        # Slot 0 = Brique, Slot 1 = Mortier
        while len(mesh.materials) < 2:
            mesh.materials.append(None)

        # Assigner slot 0 (brique) aux faces de brique
        for face in brick_faces:
            if face.is_valid:
                face.material_index = 0

        # Assigner slot 1 (mortier) aux faces de mortier
        for face in mortar_faces:
            if face.is_valid:
                face.material_index = 1

        print(f"[BrickGeometry]   ✓ {len([f for f in brick_faces if f.is_valid])} faces brique (slot 0)")
        print(f"[BrickGeometry]   ✓ {len([f for f in mortar_faces if f.is_valid])} faces mortier (slot 1)")

        bm.to_mesh(mesh)
        mesh.update()

    finally:
        bm.free()

    obj = bpy.data.objects.new("Brick_Master", mesh)

    print(f"[BrickGeometry]   ✅ Brique+mortier créée: {len(mesh.vertices)} vertices, 2 material slots")

    return obj


def is_brick_in_opening(brick_x, brick_y, brick_z, brick_width, brick_height, openings):
    """Vérifie si une brique est MAJORITAIREMENT dans une zone d'ouverture

    ✅ CORRECTION COMPLÈTE: Vérifie X/Y selon le type de mur
    - Murs AVANT/ARRIÈRE (front/back): Vérifier X et Z
    - Murs GAUCHE/DROIT (left/right): Vérifier Y et Z
    """
    if not openings:
        return False

    # Centre de la brique
    brick_center_x = brick_x + brick_width / 2
    brick_center_y = brick_y + brick_width / 2  # AJOUTÉ!
    brick_center_z = brick_z + brick_height / 2

    # Marge de sécurité
    SAFETY_MARGIN = 0.02  # 2cm

    for opening in openings:
        opening_x = opening.get('x', 0)
        opening_y = opening.get('y', 0)
        opening_z = opening.get('z', 0)
        opening_width = opening.get('width', 0)
        opening_height = opening.get('height', 0)
        opening_wall = opening.get('wall', 'front')

        # Vérifier Z (commun à tous les murs)
        opening_z_min = opening_z - SAFETY_MARGIN
        opening_z_max = opening_z + opening_height + SAFETY_MARGIN

        if not (opening_z_min < brick_center_z < opening_z_max):
            continue  # Pas au bon niveau en hauteur

        # ✅ FIX: Vérifier X OU Y selon le type de mur
        if opening_wall in ['front', 'back']:
            # Murs AVANT/ARRIÈRE: vérifier X
            opening_x_min = opening_x - SAFETY_MARGIN
            opening_x_max = opening_x + opening_width + SAFETY_MARGIN

            if opening_x_min < brick_center_x < opening_x_max:
                return True

        elif opening_wall in ['left', 'right']:
            # Murs GAUCHE/DROIT: vérifier Y
            opening_y_min = opening_y - SAFETY_MARGIN
            opening_y_max = opening_y + opening_width + SAFETY_MARGIN

            if opening_y_min < brick_center_y < opening_y_max:
                return True

    return False




def is_mortar_in_opening(mortar_x, mortar_y, mortar_z, mortar_width, mortar_height, openings):
    """Vérifie si un joint de mortier est dans une ouverture (FONCTION AJOUTÉE)"""
    if not openings:
        return False
    
    mortar_center_x = mortar_x + mortar_width / 2
    mortar_center_z = mortar_z + mortar_height / 2
    
    SAFETY_MARGIN = 0.05
    
    for opening in openings:
        opening_x = opening.get("x", 0)
        opening_z = opening.get("z", 0)
        opening_width = opening.get("width", 0)
        opening_height = opening.get("height", 0)
        
        opening_x_min = opening_x - SAFETY_MARGIN
        opening_x_max = opening_x + opening_width + SAFETY_MARGIN
        opening_z_min = opening_z - SAFETY_MARGIN
        opening_z_max = opening_z + opening_height + SAFETY_MARGIN
        
        if (opening_x_min < mortar_center_x < opening_x_max and
            opening_z_min < mortar_center_z < opening_z_max):
            return True
    
    return False


def calculate_lintel_positions(openings, wall_type, house_width, house_length, roof_type='GABLE', roof_pitch=35.0, base_height=3.0):
    """✅ NORMES: Linteaux en COURS DE SOLDATS (briques verticales)

    Un vrai linteau maçonné est un rang de briques debout ("soldier
    course") au-dessus de l'ouverture — pas des briques couchées empilées
    (qui ne "portent" rien visuellement et se superposaient aux briques
    du mur). Rotations validées numériquement:
      - Murs avant/arrière: Euler (0, -90°, 0)
          longueur→+Z (0.232m vertical), profondeur→+Y, hauteur→-X
      - Murs gauche/droit:  Euler (0, -90°, 90°)
          longueur→+Z, profondeur→-X, hauteur→-Y

    Args:
        openings: Liste des ouvertures
        wall_type: 'front', 'back', 'left', 'right'
        house_width, house_length: Dimensions de la maison
        roof_type, roof_pitch: Pour la collision avec la dalle du toit
        base_height: Hauteur nominale des murs

    Returns:
        Liste de (position Vector, rotation Euler) des briques du linteau
    """
    if not openings:
        return []

    positions = []

    print(f"[BrickGeometry] Calcul des linteaux (soldats) pour mur {wall_type}...")

    # Variation de hauteur du toit pour SHED (collision dalle)
    roof_height_variation = 0
    if roof_type == 'SHED':
        pitch_rad = math.radians(roof_pitch)
        roof_height_variation = house_width * math.tan(pitch_rad)

    row_h = BRICK_HEIGHT + MORTAR_GAP        # 0.077m: pas de la grille de rangées
    cell_along = BRICK_HEIGHT + MORTAR_GAP   # 0.077m: emprise d'un soldat le long du mur
    soldier_h = BRICK_LENGTH + MORTAR_GAP    # 0.232m: hauteur d'un soldat (brique debout)

    wall_span = house_width if wall_type in ('front', 'back') else house_length

    for opening in openings:
        if opening.get('wall') != wall_type:
            continue

        opening_x = opening.get('x', 0)
        opening_y = opening.get('y', 0)
        opening_z = opening.get('z', 0)
        opening_width = opening.get('width', 0)
        opening_height = opening.get('height', 0)

        # ✅ Aligné sur la grille des rangées du mur
        lintel_row = math.ceil((opening_z + opening_height) / row_h)
        lintel_z = lintel_row * row_h
        lintel_top = lintel_z + soldier_h

        # Coordonnée le long du mur (x pour front/back, y pour left/right)
        along_start = opening_x if wall_type in ('front', 'back') else opening_y
        lintel_start = max(0, along_start - LINTEL_OVERHANG)
        lintel_end = min(wall_span, along_start + opening_width + LINTEL_OVERHANG)

        # ✅ Clamp au sommet du mur (toits non-SHED): si le soldat ne tient
        # pas sous le sommet, pas de linteau (ouverture proche du plafond)
        if roof_type != 'SHED' and lintel_top > base_height + 0.001:
            print(f"[BrickGeometry]   Linteau omis (dépasserait le mur: {lintel_top:.2f}m > {base_height:.2f}m)")
            continue

        # Clamp dalle SHED pour les murs latéraux (hauteur constante par mur)
        if roof_type == 'SHED' and wall_type == 'left':
            if lintel_top > base_height - ROOF_GAP:
                continue
        if roof_type == 'SHED' and wall_type == 'right':
            if lintel_top > base_height + roof_height_variation - ROOF_GAP:
                continue

        num_bricks = int((lintel_end - lintel_start) / cell_along) + 1

        for i in range(num_bricks):
            coord = lintel_start + i * cell_along
            if coord + cell_along > lintel_end + 0.001:
                continue

            # Clamp dalle SHED par position pour les murs avant/arrière
            # (le toit monte avec x — vérifier au début du soldat, côté bas)
            if roof_type == 'SHED' and wall_type in ('front', 'back'):
                ratio = coord / house_width if house_width > 0 else 0
                roof_bottom = base_height + roof_height_variation * ratio - ROOF_GAP
                if lintel_top > roof_bottom:
                    continue

            if wall_type == 'front':
                # Occupe x∈[pos-0.077, pos], y∈[pos, pos+0.112]
                pos = Vector((coord + cell_along, 0, lintel_z))
                rot = Euler((0, math.radians(-90), 0), 'XYZ')
            elif wall_type == 'back':
                # Aligné sur le mur arrière (décalé vers l'intérieur)
                pos = Vector((coord + cell_along, house_length - (BRICK_DEPTH + MORTAR_GAP), lintel_z))
                rot = Euler((0, math.radians(-90), 0), 'XYZ')
            elif wall_type == 'left':
                # Occupe x∈[pos-0.112, pos], y∈[pos-0.077, pos]
                pos = Vector((BRICK_DEPTH + MORTAR_GAP, coord + cell_along, lintel_z))
                rot = Euler((0, math.radians(-90), math.radians(90)), 'XYZ')
            else:  # right
                pos = Vector((house_width, coord + cell_along, lintel_z))
                rot = Euler((0, math.radians(-90), math.radians(90)), 'XYZ')

            positions.append((pos, rot))

    print(f"[BrickGeometry]   ✓ {len(positions)} briques de linteau (soldats) pour {wall_type}")
    return positions


def _calculate_brick_transform(direction, distance, z, start_pos):
    """Helper pour calculer position et rotation d'une brique selon la direction

    Args:
        direction: 'X' ou 'Y'
        distance: Distance le long du mur
        z: Hauteur
        start_pos: Position de départ du mur

    Returns:
        tuple: (position Vector, rotation Euler)
    """
    # (math importé au niveau module)
    if direction == 'X':
        pos = start_pos + Vector((distance, 0, z))
        rot = Euler((0, 0, 0), 'XYZ')
    else:  # Y
        pos = start_pos + Vector((0, distance, z))
        rot = Euler((0, 0, math.radians(90)), 'XYZ')
    return pos, rot


def calculate_brick_positions_for_wall(wall_length, wall_height, start_pos, direction, openings=None, bonding_pattern='RUNNING'):
    """Calcule toutes les positions de briques pour un mur avec pattern d'appareillage

    Args:
        wall_length: Longueur du mur
        wall_height: Hauteur du mur
        start_pos: Position de départ
        direction: 'X' ou 'Y'
        openings: Liste des ouvertures
        bonding_pattern: 'RUNNING', 'STACK', 'FLEMISH', 'ENGLISH'

    Returns:
        Liste de (position, rotation) pour chaque brique
    """
    positions = []

    # ✅ FIX CRITIQUE: L'espacement est TOUJOURS BRICK_LENGTH. La rotation 90°
    # des briques en direction Y aligne leur LONGUEUR (22cm) le long du mur —
    # utiliser BRICK_DEPTH (10cm) faisait se chevaucher toutes les briques
    # des murs latéraux (masse solide de briques interpénétrées).
    brick_spacing = BRICK_LENGTH

    num_bricks_width = int(wall_length / (brick_spacing + MORTAR_GAP))
    num_bricks_height = int(wall_height / (BRICK_HEIGHT + MORTAR_GAP))

    for row in range(num_bricks_height):
        # ✅ NOUVEAU: Calculer l'offset selon le pattern d'appareillage
        if bonding_pattern == 'RUNNING':
            # Quinconce: offset de demi-brique sur rangées impaires
            offset = (brick_spacing + MORTAR_GAP) / 2 if row % 2 == 1 else 0
        elif bonding_pattern == 'STACK':
            # Empilé: pas d'offset, briques alignées verticalement
            offset = 0
        elif bonding_pattern == 'FLEMISH':
            # Flemish bond: alternance headers/stretchers
            # Simulé avec offset 1/4 sur rangées impaires
            offset = (brick_spacing + MORTAR_GAP) / 4 if row % 2 == 1 else 0
        elif bonding_pattern == 'ENGLISH':
            # ✅ FIX: English bond approximé — avant, ce pattern était
            # identique à RUNNING. Cycle sur 4 rangées: 0, 1/2, 1/4, 3/4
            # (un vrai English bond nécessiterait des briques coupées)
            cell = brick_spacing + MORTAR_GAP
            offset = (0, cell / 2, cell / 4, cell * 3 / 4)[row % 4]
        else:
            # Défaut: running bond
            offset = (brick_spacing + MORTAR_GAP) / 2 if row % 2 == 1 else 0

        for col in range(num_bricks_width + 1):
            # Position le long du mur
            distance_along_wall = col * (brick_spacing + MORTAR_GAP) + offset

            # ✅ FIX: Tolérance réduite (la brique pouvait déborder de 6cm
            # au bout du mur avec l'ancienne marge de 5cm)
            if distance_along_wall + brick_spacing + MORTAR_GAP > wall_length + 0.001:
                continue

            # Hauteur
            z = row * (BRICK_HEIGHT + MORTAR_GAP)

            # ✅ REFACTOR: Utiliser fonction helper pour calcul position/rotation
            pos, rot = _calculate_brick_transform(direction, distance_along_wall, z, start_pos)

            # Vérifier si dans une ouverture
            if is_brick_in_opening(pos.x, pos.y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                continue

            positions.append((pos, rot))

    return positions


def calculate_brick_positions_for_wall_gable(wall_length, base_height, peak_height, start_pos, direction, openings=None, bonding_pattern='RUNNING'):
    """✅ NOUVEAU: Briques d'un mur PIGNON sous toit à 2 pans (GABLE)

    La ligne de toit forme un triangle: base_height aux deux extrémités,
    base_height + peak_height au centre du mur. Les briques remplissent le
    pignon en restant sous la FACE INFÉRIEURE de la dalle du toit (ROOF_GAP).

    Args:
        wall_length: Longueur du mur (le faîtage est à wall_length/2)
        base_height: Hauteur des murs à l'égout
        peak_height: Hauteur ADDITIONNELLE au faîtage
        start_pos: Position de départ
        direction: 'X' ou 'Y'
        openings: Liste des ouvertures
        bonding_pattern: 'RUNNING', 'STACK', 'FLEMISH', 'ENGLISH'

    Returns:
        Liste de (position, rotation) pour chaque brique
    """
    positions = []
    brick_spacing = BRICK_LENGTH
    cell = brick_spacing + MORTAR_GAP
    num_bricks_width = int(wall_length / cell)
    max_possible_rows = int((base_height + peak_height) / (BRICK_HEIGHT + MORTAR_GAP)) + 1

    half = wall_length / 2.0

    def roof_bottom_at(x):
        """Face inférieure de la dalle à la position x (triangle du pignon)"""
        if half <= 0:
            return base_height - ROOF_GAP
        ratio = 1.0 - abs(x - half) / half  # 0 aux égouts, 1 au faîtage
        return base_height + peak_height * max(0.0, ratio) - ROOF_GAP

    for col in range(num_bricks_width + 1):
        distance_base = col * cell

        if distance_base + cell > wall_length + 0.001:
            continue

        for row in range(max_possible_rows + 1):
            # Offset selon le pattern d'appareillage (identique aux autres murs)
            if bonding_pattern == 'STACK':
                offset = 0
            elif bonding_pattern == 'FLEMISH':
                offset = cell / 4 if row % 2 == 1 else 0
            elif bonding_pattern == 'ENGLISH':
                offset = (0, cell / 2, cell / 4, cell * 3 / 4)[row % 4]
            else:  # RUNNING (défaut)
                offset = cell / 2 if row % 2 == 1 else 0

            distance = distance_base + offset

            if distance + cell > wall_length + 0.001:
                continue

            z = row * (BRICK_HEIGHT + MORTAR_GAP)
            brick_top = z + BRICK_HEIGHT + MORTAR_GAP

            # ✅ Le toit est le plus BAS à l'extrémité de la brique la plus
            # éloignée du faîtage — vérifier les DEUX bouts et garder le min
            limit = min(roof_bottom_at(distance), roof_bottom_at(distance + cell))

            if brick_top > limit:
                # Sous le faîtage la rangée peut continuer plus haut pour les
                # colonnes plus proches du centre → continue, pas break
                continue

            pos, rot = _calculate_brick_transform(direction, distance, z, start_pos)

            if is_brick_in_opening(pos.x, pos.y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                continue

            positions.append((pos, rot))

    return positions


def calculate_brick_positions_for_wall_sloped(wall_length, base_height, roof_height, start_pos, direction, openings=None, bonding_pattern='RUNNING'):
    """Calcule les positions de briques pour un mur en pente (shed roof) avec pattern d'appareillage

    Pour les murs avant/arrière d'un shed roof:
    - Hauteur varie de base_height (X=0) à base_height + roof_height (X=wall_length)
    - Les briques forment un "escalier" suivant la pente

    Args:
        wall_length: Longueur du mur
        base_height: Hauteur de base (côté bas)
        roof_height: Hauteur additionnelle (côté haut)
        start_pos: Position de départ
        direction: 'X' ou 'Y'
        openings: Liste des ouvertures
        bonding_pattern: 'RUNNING', 'STACK', 'FLEMISH', 'ENGLISH'

    Returns:
        Liste de (position, rotation) pour chaque brique
    """
    positions = []
    # ✅ FIX: Espacement TOUJOURS BRICK_LENGTH (la rotation 90° aligne la
    # longueur de la brique le long du mur, voir calculate_brick_positions_for_wall)
    brick_spacing = BRICK_LENGTH
    num_bricks_width = int(wall_length / (brick_spacing + MORTAR_GAP))

    # Calculer nombre maximum de rangées
    max_possible_rows = int((base_height + roof_height) / (BRICK_HEIGHT + MORTAR_GAP))

    # Pour chaque colonne
    for col in range(num_bricks_width + 1):
        # Position X le long du mur
        distance_along_wall_base = col * (brick_spacing + MORTAR_GAP)

        # ✅ FIX: Tolérance réduite (débord de 6cm possible avant)
        if distance_along_wall_base + brick_spacing + MORTAR_GAP > wall_length + 0.001:
            continue

        # Pour chaque rangée possible
        for row in range(max_possible_rows + 1):
            # ✅ NOUVEAU: Calculer l'offset selon le pattern d'appareillage
            if bonding_pattern == 'RUNNING':
                # Quinconce: offset de demi-brique sur rangées impaires
                offset = (brick_spacing + MORTAR_GAP) / 2 if row % 2 == 1 else 0
            elif bonding_pattern == 'STACK':
                # Empilé: pas d'offset, briques alignées verticalement
                offset = 0
            elif bonding_pattern == 'FLEMISH':
                # Flemish bond: alternance headers/stretchers
                offset = (brick_spacing + MORTAR_GAP) / 4 if row % 2 == 1 else 0
            elif bonding_pattern == 'ENGLISH':
                # ✅ FIX: English bond approximé (identique à RUNNING avant)
                cell = brick_spacing + MORTAR_GAP
                offset = (0, cell / 2, cell / 4, cell * 3 / 4)[row % 4]
            else:
                # Défaut: running bond
                offset = (brick_spacing + MORTAR_GAP) / 2 if row % 2 == 1 else 0

            distance_along_wall = distance_along_wall_base + offset

            if distance_along_wall + brick_spacing + MORTAR_GAP > wall_length + 0.001:
                continue

            # Position Z de la brique (bas)
            z = row * (BRICK_HEIGHT + MORTAR_GAP)

            # ✅ FIX DÉFINITIF: Le toit est une DALLE ÉPAISSE (ROOF_THICKNESS_PITCHED).
            # Sa face INFÉRIEURE est plus basse que la ligne de toit visible.
            # Les briques doivent rester SOUS cette face inférieure.
            # On vérifie au DÉBUT de la brique (là où le toit est le plus bas,
            # car il monte de gauche à droite).
            ratio = distance_along_wall / wall_length if wall_length > 0 else 0
            roof_bottom_at_brick_start = base_height + (roof_height * ratio) - ROOF_GAP

            # ✅ FIX: La brique maître inclut son mortier intégré → hauteur
            # réelle de la cellule = BRICK_HEIGHT + MORTAR_GAP
            brick_top = z + BRICK_HEIGHT + MORTAR_GAP

            # Si le top de la brique atteint la face inférieure du toit, arrêter cette colonne
            if brick_top > roof_bottom_at_brick_start:
                break

            # ✅ REFACTOR: Utiliser fonction helper pour calcul position/rotation
            pos, rot = _calculate_brick_transform(direction, distance_along_wall, z, start_pos)

            # Vérifier si dans une ouverture
            if is_brick_in_opening(pos.x, pos.y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                continue

            positions.append((pos, rot))

    return positions


# ============================================================
# MORTIER 3D RÉALISTE
# ============================================================

def create_mortar_3d_joints(house_width, house_length, total_height, collection, openings=None):
    """Crée des joints de mortier 3D réalistes au lieu de plans plats
    
    Args:
        house_width (float): Largeur maison
        house_length (float): Longueur maison
        total_height (float): Hauteur totale
        collection: Collection Blender
        openings (list): Liste des ouvertures à éviter
        
    Returns:
        list: Liste des objets mortier créés
    """
    
    mortars = []
    bm = bmesh.new()
    
    try:
        # Calculer nombre de rangées et colonnes
        num_rows = int(total_height / (BRICK_HEIGHT + MORTAR_GAP))
        num_cols_width = int(house_width / (BRICK_LENGTH + MORTAR_GAP))
        num_cols_length = int(house_length / (BRICK_LENGTH + MORTAR_GAP))
        
        print(f"[BrickGeometry]   Génération joints 3D: {num_rows} rangées")
        
        joint_count = 0
        
        # === JOINTS HORIZONTAUX (entre rangées) ===
        for row in range(num_rows + 1):
            z = row * (BRICK_HEIGHT + MORTAR_GAP) - MORTAR_GAP/2
            
            # Mur AVANT
            # CORRIGÉ : Vérifier les ouvertures
            if not is_mortar_in_opening(0, 0, z, house_width, MORTAR_GAP, openings):
                _add_horizontal_joint(bm, 0, 0, z, house_width, BRICK_DEPTH, MORTAR_GAP)
            joint_count += 1
            
            # Mur ARRIÈRE
            if not is_mortar_in_opening(0, house_length, z, house_width, MORTAR_GAP, openings):
                _add_horizontal_joint(bm, 0, house_length - BRICK_DEPTH, z, house_width, BRICK_DEPTH, MORTAR_GAP)
            joint_count += 1
            
            # Mur GAUCHE
            if not is_mortar_in_opening(0, 0, z, BRICK_DEPTH, MORTAR_GAP, openings):
                _add_horizontal_joint(bm, 0, 0, z, BRICK_DEPTH, house_length, MORTAR_GAP)
            joint_count += 1
            
            # Mur DROIT
            if not is_mortar_in_opening(house_width, 0, z, BRICK_DEPTH, MORTAR_GAP, openings):
                _add_horizontal_joint(bm, house_width - BRICK_DEPTH, 0, z, BRICK_DEPTH, house_length, MORTAR_GAP)
            joint_count += 1
        
        # === JOINTS VERTICAUX (entre briques) ===
        # Murs AVANT/ARRIÈRE
        for row in range(num_rows):
            for col in range(num_cols_width + 1):
                offset = (BRICK_LENGTH + MORTAR_GAP) / 2 if row % 2 == 1 else 0
                x = col * (BRICK_LENGTH + MORTAR_GAP) - MORTAR_GAP/2 + offset
                z = row * (BRICK_HEIGHT + MORTAR_GAP)
                
                if 0 <= x <= house_width:
                    # Mur AVANT
                    # CORRIGÉ : Vérifier les ouvertures
                    if not is_mortar_in_opening(0, 0, z, house_width, MORTAR_GAP, openings):
                        _add_vertical_joint(bm, x, 0, z, MORTAR_GAP, BRICK_DEPTH, BRICK_HEIGHT)
                    joint_count += 1
                    
                    # Mur ARRIÈRE
                    if not is_mortar_in_opening(0, house_length, z, house_width, MORTAR_GAP, openings):
                        _add_vertical_joint(bm, x, house_length - BRICK_DEPTH, z, MORTAR_GAP, BRICK_DEPTH, BRICK_HEIGHT)
                    joint_count += 1
        
        # Murs GAUCHE/DROIT
        for row in range(num_rows):
            for col in range(num_cols_length + 1):
                offset = (BRICK_LENGTH + MORTAR_GAP) / 2 if row % 2 == 1 else 0
                y = col * (BRICK_LENGTH + MORTAR_GAP) - MORTAR_GAP/2 + offset
                z = row * (BRICK_HEIGHT + MORTAR_GAP)
                
                if 0 <= y <= house_length:
                    # Mur GAUCHE
                    if not is_mortar_in_opening(0, 0, z, BRICK_DEPTH, MORTAR_GAP, openings):
                        _add_vertical_joint(bm, 0, y, z, BRICK_DEPTH, MORTAR_GAP, BRICK_HEIGHT)
                    joint_count += 1
                    
                    # Mur DROIT
                    if not is_mortar_in_opening(house_width, 0, z, BRICK_DEPTH, MORTAR_GAP, openings):
                        _add_vertical_joint(bm, house_width - BRICK_DEPTH, y, z, BRICK_DEPTH, MORTAR_GAP, BRICK_HEIGHT)
                    joint_count += 1
        
        print(f"[BrickGeometry]   {joint_count} joints 3D générés")
        
        # Fusionner vertices proches pour optimiser
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
        
        # Recalculer normales
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        
        # Créer objet
        mesh = bpy.data.meshes.new("Mortar_3D_Joints")
        bm.to_mesh(mesh)
        
        mortar_obj = bpy.data.objects.new("Mortar_3D", mesh)
        mortar_obj["house_part"] = "wall"
        
        # Appliquer matériau
        apply_mortar_material_to_object(mortar_obj)
        
        collection.objects.link(mortar_obj)
        mortars.append(mortar_obj)
        
        print(f"[BrickGeometry]   ✓ Mesh final: {len(mesh.vertices)} vertices, {len(mesh.polygons)} faces")
        
    finally:
        bm.free()
    
    return mortars


def _add_horizontal_joint(bm, x, y, z, width, depth, height):
    """Ajoute un joint horizontal (entre rangées) au bmesh
    
    Args:
        bm: BMesh
        x, y, z: Position du coin
        width, depth, height: Dimensions du joint
    """
    
    # 8 vertices pour un cube
    v1 = bm.verts.new((x, y, z))
    v2 = bm.verts.new((x + width, y, z))
    v3 = bm.verts.new((x + width, y + depth, z))
    v4 = bm.verts.new((x, y + depth, z))
    
    v5 = bm.verts.new((x, y, z + height))
    v6 = bm.verts.new((x + width, y, z + height))
    v7 = bm.verts.new((x + width, y + depth, z + height))
    v8 = bm.verts.new((x, y + depth, z + height))
    
    # 6 faces
    bm.faces.new([v1, v2, v3, v4])
    bm.faces.new([v5, v8, v7, v6])
    bm.faces.new([v1, v5, v6, v2])
    bm.faces.new([v2, v6, v7, v3])
    bm.faces.new([v3, v7, v8, v4])
    bm.faces.new([v4, v8, v5, v1])


def _add_vertical_joint(bm, x, y, z, width, depth, height):
    """Ajoute un joint vertical (entre briques) au bmesh
    
    Args:
        bm: BMesh
        x, y, z: Position du coin
        width, depth, height: Dimensions du joint
    """
    
    # Utilise la même logique que horizontal joint (c'est juste un cube)
    _add_horizontal_joint(bm, x, y, z, width, depth, height)


# ============================================================
# GÉNÉRATION GÉOMÉTRIE COMPLÈTE (pour HIGH quality)
# ============================================================

def generate_brick_wall(width, height, depth=BRICK_DEPTH, quality='MEDIUM', openings=None):
    """Génère UN mur en briques 3D avec toute la géométrie"""
    
    use_variations = (quality in ['MEDIUM', 'HIGH'])
    
    num_bricks_width = int(width / (BRICK_LENGTH + MORTAR_GAP))
    num_bricks_height = int(height / (BRICK_HEIGHT + MORTAR_GAP))
    
    bricks_bm = bmesh.new()
    brick_count = 0
    
    for row in range(num_bricks_height):
        offset = (BRICK_LENGTH + MORTAR_GAP) / 2 if row % 2 == 1 else 0
        
        for col in range(num_bricks_width + 1):
            x = col * (BRICK_LENGTH + MORTAR_GAP) + offset
            y = 0
            z = row * (BRICK_HEIGHT + MORTAR_GAP)
            
            if x + BRICK_LENGTH > width + 0.05:
                continue
            
            # Vérifier si dans une ouverture
            if is_brick_in_opening(x, y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                continue
            
            if use_variations:
                x += random.uniform(-0.001, 0.001)
                z += random.uniform(-0.0005, 0.0005)
            
            add_brick_to_bmesh(bricks_bm, x, y, z, BRICK_LENGTH, depth, BRICK_HEIGHT, use_variations)
            brick_count += 1
    
    bricks_mesh = bpy.data.meshes.new("BrickWall_Mesh")
    bricks_bm.to_mesh(bricks_mesh)
    bricks_bm.free()
    
    bricks_obj = bpy.data.objects.new("BrickWall", bricks_mesh)
    
    mortar_obj = create_mortar_base(width, height, depth)
    
    if quality == 'HIGH':
        add_brick_displacement(bricks_obj, strength=0.003)
    
    return bricks_obj, mortar_obj


def add_brick_to_bmesh(bm, x, y, z, length, depth, height, use_variations=True):
    """Ajoute une brique au bmesh"""
    
    if use_variations:
        height_var = height + random.uniform(-0.001, 0.001)
        length_var = length + random.uniform(-0.0008, 0.0008)
    else:
        height_var = height
        length_var = length
    
    v1 = bm.verts.new((x, y, z))
    v2 = bm.verts.new((x + length_var, y, z))
    v3 = bm.verts.new((x + length_var, y + depth, z))
    v4 = bm.verts.new((x, y + depth, z))
    
    v5 = bm.verts.new((x, y, z + height_var))
    v6 = bm.verts.new((x + length_var, y, z + height_var))
    v7 = bm.verts.new((x + length_var, y + depth, z + height_var))
    v8 = bm.verts.new((x, y + depth, z + height_var))
    
    bm.faces.new([v1, v2, v3, v4])
    bm.faces.new([v5, v8, v7, v6])
    bm.faces.new([v1, v5, v6, v2])
    bm.faces.new([v2, v6, v7, v3])
    bm.faces.new([v3, v7, v8, v4])
    bm.faces.new([v4, v8, v5, v1])


def create_mortar_base(width, height, depth):
    """Crée une couche de mortier plate"""
    
    bm = bmesh.new()
    
    w = width + 0.02
    h = height + 0.02
    d = depth
    
    v1 = bm.verts.new((0, 0, 0))
    v2 = bm.verts.new((w, 0, 0))
    v3 = bm.verts.new((w, d, 0))
    v4 = bm.verts.new((0, d, 0))
    
    v5 = bm.verts.new((0, 0, h))
    v6 = bm.verts.new((w, 0, h))
    v7 = bm.verts.new((w, d, h))
    v8 = bm.verts.new((0, d, h))
    
    bm.faces.new([v1, v2, v3, v4])
    bm.faces.new([v5, v8, v7, v6])
    bm.faces.new([v1, v5, v6, v2])
    bm.faces.new([v2, v6, v7, v3])
    bm.faces.new([v3, v7, v8, v4])
    bm.faces.new([v4, v8, v5, v1])
    
    mesh = bpy.data.meshes.new("Mortar_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    
    mortar_obj = bpy.data.objects.new("Mortar", mesh)
    
    return mortar_obj


def add_brick_displacement(obj, strength=0.003):
    """Ajoute un modificateur Displace pour relief"""

    # ✅ FIX: Réutiliser la texture existante (avant: un nouveau datablock
    # Brick_Displace_Tex.001/.002/... par mur et par régénération)
    tex = bpy.data.textures.get("Brick_Displace_Tex")
    if tex is None:
        tex = bpy.data.textures.new("Brick_Displace_Tex", 'CLOUDS')
        tex.noise_scale = 0.3
        tex.noise_depth = 3
        # Compat: noise_basis existe toujours sur CloudsTexture en 4.2,
        # mais on le garde optionnel par prudence
        if hasattr(tex, 'noise_basis'):
            tex.noise_basis = 'BLENDER_ORIGINAL'

    mod = obj.modifiers.new("BrickDisplace", 'DISPLACE')
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    mod.direction = 'NORMAL'


# ============================================================
# STATS ET UTILITAIRES
# ============================================================

def calculate_brick_count(width, height):
    """Calcule le nombre de briques pour un mur"""
    num_width = int(width / (BRICK_LENGTH + MORTAR_GAP))
    num_height = int(height / (BRICK_HEIGHT + MORTAR_GAP))
    
    total = 0
    for row in range(num_height):
        if row % 2 == 1:
            total += num_width + 1
        else:
            total += num_width
    
    return total


def get_brick_dimensions():
    """Retourne les dimensions standards des briques"""
    return {
        'length': BRICK_LENGTH,
        'height': BRICK_HEIGHT,
        'depth': BRICK_DEPTH,
        'mortar_gap': MORTAR_GAP
    }


def print_house_brick_stats(house_width, house_length, total_height):
    """Affiche des statistiques sur la maison en briques"""
    front_back = calculate_brick_count(house_width, total_height) * 2
    left_right = calculate_brick_count(house_length, total_height) * 2
    total = front_back + left_right
    
    dims = get_brick_dimensions()
    
    print("\n" + "="*60)
    print("STATISTIQUES MAISON EN BRIQUES")
    print("="*60)
    print(f"Dimensions maison: {house_width:.2f}m x {house_length:.2f}m x {total_height:.2f}m")
    print(f"Murs avant/arrière: ~{front_back} briques")
    print(f"Murs gauche/droite: ~{left_right} briques")
    print(f"TOTAL: ~{total} briques")
    print(f"Dimensions brique: {dims['length']*100:.1f}cm x {dims['height']*100:.1f}cm x {dims['depth']*100:.1f}cm")
    print(f"Épaisseur mortier: {dims['mortar_gap']*100:.1f}cm")
    print("="*60 + "\n")