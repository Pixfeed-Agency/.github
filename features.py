# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Exterior Features Module
#  Copyright (C) 2025 mvaertan
#
#  Éclairage, cheminée, gouttières, terrasse, garage, balcon, tuiles.
#  Chaque fonction prend (props, collection) + le contexte dimensionnel
#  et retourne la liste des objets créés.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler


# ============================================================
# HELPERS
# ============================================================

def _new_mesh_obj(name, bm, collection, part, material=None):
    """bmesh → objet lié à la collection, avec tag house_part"""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj["house_part"] = part
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def _add_box(bm, x0, y0, z0, x1, y1, z1):
    """Boîte [x0..x1]×[y0..y1]×[z0..z1] (winding extérieur)"""
    vb = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
    vt = [bm.verts.new(c) for c in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    return vb + vt


def _simple_material(name, color, roughness=0.7, metallic=0.0):
    """Matériau Principled simple, mis en cache par nom"""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    if not mat.use_nodes:
        mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*color[:3], 1.0)
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat


# ============================================================
# ÉCLAIRAGE AUTOMATIQUE
# ============================================================

def add_scene_lighting(props, collection):
    """✅ IMPLÉMENTÉ: Soleil + remplissage + monde ciel.

    Idempotent: remplace les lumières House_* existantes.
    """
    created = []

    # Purger les anciennes lumières de l'addon
    for obj in list(bpy.data.objects):
        if obj.name.startswith("House_Sun") or obj.name.startswith("House_Fill"):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Soleil principal (chaud, 3/4 avant-gauche)
    sun_data = bpy.data.lights.new("House_Sun", 'SUN')
    sun_data.energy = 3.5
    sun_data.angle = math.radians(1.5)  # Ombres légèrement douces
    sun_data.color = (1.0, 0.956, 0.89)
    sun = bpy.data.objects.new("House_Sun", sun_data)
    sun.rotation_euler = Euler((math.radians(50), math.radians(12), math.radians(-55)), 'XYZ')
    collection.objects.link(sun)
    created.append(sun)

    # Remplissage froid opposé (déboucher les ombres)
    fill_data = bpy.data.lights.new("House_Fill", 'SUN')
    fill_data.energy = 1.4
    fill_data.angle = math.radians(15)
    fill_data.color = (0.75, 0.82, 1.0)
    fill = bpy.data.objects.new("House_Fill", fill_data)
    fill.rotation_euler = Euler((math.radians(60), 0, math.radians(120)), 'XYZ')
    collection.objects.link(fill)
    created.append(fill)

    # Monde: ciel bleu clair si le monde est vide/défaut
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("House_World")
    if not scene.world.use_nodes:
        scene.world.use_nodes = True
    bg = next((n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg is not None:
        bg.inputs[0].default_value = (0.52, 0.68, 0.92, 1.0)
        bg.inputs[1].default_value = 1.0

    print(f"[House] ✓ Éclairage: soleil + remplissage + ciel")
    return created


# ============================================================
# CHEMINÉE
# ============================================================

def build_chimney(props, collection, wall_height, roof_peak_z):
    """Cheminée en brique traversant le toit près du faîtage.

    Args:
        wall_height: sommet des murs (hauteur réelle)
        roof_peak_z: altitude du faîtage (pour dépasser du toit)
    """
    width = props.house_width
    length = props.house_length

    cw = 0.65   # section de la cheminée
    top = roof_peak_z + 0.7          # dépasse le faîtage
    base = wall_height - 1.2         # ancrée sous le toit

    # Position: proche du faîtage, au tiers de la maison
    ridge_along_y = length >= width
    if ridge_along_y:
        cx = width / 2 + 0.9         # léger décalage du faîtage
        cy = length * 0.3
    else:
        cx = width * 0.3
        cy = length / 2 + 0.9

    bm = bmesh.new()
    # Fût
    _add_box(bm, cx - cw/2, cy - cw/2, base, cx + cw/2, cy + cw/2, top)
    # Couronnement (chapeau débordant)
    cap = 0.09
    _add_box(bm, cx - cw/2 - cap, cy - cw/2 - cap, top,
             cx + cw/2 + cap, cy + cw/2 + cap, top + 0.12)
    # Conduit (petit carré sombre au sommet)
    _add_box(bm, cx - 0.14, cy - 0.14, top + 0.12, cx + 0.14, cy + 0.14, top + 0.3)

    mat = _simple_material("House_Chimney_Brick", (0.45, 0.18, 0.12), roughness=0.9)
    obj = _new_mesh_obj("Chimney", bm, collection, "chimney", mat)
    print(f"[House] ✓ Cheminée à ({cx:.1f}, {cy:.1f}), sommet {top + 0.3:.2f}m")
    return [obj]


# ============================================================
# GOUTTIÈRES + DESCENTES
# ============================================================

def build_gutters(props, collection, eave_z_left, eave_z_right, o_eave, o_rake):
    """Gouttières le long des égouts + descentes aux angles.

    Gère GABLE (2 égouts), SHED (égout bas + haut), HIP (4), GAMBREL (2).
    eave_z_left/right: altitude de l'égout de chaque côté (SHED: différents).
    """
    width = props.house_width
    length = props.house_length
    roof_type = props.roof_type

    if roof_type == 'FLAT':
        return []  # L'acrotère draine vers l'intérieur

    r = 0.075          # rayon gouttière
    down_r = 0.045     # rayon descente
    mat = _simple_material("House_Gutter", (0.55, 0.55, 0.58), roughness=0.35, metallic=0.8)

    objs = []
    bm = bmesh.new()

    def gutter_run(p0, p1):
        """Demi-cylindre ouvert approximé: cylindre le long de p0→p1"""
        direction = (Vector(p1) - Vector(p0))
        run = direction.length
        if run < 0.05:
            return
        seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                    radius1=r, radius2=r, depth=run)
        # Orienter le cylindre (axe Z par défaut) le long de la direction
        quat = direction.normalized().to_track_quat('Z', 'Y')
        center = (Vector(p0) + Vector(p1)) / 2
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())

    def downspout(x, y, z_top):
        seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=8,
                                    radius1=down_r, radius2=down_r, depth=z_top)
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(Vector((x, y, z_top / 2))))

    ridge_along_y = length >= width

    if roof_type in ('GABLE', 'GAMBREL') and ridge_along_y or roof_type == 'SHED':
        # Égouts sur les côtés X (gauche/droit)
        y0, y1 = -o_rake, length + o_rake
        gutter_run((-o_eave, y0, eave_z_left - r), (-o_eave, y1, eave_z_left - r))
        gutter_run((width + o_eave, y0, eave_z_right - r), (width + o_eave, y1, eave_z_right - r))
        # ✅ FIX: Descentes CONTRE le mur (avant: au bord du débord, flottantes)
        downspout(-down_r - 0.01, 0.35, eave_z_left - r)
        downspout(width + down_r + 0.01, length - 0.35, eave_z_right - r)
    elif roof_type in ('GABLE', 'GAMBREL'):
        # Faîtage en X → égouts sur les côtés Y (avant/arrière)
        x0, x1 = -o_rake, width + o_rake
        gutter_run((x0, -o_eave, eave_z_left - r), (x1, -o_eave, eave_z_left - r))
        gutter_run((x0, length + o_eave, eave_z_right - r), (x1, length + o_eave, eave_z_right - r))
        downspout(0.35, -down_r - 0.01, eave_z_left - r)
        downspout(width - 0.35, length + down_r + 0.01, eave_z_right - r)

    if roof_type == 'HIP':
        # 4 égouts périphériques
        z = eave_z_left - r
        gutter_run((-o_eave, -o_eave, z), (width + o_eave, -o_eave, z))
        gutter_run((width + o_eave, -o_eave, z), (width + o_eave, length + o_eave, z))
        gutter_run((width + o_eave, length + o_eave, z), (-o_eave, length + o_eave, z))
        gutter_run((-o_eave, length + o_eave, z), (-o_eave, -o_eave, z))
        downspout(-down_r - 0.01, 0.35, z)
        downspout(width + down_r + 0.01, length - 0.35, z)

    if len(bm.verts) == 0:
        bm.free()
        return []

    obj = _new_mesh_obj("Gutters", bm, collection, "gutter", mat)
    objs.append(obj)
    print(f"[House] ✓ Gouttières + descentes ({roof_type})")
    return objs


# ============================================================
# TERRASSE
# ============================================================

def build_terrace(props, collection, plinth_visible):
    """Terrasse en lames de bois à l'ARRIÈRE de la maison."""
    width = props.house_width
    length = props.house_length

    t_w = min(5.0, width * 0.6)      # largeur de la terrasse
    t_d = 3.2                        # profondeur
    t_h = max(plinth_visible, 0.12)  # hauteur du platelage
    x0 = (width - t_w) / 2
    y0 = length                       # accolée à l'arrière
    board_w = 0.14
    gap = 0.012

    bm = bmesh.new()
    # Structure (bordure pleine sous les lames)
    _add_box(bm, x0, y0, 0, x0 + t_w, y0 + t_d, t_h - 0.025)
    # Lames de bois (le long de X)
    y = y0 + 0.02
    while y + board_w <= y0 + t_d - 0.02 + 1e-6:
        _add_box(bm, x0 + 0.02, y, t_h - 0.025, x0 + t_w - 0.02, y + board_w, t_h)
        y += board_w + gap

    mat = _simple_material("House_Terrace_Wood", (0.42, 0.27, 0.15), roughness=0.65)
    obj = _new_mesh_obj("Terrace", bm, collection, "terrace", mat)
    print(f"[House] ✓ Terrasse {t_w:.1f}×{t_d:.1f}m à l'arrière")
    return [obj]


# ============================================================
# GARAGE
# ============================================================

def build_garage(props, collection, plinth_visible):
    """Garage attenant avec porte sectionnelle.

    Utilise garage_width / garage_depth / garage_position des propriétés.
    Volume accolé au mur gauche ou droit, façade alignée sur l'avant,
    toit monopente léger s'éloignant de la maison.
    """
    width = props.house_width
    g_w = props.garage_width
    g_d = min(props.garage_depth, props.house_length)
    g_h = 2.6
    on_right = getattr(props, 'garage_position', 'RIGHT') != 'LEFT'

    if on_right:
        x0, x1 = width, width + g_w
        slope_dir = 1
    else:
        x0, x1 = -g_w, 0
        slope_dir = -1

    wall_t = 0.2
    roof_drop = 0.35  # pente légère vers l'extérieur

    bm = bmesh.new()

    def top_z(x):
        """Toit monopente: haut côté maison, bas côté extérieur"""
        if on_right:
            ratio = (x - x0) / g_w
        else:
            ratio = (x1 - x) / g_w
        return g_h - roof_drop * ratio

    # Murs (3 côtés: extérieur + arrière + avant percé de la porte)
    door_w = min(2.6, g_w - 1.0)
    door_h = 2.05
    dx0 = (x0 + x1) / 2 - door_w / 2
    dx1 = dx0 + door_w

    # Mur extérieur (côté opposé à la maison)
    ox = x1 - wall_t if on_right else x0
    _add_box(bm, ox, 0, 0, ox + wall_t, g_d, top_z(ox + wall_t / 2))
    # Mur arrière
    _add_box(bm, x0, g_d - wall_t, 0, x1, g_d, g_h - roof_drop * 0.5)
    # Façade avant: 2 trumeaux + linteau au-dessus de la porte
    _add_box(bm, x0, 0, 0, dx0, wall_t, top_z((x0 + dx0) / 2))
    _add_box(bm, dx1, 0, 0, x1, wall_t, top_z((dx1 + x1) / 2))
    _add_box(bm, dx0, 0, door_h, dx1, wall_t, top_z((dx0 + dx1) / 2))

    mat_wall = _simple_material("House_Garage_Wall", (0.82, 0.8, 0.75), roughness=0.8)
    walls = _new_mesh_obj("Garage_Walls", bm, collection, "garage", mat_wall)

    # Toit du garage (dalle monopente, léger débord)
    bm = bmesh.new()
    o = 0.25
    gx0, gx1 = x0 - o, x1 + o
    profile = [(gx0, top_z(max(x0, min(x1, gx0)))), (gx1, top_z(max(x0, min(x1, gx1))))]
    t = 0.12
    tf = [bm.verts.new((x, -o, z)) for x, z in profile]
    tb = [bm.verts.new((x, g_d + o, z)) for x, z in profile]
    bf = [bm.verts.new((x, -o, z - t)) for x, z in profile]
    bb = [bm.verts.new((x, g_d + o, z - t)) for x, z in profile]
    bm.faces.new([tf[0], tf[1], tb[1], tb[0]])
    bm.faces.new([bb[0], bb[1], bf[1], bf[0]])
    bm.faces.new([tf[0], tb[0], bb[0], bf[0]])
    bm.faces.new([tb[1], tf[1], bf[1], bb[1]])
    bm.faces.new([tf[1], tf[0], bf[0], bf[1]])
    bm.faces.new([tb[0], tb[1], bb[1], bb[0]])
    mat_roof = _simple_material("House_Garage_Roof", (0.35, 0.33, 0.32), roughness=0.85)
    roof = _new_mesh_obj("Garage_Roof", bm, collection, "garage", mat_roof)

    # Porte sectionnelle (panneaux horizontaux)
    bm = bmesh.new()
    n_panels = 4
    ph = door_h / n_panels
    for i in range(n_panels):
        z0 = i * ph + 0.01
        z1 = (i + 1) * ph - 0.01
        _add_box(bm, dx0 + 0.03, wall_t * 0.35, z0, dx1 - 0.03, wall_t * 0.65, z1)
    mat_door = _simple_material("House_Garage_Door", (0.88, 0.88, 0.86), roughness=0.5)
    door = _new_mesh_obj("Garage_Door", bm, collection, "garage", mat_door)

    print(f"[House] ✓ Garage {g_w:.1f}×{g_d:.1f}m ({'droite' if on_right else 'gauche'}) + porte sectionnelle")
    return [walls, roof, door]


# ============================================================
# BALCON + RAMBARDE
# ============================================================

def build_balcony(props, collection, floor_height_actual):
    """Balcon au 1er étage, centré sur la façade, avec rambarde à poteaux."""
    width = props.house_width

    b_w = min(getattr(props, 'balcony_width', 2.6), width * 0.5)
    b_d = getattr(props, 'balcony_depth', 1.3)
    slab_t = 0.15
    rail_h = 1.0
    post_s = 0.05

    z0 = floor_height_actual          # niveau du plancher de l'étage
    x0 = width / 2 - b_w / 2
    y0 = -b_d                         # en saillie sur la façade avant

    bm = bmesh.new()
    # Dalle
    _add_box(bm, x0, y0, z0 - slab_t, x0 + b_w, 0.02, z0)
    # Poteaux (avant + retours latéraux)
    n_posts = max(2, int(b_w / 0.45))
    for i in range(n_posts + 1):
        px = x0 + i * (b_w - post_s) / n_posts
        _add_box(bm, px, y0, z0, px + post_s, y0 + post_s, z0 + rail_h - 0.05)
    for py in (y0 + 0.45, ):
        for px in (x0, x0 + b_w - post_s):
            _add_box(bm, px, py, z0, px + post_s, py + post_s, z0 + rail_h - 0.05)
    # Main courante (avant + 2 côtés)
    _add_box(bm, x0 - 0.02, y0 - 0.02, z0 + rail_h - 0.05, x0 + b_w + 0.02, y0 + post_s + 0.02, z0 + rail_h)
    _add_box(bm, x0 - 0.02, y0, z0 + rail_h - 0.05, x0 + post_s, 0, z0 + rail_h)
    _add_box(bm, x0 + b_w - post_s, y0, z0 + rail_h - 0.05, x0 + b_w + 0.02, 0, z0 + rail_h)

    mat = _simple_material("House_Balcony", (0.9, 0.9, 0.88), roughness=0.6)
    obj = _new_mesh_obj("Balcony", bm, collection, "balcony", mat)
    print(f"[House] ✓ Balcon {b_w:.1f}×{b_d:.1f}m au niveau {z0:.2f}m")
    return [obj]


# ============================================================
# TUILES (COUVERTURE) — via nuage de points + Geometry Nodes
# ============================================================

TILE_W = 0.30      # largeur d'une tuile (le long du faîtage)
TILE_L = 0.36      # longueur (le long de la pente)
TILE_T = 0.022     # épaisseur
TILE_OVERLAP = 0.09


def _create_tile_master(collection, color):
    """✅ V2: Vraie tuile CANAL galbée (profil sinusoïdal, shading lisse)

    Remplace les "2 boîtes" de la v1 (le look Super Nintendo). Grille
    incurvée + jupe d'épaisseur + nez à l'égout, polygones lissés.
    ~200 tris — négligeable puisque le mesh est PARTAGÉ par toutes les
    instances GN.
    """
    w = TILE_W - 0.014       # largeur utile (léger jeu entre colonnes)
    amp = 0.035              # hauteur du galbe
    thick = 0.012            # épaisseur visible de la jupe
    nx, ny = 12, 5           # résolution du profil / de la longueur

    bm = bmesh.new()

    def z_profile(u):
        """Galbe en S doux: creux sur les bords, bombé au centre"""
        return amp * (0.5 - 0.5 * math.cos(2 * math.pi * u)) + 0.35 * amp * math.sin(math.pi * u)

    # Surface supérieure (grille galbée), avec léger relèvement du nez
    top = []
    for iy in range(ny + 1):
        v = iy / ny
        y = v * TILE_L
        nose = 0.010 * (1.0 - v) ** 2  # nez relevé côté égout (y=0)
        row = []
        for ix in range(nx + 1):
            u = ix / nx
            row.append(bm.verts.new((u * w, y, z_profile(u) + nose)))
        top.append(row)
    for iy in range(ny):
        for ix in range(nx):
            bm.faces.new([top[iy][ix], top[iy][ix + 1],
                          top[iy + 1][ix + 1], top[iy + 1][ix]])

    # Jupe d'épaisseur sur le pourtour (bord tombant de `thick`)
    def skirt(va, vb):
        a2 = bm.verts.new((va.co.x, va.co.y, va.co.z - thick))
        b2 = bm.verts.new((vb.co.x, vb.co.y, vb.co.z - thick))
        bm.faces.new([va, vb, b2, a2])
        return a2, b2

    for iy in range(ny):   # côtés gauche/droit
        skirt(top[iy][0], top[iy + 1][0])
        skirt(top[iy + 1][nx], top[iy][nx])
    for ix in range(nx):   # nez (égout) et queue (faîtage)
        skirt(top[0][ix + 1], top[0][ix])
        skirt(top[ny][ix], top[ny][ix + 1])

    mat = _simple_material("House_Tile", color, roughness=0.65)
    obj = _new_mesh_obj("Tile_Master", bm, collection, "roof", mat)

    # ✅ Shading LISSE (l'aspect facetté criait "low-poly")
    for poly in obj.data.polygons:
        poly.use_smooth = True

    obj.hide_render = True
    try:
        obj.hide_set(True)
    except RuntimeError:
        pass
    return obj


def build_roof_tiles(props, collection, wall_height, effective_pitch, o_eave, o_rake):
    """Pose des tuiles instanciées (GN) sur les pans GABLE et SHED.

    Même architecture que les briques: positions+rotations calculées en
    Python, matérialisées par UN objet nuage de points + Instance on Points.
    """
    # Seed déterministe: mêmes micro-variations à chaque régénération
    random.seed(42)

    roof_type = props.roof_type
    if roof_type not in ('GABLE', 'SHED'):
        print(f"[House] Tuiles: non supporté pour {roof_type} (GABLE/SHED seulement pour l'instant)")
        return []

    width = props.house_width
    length = props.house_length
    pitch_rad = math.radians(effective_pitch)
    h = wall_height

    positions = []  # (Vector pos, Euler rot)
    step_v = TILE_L - TILE_OVERLAP           # pas le long de la pente
    step_u = TILE_W                          # pas le long du faîtage
    lift = 0.02                              # au-dessus de la surface du toit

    def cover_slope(origin, dir_u, dir_v, len_u, len_v, rot):
        """Grille de tuiles sur un pan: origin à l'égout, v monte la pente

        ✅ FIX 1: Clamp au faîtage (la dernière rangée ne déborde plus sur
        l'autre versant).
        ✅ FIX 2: Décalage NORMAL progressif par rangée — les rangées se
        chevauchent dans le MÊME plan → faces coplanaires (bandes sombres
        de z-fighting). Chaque rangée monte de 4mm: effet d'écailles réel.
        """
        n_u = int(len_u / step_u)
        normal = dir_u.cross(dir_v).normalized()
        if normal.z < 0:
            normal = -normal
        iv = 0
        while iv * step_v + TILE_L <= len_v + 0.03 + 1e-6:
            row_lift = normal * (iv * 0.004)
            for iu in range(n_u):
                p = origin + dir_u * (iu * step_u) + dir_v * (iv * step_v) + row_lift
                # ✅ V2: Micro-variation par tuile (pose imparfaite réelle)
                # — l'alignement parfait criait "généré par ordinateur"
                j = math.radians(0.8)
                r = Euler((rot.x + random.uniform(-j, j),
                           rot.y + random.uniform(-j, j),
                           rot.z + random.uniform(-j, j)), 'XYZ')
                p = p + normal * random.uniform(0, 0.003)
                positions.append((p, r))
            iv += 1

    if roof_type == 'SHED':
        # Un seul pan: monte de x=0 vers x=width (plan par la façade à z=h)
        slope = math.tan(pitch_rad)
        slope_len = math.sqrt((width + 2 * o_eave) ** 2 + ((width + 2 * o_eave) * slope) ** 2)
        dir_v = Vector((math.cos(pitch_rad), 0, math.sin(pitch_rad)))
        dir_u = Vector((0, 1, 0))
        z_eave = h - o_eave * slope
        origin = Vector((-o_eave, -o_rake, z_eave + lift))
        rot = Euler((0, -pitch_rad, math.radians(90)), 'XYZ')
        cover_slope(origin, dir_u, dir_v, length + 2 * o_rake, slope_len, rot)
    else:
        # GABLE: 2 pans, faîtage selon la grande dimension
        ridge_along_y = length >= width
        if ridge_along_y:
            half = width / 2
            slope_len = (half + o_eave) / math.cos(pitch_rad)
            z_eave = h - o_eave * math.tan(pitch_rad)
            # Pan gauche (monte vers +X)
            cover_slope(Vector((-o_eave, -o_rake, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((math.cos(pitch_rad), 0, math.sin(pitch_rad))),
                        length + 2 * o_rake, slope_len,
                        Euler((0, -pitch_rad, math.radians(90)), 'XYZ'))
            # Pan droit (monte vers -X)
            cover_slope(Vector((width + o_eave, -o_rake, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((-math.cos(pitch_rad), 0, math.sin(pitch_rad))),
                        length + 2 * o_rake, slope_len,
                        Euler((0, pitch_rad, math.radians(90)), 'XYZ'))
        else:
            half = length / 2
            slope_len = (half + o_eave) / math.cos(pitch_rad)
            z_eave = h - o_eave * math.tan(pitch_rad)
            # Pan avant (monte vers +Y)
            cover_slope(Vector((-o_rake, -o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, math.cos(pitch_rad), math.sin(pitch_rad))),
                        width + 2 * o_rake, slope_len,
                        Euler((pitch_rad, 0, 0), 'XYZ'))
            # Pan arrière (monte vers -Y)
            cover_slope(Vector((-o_rake, length + o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, -math.cos(pitch_rad), math.sin(pitch_rad))),
                        width + 2 * o_rake, slope_len,
                        Euler((-pitch_rad, 0, math.radians(0)), 'XYZ'))

    if not positions:
        return []

    tile_color = tuple(getattr(props, 'tile_color', (0.45, 0.2, 0.14)))[:3]
    master = _create_tile_master(collection, tile_color)

    # ✅ NOUVEAU: FAÎTIÈRES — demi-rond couvrant la jonction des deux pans
    ridge_objs = []
    if roof_type == 'GABLE':
        ridge_along_y = length >= width
        peak_h = h + ((width / 2) if ridge_along_y else (length / 2)) * math.tan(pitch_rad)
        bm = bmesh.new()
        if ridge_along_y:
            ridge_len = length + 2 * o_rake
            seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                        radius1=0.11, radius2=0.11, depth=ridge_len)
            bmesh.ops.transform(bm, verts=seg['verts'],
                                matrix=Matrix.Translation(Vector((width / 2, length / 2, peak_h + 0.03))) @
                                Matrix.Rotation(math.radians(90), 4, 'X'))
        else:
            ridge_len = width + 2 * o_rake
            seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                        radius1=0.11, radius2=0.11, depth=ridge_len)
            bmesh.ops.transform(bm, verts=seg['verts'],
                                matrix=Matrix.Translation(Vector((width / 2, length / 2, peak_h + 0.03))) @
                                Matrix.Rotation(math.radians(90), 4, 'Y'))
        mat = _simple_material("House_Tile", tile_color, roughness=0.75)
        ridge = _new_mesh_obj("Roof_Ridge", bm, collection, "roof", mat)
        ridge_objs.append(ridge)

    # Nuage de points + node group (même mécanique que les briques GN)
    mesh = bpy.data.meshes.new("Roof_Tiles_Points")
    mesh.from_pydata([tuple(p) for p, _r in positions], [], [])
    mesh.update()
    attr = mesh.attributes.new("tile_rot", 'FLOAT_VECTOR', 'POINT')
    flat = []
    for _p, r in positions:
        flat.extend((r.x, r.y, r.z))
    attr.data.foreach_set('vector', flat)

    obj = bpy.data.objects.new("Roof_Tiles", mesh)
    obj["house_part"] = "roof"
    collection.objects.link(obj)

    ng = bpy.data.node_groups.new("House_Tile_Instancer", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n_in = ng.nodes.new('NodeGroupInput')
    n_pts = ng.nodes.new('GeometryNodeMeshToPoints'); n_pts.mode = 'VERTICES'
    n_obj = ng.nodes.new('GeometryNodeObjectInfo')
    n_obj.transform_space = 'ORIGINAL'
    n_obj.inputs['Object'].default_value = master
    if 'As Instance' in n_obj.inputs:
        n_obj.inputs['As Instance'].default_value = True
    n_attr = ng.nodes.new('GeometryNodeInputNamedAttribute')
    n_attr.data_type = 'FLOAT_VECTOR'
    n_attr.inputs['Name'].default_value = "tile_rot"
    n_inst = ng.nodes.new('GeometryNodeInstanceOnPoints')
    n_out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(n_in.outputs['Geometry'], n_pts.inputs['Mesh'])
    ng.links.new(n_pts.outputs['Points'], n_inst.inputs['Points'])
    ng.links.new(n_obj.outputs['Geometry'], n_inst.inputs['Instance'])
    ng.links.new(n_attr.outputs['Attribute'], n_inst.inputs['Rotation'])
    ng.links.new(n_inst.outputs['Instances'], n_out.inputs['Geometry'])

    mod = obj.modifiers.new("TileInstancer", 'NODES')
    mod.node_group = ng

    print(f"[House] ✓ Couverture: {len(positions):,} tuiles instanciées (GN)")
    return [obj, master] + ridge_objs


# ============================================================
# VOLETS
# ============================================================

def build_shutters(props, collection, window_specs):
    """Volets battants ouverts de part et d'autre de chaque fenêtre.

    window_specs: liste de dicts {x, y, z_center, width, height, wall}
    (fournie par l'opérateur — mêmes valeurs que les fenêtres visuelles)
    """
    if not window_specs:
        return []

    mat = _simple_material("House_Shutter", (0.25, 0.35, 0.42), roughness=0.6)
    bm = bmesh.new()
    t = 0.035  # épaisseur du volet

    for spec in window_specs:
        w = spec['width'] / 2 - 0.02   # chaque volet = moitié de la fenêtre
        hgt = spec['height']
        z0 = spec['z_center'] - hgt / 2
        z1 = spec['z_center'] + hgt / 2
        wall = spec['wall']

        if wall in ('front', 'back'):
            y = spec['y'] + (-t if wall == 'front' else 0)
            for side in (-1, 1):
                x_in = spec['x'] + side * (spec['width'] / 2 + 0.03)
                x_out = x_in + side * w
                _add_box(bm, min(x_in, x_out), y, z0, max(x_in, x_out), y + t, z1)
        else:
            x = spec['x'] + (-t if wall == 'left' else 0)
            for side in (-1, 1):
                y_in = spec['y'] + side * (spec['width'] / 2 + 0.03)
                y_out = y_in + side * w
                _add_box(bm, x, min(y_in, y_out), z0, x + t, max(y_in, y_out), z1)

    obj = _new_mesh_obj("Shutters", bm, collection, "shutter", mat)
    print(f"[House] ✓ Volets: {len(window_specs)} paires")
    return [obj]
