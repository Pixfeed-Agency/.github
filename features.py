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
    """✅ V2: Cheminée maçonnée complète — fût en briques (Brick Texture
    à l'échelle réelle), SOLIN zinc au passage du toit, couronnement
    béton débordant avec goutte d'eau, deux boisseaux terre cuite.

    Args:
        wall_height: sommet des murs (hauteur réelle)
        roof_peak_z: altitude du faîtage (pour dépasser du toit)
    """
    width = props.house_width
    length = props.house_length

    cw, cd = 0.92, 0.60              # fût rectangulaire (double conduit)
    top = roof_peak_z + 0.55         # dépasse le faîtage (règle: +40cm min)
    if props.roof_type == 'FLAT':
        top = wall_height + 0.30 + 0.45 + 0.65  # au-dessus de l'acrotère
    base = wall_height - 1.2         # ancrée sous le toit

    # ✅ v1.6: position, hauteur de toit et angle de solin EXACTS par
    # type de toit (avant: maths GABLE appliquées partout)
    ridge_along_y = length >= width
    rtype = props.roof_type
    h0 = wall_height

    if rtype == 'GABLE':
        half = (width / 2) if ridge_along_y else (length / 2)
        slope = max(0.0, (roof_peak_z - h0) / max(half, 0.01))
        pitch = math.atan(slope)
        if ridge_along_y:
            cx = width / 2 + 0.9
            cy = length * 0.3
            z_roof = h0 + slope * (width - cx)
            flash_rot = Matrix.Rotation(pitch, 4, 'Y')
        else:
            cx = width * 0.3
            cy = length / 2 + 0.9
            z_roof = h0 + slope * (length - cy)
            flash_rot = Matrix.Rotation(-pitch, 4, 'X')
    elif rtype == 'HIP':
        half = min(width, length) / 2
        slope = max(0.0, (roof_peak_z - h0) / max(half, 0.01))
        pitch = math.atan(slope)
        # clampée sur la PARTIE TRAPÉZOÏDALE (le long du faîtage)
        if ridge_along_y:
            r0, r1 = width / 2, length - width / 2
            cy = max(r0 + 0.8, min(r1 - 0.8, length * 0.3))
            cx = width / 2 + 0.9
            z_roof = roof_peak_z - slope * 0.9
            flash_rot = Matrix.Rotation(pitch, 4, 'Y')
        else:
            r0, r1 = length / 2, width - length / 2
            cx = max(r0 + 0.8, min(r1 - 0.8, width * 0.3))
            cy = length / 2 + 0.9
            z_roof = roof_peak_z - slope * 0.9
            flash_rot = Matrix.Rotation(-pitch, 4, 'X')
    elif rtype == 'SHED':
        slope = max(0.0, (roof_peak_z - h0) / max(width, 0.01))
        pitch = math.atan(slope)
        cx = width * 0.7
        cy = length * 0.3
        z_roof = h0 + slope * cx
        flash_rot = Matrix.Rotation(-pitch, 4, 'Y')
    elif rtype == 'GAMBREL':
        brisis_rad = math.radians(68.0)
        bd = (width / 2) * 0.25
        bh = bd * math.tan(brisis_rad)
        terr_slope = max(0.0, (roof_peak_z - h0 - bh) / max(width / 2 - bd, 0.01))
        pitch = math.atan(terr_slope)
        slope = terr_slope
        cx = min(width / 2 + 0.9, width - bd - 0.3)
        cy = length * 0.3
        z_roof = h0 + bh + terr_slope * (width - bd - cx)
        flash_rot = Matrix.Rotation(pitch, 4, 'Y')
    else:  # FLAT
        pitch = 0.0
        slope = 0.0
        cx = width * 0.3
        cy = length / 2
        z_roof = h0 + 0.30
        flash_rot = Matrix.Identity(4)

    objs = []

    # --- FÛT en briques ---
    bm = bmesh.new()
    _add_box(bm, cx - cw / 2, cy - cd / 2, base, cx + cw / 2, cy + cd / 2, top)
    try:
        from . import look
        brick_mat = look.chimney_brick_material(
            tuple(getattr(props, 'mortar_color', (0.72, 0.69, 0.64)))[:3])
    except Exception:
        brick_mat = _simple_material("House_Chimney_Brick", (0.30, 0.085, 0.05),
                                     roughness=0.9)
    objs.append(_new_mesh_obj("Chimney", bm, collection, "chimney", brick_mat))

    # --- SOLIN zinc (collerette inclinée épousant le versant) ---
    bm = bmesh.new()
    sk = 0.20                        # débord du solin autour du fût
    plate = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, verts=plate['verts'],
                        matrix=Matrix.Diagonal((cw + 2 * sk, cd + 2 * sk, 0.012, 1.0)))
    bmesh.ops.transform(bm, verts=bm.verts,
                        matrix=Matrix.Translation(Vector((cx, cy, z_roof + 0.03))) @ flash_rot)
    zinc = _simple_material("House_Zinc", (0.62, 0.65, 0.67), roughness=0.35,
                            metallic=0.9)
    objs.append(_new_mesh_obj("Chimney_Flashing", bm, collection, "chimney", zinc))

    # --- COURONNEMENT béton (dalle débordante + goutte d'eau) ---
    bm = bmesh.new()
    cap = 0.07
    _add_box(bm, cx - cw / 2 - cap, cy - cd / 2 - cap, top,
             cx + cw / 2 + cap, cy + cd / 2 + cap, top + 0.10)
    _add_box(bm, cx - cw / 2 - cap + 0.02, cy - cd / 2 - cap + 0.02, top + 0.10,
             cx + cw / 2 + cap - 0.02, cy + cd / 2 + cap - 0.02, top + 0.14)
    concrete = _simple_material("House_Concrete_Cap", (0.58, 0.57, 0.54),
                                roughness=0.85)
    objs.append(_new_mesh_obj("Chimney_Cap", bm, collection, "chimney", concrete))

    # --- BOISSEAUX terre cuite (2 conduits) ---
    bm = bmesh.new()
    pot_mat = _simple_material("House_Chimney_Pot", (0.36, 0.14, 0.08),
                               roughness=0.7)
    for dx in (-cw / 4, cw / 4):
        pot = bmesh.ops.create_cone(bm, cap_ends=False, segments=14,
                                    radius1=0.105, radius2=0.09, depth=0.34)
        bmesh.ops.transform(bm, verts=pot['verts'],
                            matrix=Matrix.Translation(Vector((cx + dx, cy,
                                                              top + 0.14 + 0.17))))
        # assombrir l'intérieur: petit cylindre noir
        hole = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                     radius1=0.075, radius2=0.075, depth=0.02)
        bmesh.ops.transform(bm, verts=hole['verts'],
                            matrix=Matrix.Translation(Vector((cx + dx, cy,
                                                              top + 0.14 + 0.30))))
    objs.append(_new_mesh_obj("Chimney_Pots", bm, collection, "chimney", pot_mat))

    print(f"[House] ✓ Cheminée V2 à ({cx:.1f}, {cy:.1f}) — fût briques + "
          f"solin + couronnement + boisseaux")
    return objs


# ============================================================
# GOUTTIÈRES + DESCENTES
# ============================================================

def _split_interval(t0, t1, exclusions):
    """Découpe [t0,t1] en segments hors des intervalles d'exclusion."""
    segs = [(t0, t1)]
    for (e0, e1) in (exclusions or []):
        out = []
        for (s0, s1) in segs:
            if e1 <= s0 or e0 >= s1:
                out.append((s0, s1))
                continue
            if e0 > s0 + 0.05:
                out.append((s0, e0))
            if e1 < s1 - 0.05:
                out.append((e1, s1))
        segs = out
    return segs


def build_gutters(props, collection, eave_z_left, eave_z_right, o_eave, o_rake,
                  eave_exclusions=None):
    """Gouttières le long des égouts + descentes aux angles.

    Gère GABLE (2 égouts), SHED (égout bas + haut), HIP (4), GAMBREL (2).
    eave_z_left/right: altitude de l'égout de chaque côté (SHED: différents).
    """
    width = props.house_width
    length = props.house_length
    roof_type = props.roof_type
    ex = eave_exclusions or {}

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

    if roof_type == 'SHED':
        # ✅ v1.6: monopente — gouttière UNIQUEMENT à l'égout BAS (l'eau
        # ne coule pas vers le haut); la tête reçoit un bandeau (charpente)
        y0, y1 = -o_rake, length + o_rake
        gutter_run((-o_eave, y0, eave_z_left - r), (-o_eave, y1, eave_z_left - r))
        downspout(-down_r - 0.01, 0.35, eave_z_left - r)
    elif roof_type == 'GAMBREL' or (roof_type == 'GABLE' and ridge_along_y):
        # Égouts sur les côtés X (gauche/droit) — ✅ v1.7: segments
        # DÉCOUPÉS autour des ailes (plus de tronçon caché dans le comble)
        y0, y1 = -o_rake, length + o_rake
        for (s0, s1) in _split_interval(y0, y1, ex.get('left')):
            gutter_run((-o_eave, s0, eave_z_left - r), (-o_eave, s1, eave_z_left - r))
        for (s0, s1) in _split_interval(y0, y1, ex.get('right')):
            gutter_run((width + o_eave, s0, eave_z_right - r), (width + o_eave, s1, eave_z_right - r))
        downspout(-down_r - 0.01, 0.35, eave_z_left - r)
        downspout(width + down_r + 0.01, length - 0.35, eave_z_right - r)
    elif roof_type == 'GABLE':
        # Faîtage en X → égouts sur les côtés Y (avant/arrière)
        x0, x1 = -o_rake, width + o_rake
        for (s0, s1) in _split_interval(x0, x1, ex.get('front')):
            gutter_run((s0, -o_eave, eave_z_left - r), (s1, -o_eave, eave_z_left - r))
        for (s0, s1) in _split_interval(x0, x1, ex.get('back')):
            gutter_run((s0, length + o_eave, eave_z_right - r), (s1, length + o_eave, eave_z_right - r))
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
    # ✅ FIX Z-FIGHTING: le mur s'arrête ENTRE la façade et le mur arrière
    # (avant: recouvrement aux angles → faces coplanaires → bandes noires)
    ox = x1 - wall_t if on_right else x0
    _add_box(bm, ox, wall_t, 0, ox + wall_t, g_d - wall_t, top_z(ox + wall_t / 2))
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

    # ✅ ARTICULATION: porte sectionnelle OUVRABLE — propriété 'ouverture'
    # (0=fermée, 1=ouverte) pilotant la montée par driver
    door["ouverture"] = 0.0
    try:
        ui = door.id_properties_ui("ouverture")
        ui.update(min=0.0, max=1.0, description="0 = fermée, 1 = ouverte (monte)")
    except Exception:
        pass
    fcu = door.driver_add('location', 2)
    drv = fcu.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'o'
    var.type = 'SINGLE_PROP'
    var.targets[0].id = door
    var.targets[0].data_path = '["ouverture"]'
    drv.expression = f'o * {door_h - 0.15:.3f}'

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


ROOF_WIN_W = 0.78   # largeur fenêtre de toit (standard 78×118)
ROOF_WIN_L = 1.18   # longueur le long de la pente


def roof_window_layout(props, wall_height, effective_pitch, o_eave, o_rake):
    """NOTE v1.8: retourne (pan, centres, u_axis, v_axis, origin, exc)
    où exc = (half_u, v_lo_rel, v_hi_rel) est le rectangle d'exclusion
    des tuiles AUTOUR de chaque centre (relatif à v_center)."""
    """Calepinage PARTAGÉ des fenêtres de toit (tuiles + objets).

    GABLE uniquement. Elles sont posées sur le pan "visible":
    faîtage en X → pan AVANT (y-), faîtage en Y → pan GAUCHE (x-).
    Returns: (pan, [(u_center, v_center)], u_axis, v_axis, origin) ou None
        pan ∈ {'front', 'left'}; u le long de l'égout, v monte la pente.
    """
    n = int(getattr(props, 'num_roof_windows', 0))
    if props.roof_type not in ('GABLE', 'SHED', 'HIP', 'GAMBREL') or \
            not getattr(props, 'include_roof_windows', False) or n <= 0:
        return None
    width, length = props.house_width, props.house_length
    pitch_rad = math.radians(effective_pitch)
    cosp, sinp = math.cos(pitch_rad), math.sin(pitch_rad)
    h = wall_height
    slope = math.tan(pitch_rad)
    z_eave = h - o_eave * slope
    ridge_along_y = length >= width

    if props.roof_type == 'HIP':
        # ✅ v1.7: velux sur le pan TRAPÉZOÏDAL visible, centres clampés
        # entre les arêtiers (coupe 45°)
        if ridge_along_y:
            pan = 'hip_left'
            u_len = length + 2 * o_eave
            slope_len = (width / 2 + o_eave) / cosp
            origin = Vector((-o_eave, -o_eave, z_eave))
            u_axis = Vector((0, 1, 0))
            v_axis = Vector((cosp, 0, sinp))
        else:
            pan = 'hip_front'
            u_len = width + 2 * o_eave
            slope_len = (length / 2 + o_eave) / cosp
            origin = Vector((-o_eave, -o_eave, z_eave))
            u_axis = Vector((1, 0, 0))
            v_axis = Vector((0, cosp, sinp))
        if slope_len < ROOF_WIN_L + 0.9:
            print("[House] Fenêtres de toit: pan trop court — ignorées")
            return None
        v_center = max(ROOF_WIN_L / 2 + 0.35,
                       min(slope_len - ROOF_WIN_L / 2 - 0.45, slope_len * 0.45))
        d_need = (v_center + ROOF_WIN_L / 2) * cosp + 0.35
        u0, u1 = d_need, u_len - d_need
        if u1 - u0 < ROOF_WIN_W:
            print("[House] Fenêtres de toit: trapèze trop resserré — ignorées")
            return None
        n_fit = min(n, max(1, int((u1 - u0) / (ROOF_WIN_W + 0.6))))
        centers = [(u0 + (i + 1) * (u1 - u0) / (n_fit + 1), v_center)
                   for i in range(n_fit)]
        exc = (ROOF_WIN_W / 2 + 0.16, -ROOF_WIN_L / 2 - 0.16, ROOF_WIN_L / 2 + 0.16)
        return pan, centers, u_axis, v_axis, origin, exc

    if props.roof_type == 'GAMBREL':
        # ✅ v1.7: velux sur le TERRASSON gauche (pente douce)
        brisis_rad = math.radians(68.0)
        bd = (width / 2) * 0.25
        bh = bd * math.tan(brisis_rad)
        pan = 'gambrel_terr_left'
        u_len = length + 2 * o_rake
        terr_len = (width / 2 - bd) / cosp
        origin = Vector((bd, -o_rake, h + bh))
        u_axis = Vector((0, 1, 0))
        v_axis = Vector((cosp, 0, sinp))
        if terr_len < ROOF_WIN_L + 0.7:
            print("[House] Fenêtres de toit: terrasson trop court — ignorées")
            return None
        v_center = max(ROOF_WIN_L / 2 + 0.25,
                       min(terr_len - ROOF_WIN_L / 2 - 0.25, terr_len * 0.45))
        centers = [((i + 1) * u_len / (n + 1), v_center) for i in range(n)]
        exc = (ROOF_WIN_W / 2 + 0.16, -ROOF_WIN_L / 2 - 0.16, ROOF_WIN_L / 2 + 0.16)
        return pan, centers, u_axis, v_axis, origin, exc

    if props.roof_type == 'SHED':
        pan = 'shed'
        u_len = length + 2 * o_rake
        slope_len = (width + 2 * o_eave) / cosp
        origin = Vector((-o_eave, -o_rake, z_eave))
        u_axis = Vector((0, 1, 0))
        v_axis = Vector((cosp, 0, sinp))
    elif ridge_along_y:
        pan = 'left'
        u_len = length + 2 * o_rake
        slope_len = (width / 2 + o_eave) / cosp
        origin = Vector((-o_eave, -o_rake, z_eave))
        u_axis = Vector((0, 1, 0))
        v_axis = Vector((cosp, 0, sinp))
    else:
        pan = 'front'
        u_len = width + 2 * o_rake
        slope_len = (length / 2 + o_eave) / cosp
        origin = Vector((-o_rake, -o_eave, z_eave))
        u_axis = Vector((1, 0, 0))
        v_axis = Vector((0, cosp, sinp))
    if slope_len < ROOF_WIN_L + 0.8:
        print("[House] Fenêtres de toit: pan trop court — ignorées")
        return None
    # ✅ v1.8: LUCARNES jacobines sur GABLE (style au choix)
    style = getattr(props, 'roof_window_style', 'VELUX')
    if style == 'LUCARNE' and props.roof_type == 'GABLE':
        cosp_l = math.cos(pitch_rad)
        lw, dd = 1.5, 1.6
        v_center = max((dd / 2 + 0.5) / cosp_l,
                       min(slope_len - 1.2, slope_len * 0.42))
        y_c = v_center * cosp_l
        y_f = y_c - dd / 2
        z_b = math.tan(pitch_rad) * y_f
        z_w = z_b + 1.45
        dp = math.radians(max(effective_pitch, 35.0))
        z_r = z_w + (lw / 2) * math.tan(dp)
        y_back = z_r / max(math.tan(pitch_rad), 0.05)
        centers = [((i + 1) * u_len / (n + 1), v_center) for i in range(n)]
        # exclusion resserrée: derrière la lucarne, le toiton recouvre
        # lui-même le pan jusqu'à sa ligne de pénétration
        y_cover = z_w / max(math.tan(pitch_rad), 0.05) + 0.30
        exc = (lw / 2 + 0.14,
               (y_f - 0.2) / cosp_l - v_center,
               min(y_cover / cosp_l, slope_len) - v_center)
        return pan, centers, u_axis, v_axis, origin, exc

    v_center = max(ROOF_WIN_L / 2 + 0.35,
                   min(slope_len - ROOF_WIN_L / 2 - 0.35, slope_len * 0.45))
    centers = [((i + 1) * u_len / (n + 1), v_center) for i in range(n)]
    exc = (ROOF_WIN_W / 2 + 0.16, -ROOF_WIN_L / 2 - 0.16, ROOF_WIN_L / 2 + 0.16)
    return pan, centers, u_axis, v_axis, origin, exc


def build_roof_windows(props, collection, wall_height, effective_pitch,
                       o_eave, o_rake):
    """✅ v1.5: FENÊTRES DE TOIT (type velux) posées sur le pan.

    Cadre + battant vitré légèrement saillant + solin zinc périphérique.
    Les tuiles sont exclues de l'emprise par build_roof_tiles (même
    calepinage partagé).
    """
    layout = roof_window_layout(props, wall_height, effective_pitch,
                                o_eave, o_rake)
    if layout is None:
        return []
    if getattr(props, 'roof_window_style', 'VELUX') == 'LUCARNE' and \
            props.roof_type == 'GABLE':
        return build_roof_dormers(props, collection, wall_height,
                                  effective_pitch, o_eave, o_rake, layout)
    pan, centers, u_axis, v_axis, origin = layout[:5]
    normal = u_axis.cross(v_axis).normalized()
    if normal.z < 0:
        normal = -normal

    frame_mat = _simple_material("House_RoofWin_Frame", (0.28, 0.28, 0.30),
                                 roughness=0.5)
    zinc = _simple_material("House_Zinc", (0.62, 0.65, 0.67), roughness=0.35,
                            metallic=0.9)
    glass = None
    try:
        from . import look
        glass = look.glass_material()
    except Exception:
        glass = _simple_material("House_Glass_Roof", (0.4, 0.5, 0.55),
                                 roughness=0.05)

    hw, hl = ROOF_WIN_W / 2, ROOF_WIN_L / 2
    bm_f = bmesh.new()
    bm_g = bmesh.new()
    bm_z = bmesh.new()

    def box_on_plane(bm, uc, vc, du, dv, off, th):
        """Boîte alignée sur le pan: demi-tailles du×dv, décollée de off,
        épaisseur th (le long de la normale)."""
        c = origin + u_axis * uc + v_axis * vc + normal * (off + th / 2)
        rot = Matrix((u_axis, v_axis, normal)).transposed().to_4x4()
        b = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.transform(bm, verts=b['verts'],
                            matrix=Matrix.Diagonal((du * 2, dv * 2, th, 1.0)))
        bmesh.ops.transform(bm, verts=b['verts'],
                            matrix=Matrix.Translation(c) @ rot)

    for uc, vc in centers:
        # Solin périphérique (plaque zinc sous le cadre)
        box_on_plane(bm_z, uc, vc, hw + 0.12, hl + 0.12, 0.015, 0.012)
        # Cadre (4 côtés)
        t, th = 0.06, 0.09
        box_on_plane(bm_f, uc, vc - hl + t / 2, hw, t / 2, 0.03, th)
        box_on_plane(bm_f, uc, vc + hl - t / 2, hw, t / 2, 0.03, th)
        box_on_plane(bm_f, uc - hw + t / 2, vc, t / 2, hl - t, 0.03, th)
        box_on_plane(bm_f, uc + hw - t / 2, vc, t / 2, hl - t, 0.03, th)
        # Vitrage
        box_on_plane(bm_g, uc, vc, hw - t, hl - t, 0.085, 0.012)

    objs = [
        _new_mesh_obj("Roof_Windows_Flashing", bm_z, collection, "roof_window", zinc),
        _new_mesh_obj("Roof_Windows_Frame", bm_f, collection, "roof_window", frame_mat),
    ]
    g = _new_mesh_obj("Roof_Windows_Glass", bm_g, collection, "roof_window", glass)
    objs.append(g)
    print(f"[House] ✓ {len(centers)} fenêtre(s) de toit posée(s) (pan {pan})")
    return objs


def build_roof_dormers(props, collection, wall_height, effective_pitch,
                       o_eave, o_rake, layout):
    """✅ v1.8: LUCARNES JACOBINES — vraie lucarne à 2 pans: façade
    verticale avec fenêtre, jouées triangulaires, toiton à 2 pans coupé
    EXACTEMENT au plan du toit principal (bisect), tuiles du toiton
    ajustées, faîtière arrêtée au point de pénétration analytique.
    """
    pan, centers, u_axis, v_axis, origin, _exc = layout
    pitch_rad = math.radians(effective_pitch)
    cosp, sinp = math.cos(pitch_rad), math.sin(pitch_rad)
    tanp = math.tan(pitch_rad)

    # Repère F du pan: X = u (horizontal le long de l'égout),
    # Y = horizontal vers l'intérieur du toit, Z = vertical
    dir_h = Vector((v_axis.x, v_axis.y, 0)).normalized()
    up = Vector((0, 0, 1))
    M3 = Matrix((u_axis, dir_h, up)).transposed()
    MF = Matrix.Translation(origin) @ M3.to_4x4()
    normal_main = u_axis.cross(v_axis).normalized()
    if normal_main.z < 0:
        normal_main = -normal_main

    lw, dd = 1.5, 1.6
    dp = math.radians(max(effective_pitch, 35.0))
    tan_dp = math.tan(dp)

    wall_mat = _simple_material("House_Dormer_Wall", (0.88, 0.85, 0.78),
                                roughness=0.85)
    tile_color = tuple(getattr(props, 'tile_color', (0.34, 0.115, 0.062)))[:3]
    tile_mat = _simple_material("House_Tile", tile_color, roughness=0.75)
    fascia_mat = _simple_material("House_Fascia", (0.92, 0.92, 0.90),
                                  roughness=0.5)
    objs = []
    positions = []
    random.seed(777)
    step_v = TILE_L - TILE_OVERLAP
    delta = math.atan2(0.014, step_v)

    try:
        from .windows import WindowGenerator
        wgen = WindowGenerator(quality=getattr(props, 'window_quality', 'MEDIUM'))
    except Exception:
        wgen = None

    orientation = {'front': 'front', 'left': 'left'}.get(pan, 'front')

    for (uc, vc) in centers:
        y_c = vc * cosp
        y_f = y_c - dd / 2
        z_b = tanp * y_f
        z_w = z_b + 1.45
        z_r = z_w + (lw / 2) * tan_dp
        y_back = z_r / max(tanp, 0.05)

        bm = bmesh.new()
        # --- FAÇADE de lucarne (trumeaux + allège + linteau autour de la fenêtre)
        wx0, wx1 = uc - lw / 2, uc + lw / 2
        ww, wh = 0.78, 0.95
        ox0, ox1 = uc - ww / 2, uc + ww / 2
        sill = z_b + 0.32
        _add_box(bm, wx0, y_f, z_b - 0.35, ox0, y_f + 0.10, z_w)
        _add_box(bm, ox1, y_f, z_b - 0.35, wx1, y_f + 0.10, z_w)
        _add_box(bm, ox0, y_f, z_b - 0.35, ox1, y_f + 0.10, sill)
        _add_box(bm, ox0, y_f, sill + wh, ox1, y_f + 0.10, z_w)
        # pignon triangulaire de la façade (sous le toiton)
        v = [bm.verts.new(pt) for pt in
             ((wx0, y_f, z_w), (wx1, y_f, z_w), (uc, y_f, z_r),
              (wx0, y_f + 0.10, z_w), (wx1, y_f + 0.10, z_w),
              (uc, y_f + 0.10, z_r))]
        bm.faces.new([v[0], v[1], v[2]])
        bm.faces.new([v[5], v[4], v[3]])
        bm.faces.new([v[0], v[3], v[4], v[1]])
        bm.faces.new([v[1], v[4], v[5], v[2]])
        bm.faces.new([v[2], v[5], v[3], v[0]])

        # --- JOUÉES (murs latéraux triangulaires): dalles verticales
        # coupées par le plan du toit principal ET les plans du toiton
        for sgn in (-1, 1):
            xs = uc + sgn * (lw / 2 - 0.06)
            js = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.transform(bm, verts=js['verts'],
                                matrix=Matrix.Diagonal((0.06, (y_back - y_f) + 0.6,
                                                        z_r + 0.8, 1.0)))
            bmesh.ops.transform(bm, verts=js['verts'],
                                matrix=Matrix.Translation(Vector((
                                    xs + sgn * 0.03, (y_f + y_back) / 2,
                                    z_r / 2))))
        # coupe au plan principal (z = tanp·y): garder AU-DESSUS
        bmesh.ops.bisect_plane(
            bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=(0.0, 0.0, -0.001), plane_no=(0.0, -sinp, cosp),
            clear_outer=False, clear_inner=True)
        # coupes aux plans du toiton: z = z_r ± x'·tan_dp (garder DESSOUS)
        for sgn in (-1, 1):
            no = Vector((sgn * tan_dp, 0.0, 1.0)).normalized()
            bmesh.ops.bisect_plane(
                bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                plane_co=(uc, 0.0, z_r + 0.001), plane_no=tuple(no),
                clear_outer=True, clear_inner=False)
        bmesh.ops.transform(bm, verts=bm.verts, matrix=MF)
        objs.append(_new_mesh_obj("Dormer_Walls", bm, collection, "roof_window",
                                  wall_mat))

        # --- TOITON (2 dallettes) coupé au plan principal ---
        bm = bmesh.new()
        ov = 0.14
        for sgn in (-1, 1):
            x_e = uc + sgn * (lw / 2 + ov)
            z_e = z_r - (lw / 2 + ov) * tan_dp
            xs = sorted([x_e, uc])
            tf = [bm.verts.new((x, y_f - 0.15, z_r - abs(x - uc) * tan_dp))
                  for x in xs]
            tb = [bm.verts.new((x, y_back + 0.5, z_r - abs(x - uc) * tan_dp))
                  for x in xs]
            bf = [bm.verts.new((x, y_f - 0.15, z_r - abs(x - uc) * tan_dp - 0.09))
                  for x in xs]
            bb = [bm.verts.new((x, y_back + 0.5, z_r - abs(x - uc) * tan_dp - 0.09))
                  for x in xs]
            bm.faces.new([tf[0], tf[1], tb[1], tb[0]])
            bm.faces.new([bb[0], bb[1], bf[1], bf[0]])
            bm.faces.new([tf[0], tb[0], bb[0], bf[0]])
            bm.faces.new([tb[1], tf[1], bf[1], bb[1]])
            bm.faces.new([tf[1], tf[0], bf[0], bf[1]])
            bm.faces.new([tb[0], tb[1], bb[1], bb[0]])
        bmesh.ops.bisect_plane(
            bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=(0.0, 0.0, -0.02), plane_no=(0.0, -sinp, cosp),
            clear_outer=False, clear_inner=True)
        bmesh.ops.transform(bm, verts=bm.verts, matrix=MF)
        objs.append(_new_mesh_obj("Dormer_Roof", bm, collection, "roof_window",
                                  fascia_mat))

        # --- TUILES du toiton (petits pans, coupées au plan principal) ---
        for sgn in (-1, 1):
            eave_x = uc + sgn * (lw / 2 + ov)
            up_dir_F = Vector((-sgn * math.cos(dp), 0, math.sin(dp)))
            u_dir_F = Vector((0, 1, 0))
            origin_F = Vector((eave_x, y_f - 0.12,
                               z_r - (lw / 2 + ov) * tan_dp + 0.02))
            dir_u_w = M3 @ u_dir_F
            dir_v_w = M3 @ up_dir_F
            origin_w = MF @ origin_F
            nrm = dir_u_w.cross(dir_v_w).normalized()
            if nrm.z < 0:
                nrm = -nrm
            rot_m = Matrix(((-dir_u_w if sgn > 0 else dir_u_w),
                            dir_v_w, nrm)).transposed()
            tilt = Matrix.Rotation(-delta, 3, dir_u_w)
            base_rot = (tilt @ rot_m).to_euler()
            slope_len_d = (lw / 2 + ov) / math.cos(dp)
            n_u = max(1, int(((y_back + 0.4) - (y_f - 0.12)) / TILE_W))
            iv = 0
            while iv * step_v + TILE_L <= slope_len_d + 0.05:
                for iu in range(n_u):
                    pF = origin_F + Vector((0, iu * TILE_W, 0)) + \
                        up_dir_F * (iv * step_v)
                    pw = MF @ pF
                    # garder si au-dessus du plan principal
                    if (pw - origin).dot(normal_main) < 0.005:
                        continue
                    j = math.radians(0.8)
                    r = Euler((base_rot.x + random.uniform(-j, j),
                               base_rot.y + random.uniform(-j, j),
                               base_rot.z + random.uniform(-j, j)), 'XYZ')
                    positions.append((pw + nrm * 0.008, r))
                iv += 1

        # --- FAÎTIÈRE du toiton (arrêtée au point de pénétration) ---
        bm = bmesh.new()
        p0 = MF @ Vector((uc, y_f - 0.15, z_r + 0.03))
        p1 = MF @ Vector((uc, y_back - 0.02, z_r + 0.03))
        axis = p1 - p0
        if axis.length > 0.05:
            seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                        radius1=0.09, radius2=0.09,
                                        depth=axis.length)
            quat = axis.normalized().to_track_quat('Z', 'Y')
            bmesh.ops.transform(bm, verts=seg['verts'],
                                matrix=Matrix.Translation((p0 + p1) / 2) @
                                quat.to_matrix().to_4x4())
            objs.append(_new_mesh_obj("Dormer_Ridge", bm, collection,
                                      "roof_window", tile_mat))
        else:
            bm.free()

        # --- FENÊTRE de la lucarne ---
        if wgen is not None:
            wc = MF @ Vector((uc, y_f + 0.05, sill + wh / 2))
            try:
                wgen.generate_window(window_type='CASEMENT', width=ww,
                                     height=wh, location=wc,
                                     orientation=orientation,
                                     collection=collection)
            except Exception as e:
                print(f"[House] Fenêtre de lucarne échouée: {e}")

    # nuage GN des tuiles de toiton (master partagé si présent)
    if positions:
        master = None
        for o in collection.objects:
            if o.name.startswith("Tile_Master"):
                master = o
                break
        if master is None:
            master = _create_tile_master(collection, tile_color)
        mesh = bpy.data.meshes.new("Dormer_Tiles_Points")
        mesh.from_pydata([tuple(p) for p, _r in positions], [], [])
        mesh.update()
        attr = mesh.attributes.new("tile_rot", 'FLOAT_VECTOR', 'POINT')
        flat = []
        for _p, r in positions:
            flat.extend((r.x, r.y, r.z))
        attr.data.foreach_set('vector', flat)
        obj = bpy.data.objects.new("Dormer_Tiles", mesh)
        obj["house_part"] = "roof_window"
        collection.objects.link(obj)
        ng = bpy.data.node_groups.new("House_DormerTile_Instancer",
                                      'GeometryNodeTree')
        ng.interface.new_socket("Geometry", in_out='INPUT',
                                socket_type='NodeSocketGeometry')
        ng.interface.new_socket("Geometry", in_out='OUTPUT',
                                socket_type='NodeSocketGeometry')
        n_in = ng.nodes.new('NodeGroupInput')
        n_pts = ng.nodes.new('GeometryNodeMeshToPoints')
        n_pts.mode = 'VERTICES'
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
        objs.append(obj)

    print(f"[House] ✓ {len(centers)} lucarne(s) jacobine(s) posée(s) (pan {pan})")
    return objs


def build_roof_tiles(props, collection, wall_height, effective_pitch, o_eave, o_rake):
    """Pose des tuiles instanciées (GN) sur les pans GABLE et SHED.

    Même architecture que les briques: positions+rotations calculées en
    Python, matérialisées par UN objet nuage de points + Instance on Points.
    """
    # Seed déterministe: mêmes micro-variations à chaque régénération
    random.seed(42)

    roof_type = props.roof_type
    if roof_type not in ('GABLE', 'SHED', 'HIP', 'GAMBREL'):
        print(f"[House] Tuiles: non supporté pour {roof_type}")
        return []

    width = props.house_width
    length = props.house_length
    pitch_rad = math.radians(effective_pitch)
    h = wall_height

    positions = []  # (Vector pos, Euler rot)
    step_v = TILE_L - TILE_OVERLAP           # pas le long de la pente
    step_u = TILE_W                          # pas le long du faîtage
    lift = 0.02                              # au-dessus de la surface du toit

    def cover_slope(origin, dir_u, dir_v, len_u, len_v, rot, keep=None):
        """Grille de tuiles sur un pan: origin à l'égout, v monte la pente

        ✅ FIX 1: Clamp au faîtage (la dernière rangée ne déborde plus sur
        l'autre versant).
        ✅ FIX 2 (v1.4): INCLINAISON DE POSE physique — le nez de chaque
        tuile repose sur la tête de la rangée du dessous, donc chaque
        tuile est MOINS pentue que le toit de δ=atan(épaisseur/pas).
        Les plans des rangées deviennent parallèles non coplanaires (fini
        le z-fighting) SANS le décalage cumulatif qui faisait flotter les
        tuiles jusqu'à 16cm en haut des longues pentes (monopente).
        """
        n_u = int(len_u / step_u)
        normal = dir_u.cross(dir_v).normalized()
        if normal.z < 0:
            normal = -normal
        # Inclinaison de pose: tourne autour de l'axe TRANSVERSAL (dir_u),
        # sens qui SOULÈVE le nez (extrémité -v) de ~1.4cm
        delta = math.atan2(0.014, step_v)
        tilt = Matrix.Rotation(-delta, 3, dir_u)
        rot_m = tilt @ rot.to_matrix()
        base_rot = rot_m.to_euler()
        iv = 0
        while iv * step_v + TILE_L <= len_v + 0.03 + 1e-6:
            for iu in range(n_u):
                p = origin + dir_u * (iu * step_u) + dir_v * (iv * step_v) \
                    + normal * 0.008
                if keep is not None and not keep(p, p + dir_u * TILE_W):
                    continue
                # ✅ V2: Micro-variation par tuile (pose imparfaite réelle)
                # — l'alignement parfait criait "généré par ordinateur"
                j = math.radians(0.8)
                r = Euler((base_rot.x + random.uniform(-j, j),
                           base_rot.y + random.uniform(-j, j),
                           base_rot.z + random.uniform(-j, j)), 'XYZ')
                p = p + normal * random.uniform(0, 0.003)
                positions.append((p, r))
            iv += 1

    # ✅ FIX ORIENTATION: pans qui montent le long de ±X — la tuile doit
    # avoir sa LONGUEUR vers le faîtage et son galbe EN TRAVERS. L'ancien
    # Euler (0,±pitch,90°) la couchait en travers de la pente (tuiles
    # noyées dans la dalle, il ne dépassait que les nez).
    rot_up_x = (Matrix.Rotation(-pitch_rad, 3, 'Y') @
                Matrix.Rotation(math.radians(-90), 3, 'Z')).to_euler()
    rot_down_x = (Matrix.Rotation(pitch_rad, 3, 'Y') @
                  Matrix.Rotation(math.radians(90), 3, 'Z')).to_euler()

    # ✅ v1.5/1.7: exclusion des tuiles sous les fenêtres de toit
    rw_keep = None
    rw_pan = None
    rw = roof_window_layout(props, h, effective_pitch, o_eave, o_rake)
    if rw is not None:
        rw_pan, rw_centers, rw_u, rw_v, rw_origin, rw_exc = rw
        exc_hu, exc_vlo, exc_vhi = rw_exc

        def rw_keep(p, pf):
            rel = p - rw_origin
            u, v = rel.dot(rw_u), rel.dot(rw_v)
            for (uc, vc) in rw_centers:
                if abs(u + TILE_W / 2 - uc) < exc_hu + TILE_W / 2 and \
                        (vc + exc_vlo - TILE_L) < v < (vc + exc_vhi + 0.02):
                    return False
            return True

    if roof_type == 'SHED':
        # Un seul pan: monte de x=0 vers x=width (plan par la façade à z=h)
        slope = math.tan(pitch_rad)
        slope_len = math.sqrt((width + 2 * o_eave) ** 2 + ((width + 2 * o_eave) * slope) ** 2)
        dir_v = Vector((math.cos(pitch_rad), 0, math.sin(pitch_rad)))
        dir_u = Vector((0, 1, 0))
        z_eave = h - o_eave * slope
        origin = Vector((-o_eave, -o_rake, z_eave + lift))
        cover_slope(origin, dir_u, dir_v, length + 2 * o_rake, slope_len, rot_up_x,
                    keep=rw_keep)
    elif roof_type == 'GABLE':
        # GABLE: 2 pans, faîtage selon la grande dimension
        # ✅ FIX: branche EXPLICITE — le 'else' attrapait aussi HIP/GAMBREL
        # et superposait un champ de tuiles GABLE fantôme à leur couverture
        ridge_along_y = length >= width
        if ridge_along_y:
            half = width / 2
            slope_len = (half + o_eave) / math.cos(pitch_rad)
            z_eave = h - o_eave * math.tan(pitch_rad)
            # Pan gauche (monte vers +X)
            cover_slope(Vector((-o_eave, -o_rake, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((math.cos(pitch_rad), 0, math.sin(pitch_rad))),
                        length + 2 * o_rake, slope_len, rot_up_x, keep=rw_keep)
            # Pan droit (monte vers -X)
            cover_slope(Vector((width + o_eave, -o_rake, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((-math.cos(pitch_rad), 0, math.sin(pitch_rad))),
                        length + 2 * o_rake, slope_len, rot_down_x)
        else:
            half = length / 2
            slope_len = (half + o_eave) / math.cos(pitch_rad)
            z_eave = h - o_eave * math.tan(pitch_rad)
            # Pan avant (monte vers +Y)
            cover_slope(Vector((-o_rake, -o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, math.cos(pitch_rad), math.sin(pitch_rad))),
                        width + 2 * o_rake, slope_len,
                        Euler((pitch_rad, 0, 0), 'XYZ'), keep=rw_keep)
            # Pan arrière (monte vers -Y)
            cover_slope(Vector((-o_rake, length + o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, -math.cos(pitch_rad), math.sin(pitch_rad))),
                        width + 2 * o_rake, slope_len,
                        Euler((-pitch_rad, 0, math.radians(0)), 'XYZ'))

    def _and_keep(k1, k2):
        if k1 is None:
            return k2
        if k2 is None:
            return k1
        return lambda p, pf: k1(p, pf) and k2(p, pf)

    if roof_type == 'HIP':
        # ✅ 4 pans, coupes d'ARÊTIERS à 45° en plan (pentes égales) —
        # les tuiles coupées sont ensuite couvertes par les arêtiers
        slope = math.tan(pitch_rad)
        z_eave = h - o_eave * slope
        cosp = math.cos(pitch_rad)
        tol = 0.10
        # Pans le long des GRANDS côtés (trapèzes) + petits côtés (triangles)
        if length >= width:
            half = width / 2
            slope_len = (half + o_eave) / cosp
            # Pan gauche (x-) trapèze: u le long de +Y, v monte +X
            hip_trim = lambda p, pf: (p.y + o_eave >= (p.x + o_eave) - tol) \
                and (pf.y <= length + o_eave - (p.x + o_eave) + tol)
            cover_slope(Vector((-o_eave, -o_eave, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((cosp, 0, math.sin(pitch_rad))),
                        length + 2 * o_eave, slope_len, rot_up_x,
                        keep=_and_keep(hip_trim,
                                       rw_keep if rw_pan == 'hip_left' else None))
            # Pan droit (x+)
            cover_slope(Vector((width + o_eave, -o_eave, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((-cosp, 0, math.sin(pitch_rad))),
                        length + 2 * o_eave, slope_len, rot_down_x,
                        keep=lambda p, pf: (p.y + o_eave >= (width + o_eave - p.x) - tol)
                        and (pf.y <= length + o_eave - (width + o_eave - p.x) + tol))
            # Pan avant (y-) triangle: u le long de +X, v monte +Y
            tri_len = (half + o_eave) / cosp
            cover_slope(Vector((-o_eave, -o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, cosp, math.sin(pitch_rad))),
                        width + 2 * o_eave, tri_len,
                        Euler((pitch_rad, 0, 0), 'XYZ'),
                        keep=lambda p, pf: (p.x + o_eave >= (p.y + o_eave) - tol)
                        and (pf.x <= width + o_eave - (p.y + o_eave) + tol))
            # Pan arrière (y+)
            cover_slope(Vector((-o_eave, length + o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, -cosp, math.sin(pitch_rad))),
                        width + 2 * o_eave, tri_len,
                        Euler((-pitch_rad, 0, 0), 'XYZ'),
                        keep=lambda p, pf: (p.x + o_eave >= (length + o_eave - p.y) - tol)
                        and (pf.x <= width + o_eave - (length + o_eave - p.y) + tol))
        else:
            half = length / 2
            slope_len = (half + o_eave) / cosp
            # Pans avant/arrière = trapèzes; gauche/droit = triangles
            hip_trim_f = lambda p, pf: (p.x + o_eave >= (p.y + o_eave) - tol) \
                and (pf.x <= width + o_eave - (p.y + o_eave) + tol)
            cover_slope(Vector((-o_eave, -o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, cosp, math.sin(pitch_rad))),
                        width + 2 * o_eave, slope_len,
                        Euler((pitch_rad, 0, 0), 'XYZ'),
                        keep=_and_keep(hip_trim_f,
                                       rw_keep if rw_pan == 'hip_front' else None))
            cover_slope(Vector((-o_eave, length + o_eave, z_eave + lift)),
                        Vector((1, 0, 0)),
                        Vector((0, -cosp, math.sin(pitch_rad))),
                        width + 2 * o_eave, slope_len,
                        Euler((-pitch_rad, 0, 0), 'XYZ'),
                        keep=lambda p, pf: (p.x + o_eave >= (length + o_eave - p.y) - tol)
                        and (pf.x <= width + o_eave - (length + o_eave - p.y) + tol))
            tri_len = (half + o_eave) / cosp
            cover_slope(Vector((-o_eave, -o_eave, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((cosp, 0, math.sin(pitch_rad))),
                        length + 2 * o_eave, tri_len, rot_up_x,
                        keep=lambda p, pf: (p.y + o_eave >= (p.x + o_eave) - tol)
                        and (pf.y <= length + o_eave - (p.x + o_eave) + tol))
            cover_slope(Vector((width + o_eave, -o_eave, z_eave + lift)),
                        Vector((0, 1, 0)),
                        Vector((-cosp, 0, math.sin(pitch_rad))),
                        length + 2 * o_eave, tri_len, rot_down_x,
                        keep=lambda p, pf: (p.y + o_eave >= (width + o_eave - p.x) - tol)
                        and (pf.y <= length + o_eave - (width + o_eave - p.x) + tol))

    if roof_type == 'GAMBREL':
        # ✅ Mansarde: 4 surfaces rectangulaires (2 brisis raides 68° +
        # 2 terrassons doux), égouts toujours en ±X, rives en ±Y
        brisis_rad = math.radians(68.0)
        bd = (width / 2) * 0.25
        bh = bd * math.tan(brisis_rad)
        z_eave = h - o_eave * math.tan(brisis_rad)
        len_u = length + 2 * o_rake
        cosb, sinb = math.cos(brisis_rad), math.sin(brisis_rad)
        rot_b_up = (Matrix.Rotation(-brisis_rad, 3, 'Y') @
                    Matrix.Rotation(math.radians(-90), 3, 'Z')).to_euler()
        rot_b_down = (Matrix.Rotation(brisis_rad, 3, 'Y') @
                      Matrix.Rotation(math.radians(90), 3, 'Z')).to_euler()
        # Brisis gauche/droit
        brisis_len = (o_eave + bd) / cosb
        cover_slope(Vector((-o_eave, -o_rake, z_eave + lift)),
                    Vector((0, 1, 0)), Vector((cosb, 0, sinb)),
                    len_u, brisis_len, rot_b_up)
        cover_slope(Vector((width + o_eave, -o_rake, z_eave + lift)),
                    Vector((0, 1, 0)), Vector((-cosb, 0, sinb)),
                    len_u, brisis_len, rot_b_down)
        # Terrassons gauche/droit (pente utilisateur)
        cosp2, sinp2 = math.cos(pitch_rad), math.sin(pitch_rad)
        terr_len = (width / 2 - bd) / cosp2
        cover_slope(Vector((bd, -o_rake, h + bh + lift)),
                    Vector((0, 1, 0)), Vector((cosp2, 0, sinp2)),
                    len_u, terr_len + 0.03, rot_up_x,
                    keep=rw_keep if rw_pan == 'gambrel_terr_left' else None)
        cover_slope(Vector((width - bd, -o_rake, h + bh + lift)),
                    Vector((0, 1, 0)), Vector((-cosp2, 0, sinp2)),
                    len_u, terr_len + 0.03, rot_down_x)

    if not positions:
        return []

    tile_color = tuple(getattr(props, 'tile_color', (0.34, 0.115, 0.062)))[:3]
    master = _create_tile_master(collection, tile_color)

    # ✅ NOUVEAU: FAÎTIÈRES — demi-rond couvrant la jonction des deux pans
    ridge_objs = []

    def cap_run(bm, p0, p1, radius=0.10):
        """Demi-rond de couverture le long d'une arête p0→p1"""
        axis = Vector(p1) - Vector(p0)
        if axis.length < 0.05:
            return
        seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                    radius1=radius, radius2=radius,
                                    depth=axis.length)
        quat = axis.normalized().to_track_quat('Z', 'Y')
        center = (Vector(p0) + Vector(p1)) / 2
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())

    if roof_type == 'HIP':
        # Faîtage central + 4 ARÊTIERS jusqu'aux angles d'égout
        slope = math.tan(pitch_rad)
        z_eave = h - o_eave * slope
        peak_h = h + (min(width, length) / 2) * slope
        bm = bmesh.new()
        if length >= width:
            r0 = Vector((width / 2, width / 2, peak_h))
            r1 = Vector((width / 2, length - width / 2, peak_h))
        else:
            r0 = Vector((length / 2, length / 2, peak_h))
            r1 = Vector((width - length / 2, length / 2, peak_h))
        cap_run(bm, r0 + Vector((0, 0, 0.03)), r1 + Vector((0, 0, 0.03)), 0.11)
        corners = [Vector((-o_eave, -o_eave, z_eave)),
                   Vector((width + o_eave, -o_eave, z_eave)),
                   Vector((width + o_eave, length + o_eave, z_eave)),
                   Vector((-o_eave, length + o_eave, z_eave))]
        # associer chaque angle à l'extrémité de faîtage la plus proche
        for c in corners:
            end = r0 if (c - r0).length <= (c - r1).length else r1
            cap_run(bm, c + Vector((0, 0, 0.05)), end + Vector((0, 0, 0.03)), 0.09)
        mat = _simple_material("House_Tile", tile_color, roughness=0.75)
        ridge_objs.append(_new_mesh_obj("Roof_Hips", bm, collection, "roof", mat))

    if roof_type == 'GAMBREL':
        # Faîtière + MEMBRONS (cassures brisis/terrasson)
        brisis_rad = math.radians(68.0)
        bd = (width / 2) * 0.25
        bh = bd * math.tan(brisis_rad)
        peak_h = h + bh + (width / 2 - bd) * math.tan(pitch_rad)
        y0, y1 = -o_rake, length + o_rake
        bm = bmesh.new()
        cap_run(bm, (width / 2, y0, peak_h + 0.03), (width / 2, y1, peak_h + 0.03), 0.11)
        for xb in (bd, width - bd):
            cap_run(bm, (xb, y0, h + bh + 0.03), (xb, y1, h + bh + 0.03), 0.085)
        mat = _simple_material("House_Tile", tile_color, roughness=0.75)
        ridge_objs.append(_new_mesh_obj("Roof_Membrons", bm, collection, "roof", mat))

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
    """✅ V2: Volets battants ARTICULÉS — chaque battant est un objet avec
    charnière à l'origine et propriété 'fermeture' (0 = ouverts contre le
    mur, 1 = fermés sur la fenêtre) pilotée par driver.
    """
    if not window_specs:
        return []

    mat = _simple_material("House_Shutter", (0.25, 0.35, 0.42), roughness=0.6)
    t = 0.035  # épaisseur du volet
    created = []

    # Sens de rotation pour que le battant balaie l'EXTÉRIEUR en se fermant
    signs = {('front', -1): 1, ('front', 1): -1,
             ('back', -1): -1, ('back', 1): 1,
             ('left', -1): -1, ('left', 1): 1,
             ('right', -1): 1, ('right', 1): -1}

    for idx, spec in enumerate(window_specs):
        w_leaf = spec['width'] / 2 - 0.02
        hgt = spec['height']
        z0 = spec['z_center'] - hgt / 2
        wall = spec['wall']

        for side in (-1, 1):
            bm = bmesh.new()
            # Battant construit OUVERT, à plat contre le mur, charnière à
            # l'origine (bord côté fenêtre)
            if wall in ('front', 'back'):
                ex = 1 if wall == 'front' else -1  # extérieur en -y / +y
                y0 = -t if wall == 'front' else 0.0
                x_out = side * w_leaf
                _add_box(bm, min(0, x_out), y0, 0, max(0, x_out), y0 + t, hgt)
                hinge = Vector((spec['x'] + side * (spec['width'] / 2 + 0.02),
                                spec['y'], z0))
            else:
                x0 = -t if wall == 'left' else 0.0
                y_out = side * w_leaf
                _add_box(bm, x0, min(0, y_out), 0, x0 + t, max(0, y_out), hgt)
                hinge = Vector((spec['x'],
                                spec['y'] + side * (spec['width'] / 2 + 0.02), z0))

            obj = _new_mesh_obj(f"Shutter_{idx}_{'L' if side < 0 else 'R'}",
                                bm, collection, "shutter", mat)
            obj.location = hinge

            # ✅ Driver 'fermeture': 0 = ouvert (à plat), 1 = fermé (sur la fenêtre)
            obj["fermeture"] = 0.0
            try:
                ui = obj.id_properties_ui("fermeture")
                ui.update(min=0.0, max=1.0,
                          description="0 = volets ouverts, 1 = fermés sur la fenêtre")
            except Exception:
                pass
            fcu = obj.driver_add('rotation_euler', 2)
            drv = fcu.driver
            drv.type = 'SCRIPTED'
            var = drv.variables.new()
            var.name = 'f'
            var.type = 'SINGLE_PROP'
            var.targets[0].id = obj
            var.targets[0].data_path = '["fermeture"]'
            sgn = signs[(wall, side)]
            drv.expression = f'{sgn} * f * {math.pi:.6f}'
            created.append(obj)

    print(f"[House] ✓ Volets ARTICULÉS: {len(created)} battants (propriété 'fermeture')")
    return created


# ============================================================
# ✅ CHARPENTE VISIBLE + TUILES DE RIVE (GABLE)
# ============================================================

def _rake_board_seg(bm, p0, p1, out_axis, sign, bb_h=0.28, bb_t=0.025):
    """Planche de rive le long d'un rampant p0→p1, plaquée au nu du
    pignon (décalée de bb_t/2 le long de out_axis·sign)."""
    axis = p1 - p0
    if axis.length < 0.05:
        return
    quat = axis.normalized().to_track_quat('Z', 'Y')
    box = bmesh.ops.create_cube(bm, size=1.0)
    if out_axis == 'Y':
        scale = Matrix.Diagonal((bb_h, bb_t, axis.length, 1.0))
        off = Vector((0, sign * bb_t / 2, -bb_h * 0.25))
    else:
        scale = Matrix.Diagonal((bb_t, bb_h, axis.length, 1.0))
        off = Vector((sign * bb_t / 2, 0, -bb_h * 0.25))
    bmesh.ops.transform(bm, verts=box['verts'], matrix=scale)
    center = (p0 + p1) / 2 + off
    bmesh.ops.transform(bm, verts=box['verts'],
                        matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())


def _carpentry_other_roofs(props, collection, wall_height, effective_pitch,
                           o_eave, o_rake):
    """✅ v1.6: finitions RÉELLES des toits non-GABLE.

    SHED: fascia d'égout bas + bandeau haut + planches de rive le long
    des rampants + chevrons apparents sous l'égout bas.
    HIP: fascia périphérique sur les 4 égouts + chevrons sur les 4 côtés.
    GAMBREL: fascias d'égout + planches de rive des pignons (2 segments
    brisis/terrasson par rampant).
    FLAT: COUVERTINE zinc sur l'acrotère + MEMBRANE bitume sur la dalle.
    """
    width, length = props.house_width, props.house_length
    pitch_rad = math.radians(effective_pitch)
    slope = math.tan(pitch_rad)
    cosp = math.cos(pitch_rad)
    h = wall_height
    rt = 0.15
    objs = []
    fascia_mat = _simple_material("House_Fascia", (0.92, 0.92, 0.90), roughness=0.5)
    wood = _simple_material("House_Rafter", (0.36, 0.25, 0.15), roughness=0.7)
    fh, ft = 0.18, 0.022

    if props.roof_type == 'SHED':
        z_low = h - o_eave * slope
        z_high = h + (width + o_eave) * slope
        y0, y1 = -o_rake, length + o_rake
        bm = bmesh.new()
        # Fascia d'égout bas (x = -o_eave)
        _add_box(bm, -o_eave - ft, y0, z_low - rt - fh + 0.06,
                 -o_eave, y1, z_low - rt + 0.06)
        # Bandeau haut (x = width + o_eave) — pas de gouttière en tête
        _add_box(bm, width + o_eave, y0, z_high - rt - fh + 0.06,
                 width + o_eave + ft, y1, z_high - rt + 0.06)
        objs.append(_new_mesh_obj("Roof_Fascia", bm, collection, "roof", fascia_mat))
        # Planches de rive le long des rampants (±Y)
        bm = bmesh.new()
        for yy, sgn in ((y0, -1), (y1, 1)):
            _rake_board_seg(bm, Vector((-o_eave, yy, z_low)),
                            Vector((width + o_eave, yy, z_high)), 'Y', sgn)
        objs.append(_new_mesh_obj("Roof_Bargeboard", bm, collection, "roof", fascia_mat))
        # Chevrons apparents sous l'égout bas
        bm = bmesh.new()
        sec_w, sec_h = 0.06, 0.09
        inner = 0.30
        tail_len = (o_eave + inner) / cosp
        n = max(2, int((length + 2 * o_rake) / 0.6))
        for i in range(n + 1):
            yy = -o_rake + 0.06 + i * (length + 2 * o_rake - 0.12) / n
            ret = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Diagonal((tail_len, sec_w, sec_h, 1.0)))
            rot = Matrix.Rotation(-pitch_rad, 4, 'Y')
            xc = (inner - o_eave) / 2
            z_under = h + slope * xc - rt
            center = Vector((xc, yy, z_under - (sec_h / 2) / cosp + 0.005))
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Translation(center) @ rot)
        objs.append(_new_mesh_obj("Roof_Rafters", bm, collection, "roof", wood))
        print("[House] ✓ Finitions monopente: fascia + bandeau + rives + chevrons")

    elif props.roof_type == 'HIP':
        z_eave = h - o_eave * slope
        drop = rt / max(0.2, cosp)   # dalle solidifiée perpendiculairement
        bm = bmesh.new()
        # Fascia périphérique (4 côtés)
        _add_box(bm, -o_eave - ft, -o_eave, z_eave - drop - fh + 0.06,
                 -o_eave, length + o_eave, z_eave - drop + 0.06)
        _add_box(bm, width + o_eave, -o_eave, z_eave - drop - fh + 0.06,
                 width + o_eave + ft, length + o_eave, z_eave - drop + 0.06)
        _add_box(bm, -o_eave - ft, -o_eave - ft, z_eave - drop - fh + 0.06,
                 width + o_eave + ft, -o_eave, z_eave - drop + 0.06)
        _add_box(bm, -o_eave - ft, length + o_eave, z_eave - drop - fh + 0.06,
                 width + o_eave + ft, length + o_eave + ft, z_eave - drop + 0.06)
        objs.append(_new_mesh_obj("Roof_Fascia", bm, collection, "roof", fascia_mat))
        # Chevrons sur les 4 côtés (à l'écart des angles: les arêtiers y règnent)
        bm = bmesh.new()
        sec_w, sec_h = 0.06, 0.09
        inner = 0.30
        tail_len = (o_eave + inner) / cosp

        def hip_rafter(axis, sign, coord):
            ret = bmesh.ops.create_cube(bm, size=1.0)
            if axis == 'X':   # égouts x=cst → chevrons le long de X
                bmesh.ops.transform(bm, verts=ret['verts'],
                                    matrix=Matrix.Diagonal((tail_len, sec_w, sec_h, 1.0)))
                ang = -pitch_rad if sign < 0 else pitch_rad
                rot = Matrix.Rotation(ang, 4, 'Y')
                xc = (inner - o_eave) / 2 if sign < 0 else width - (inner - o_eave) / 2
                x_in = xc if sign < 0 else width - xc
                z_under = h + slope * x_in - rt / cosp
                center = Vector((xc, coord, z_under - (sec_h / 2) / cosp + 0.005))
            else:
                bmesh.ops.transform(bm, verts=ret['verts'],
                                    matrix=Matrix.Diagonal((sec_w, tail_len, sec_h, 1.0)))
                ang = pitch_rad if sign < 0 else -pitch_rad
                rot = Matrix.Rotation(ang, 4, 'X')
                yc = (inner - o_eave) / 2 if sign < 0 else length - (inner - o_eave) / 2
                y_in = yc if sign < 0 else length - yc
                z_under = h + slope * y_in - rt / cosp
                center = Vector((coord, yc, z_under - (sec_h / 2) / cosp + 0.005))
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Translation(center) @ rot)

        margin = 0.55
        n = max(1, int((length - 2 * margin) / 0.6))
        for i in range(n + 1):
            yy = margin + i * (length - 2 * margin) / max(n, 1)
            hip_rafter('X', -1, yy)
            hip_rafter('X', +1, yy)
        n = max(1, int((width - 2 * margin) / 0.6))
        for i in range(n + 1):
            xx = margin + i * (width - 2 * margin) / max(n, 1)
            hip_rafter('Y', -1, xx)
            hip_rafter('Y', +1, xx)
        objs.append(_new_mesh_obj("Roof_Rafters", bm, collection, "roof", wood))
        print("[House] ✓ Finitions croupe: fascia périphérique + chevrons 4 côtés")

    elif props.roof_type == 'GAMBREL':
        brisis_rad = math.radians(68.0)
        bd = (width / 2) * 0.25
        bh = bd * math.tan(brisis_rad)
        rh = bh + (width / 2 - bd) * slope
        z_eave = h - o_eave * math.tan(brisis_rad)
        y0, y1 = -o_rake, length + o_rake
        bm = bmesh.new()
        # Fascias d'égout (pieds de brisis, ±X)
        _add_box(bm, -o_eave - ft, y0, z_eave - rt - fh + 0.06,
                 -o_eave, y1, z_eave - rt + 0.06)
        _add_box(bm, width + o_eave, y0, z_eave - rt - fh + 0.06,
                 width + o_eave + ft, y1, z_eave - rt + 0.06)
        objs.append(_new_mesh_obj("Roof_Fascia", bm, collection, "roof", fascia_mat))
        # Planches de rive des pignons: 2 segments par rampant × 2 côtés × 2 pignons
        bm = bmesh.new()
        for yy, sgn in ((y0, -1), (y1, 1)):
            for xs, xb, xr in ((-o_eave, bd, width / 2),
                               (width + o_eave, width - bd, width / 2)):
                _rake_board_seg(bm, Vector((xs, yy, z_eave)),
                                Vector((xb, yy, h + bh)), 'Y', sgn)
                _rake_board_seg(bm, Vector((xb, yy, h + bh)),
                                Vector((xr, yy, h + rh)), 'Y', sgn)
        objs.append(_new_mesh_obj("Roof_Bargeboard", bm, collection, "roof", fascia_mat))
        print("[House] ✓ Finitions mansarde: fascias + rives brisis/terrasson")

    elif props.roof_type == 'FLAT':
        # COUVERTINE zinc sur l'acrotère + MEMBRANE bitume
        # Géométrie EXACTE de _create_flat_roof: dalle h..h+0.30,
        # acrotère 0.45 au-dessus, épaisseur clampée comme là-bas
        o = props.roof_overhang
        top_slab = h + 0.30
        pz = top_slab + 0.45
        pt = min(0.15, (width + 2 * o) / 3, (length + 2 * o) / 3)
        zinc = _simple_material("House_Zinc", (0.62, 0.65, 0.67), roughness=0.35,
                                metallic=0.9)
        bm = bmesh.new()
        e = 0.03  # débord de couvertine
        x0, x1 = -o, width + o
        y0, y1 = -o, length + o
        _add_box(bm, x0 - e, y0 - e, pz, x1 + e, y0 + pt + e, pz + 0.04)
        _add_box(bm, x0 - e, y1 - pt - e, pz, x1 + e, y1 + e, pz + 0.04)
        _add_box(bm, x0 - e, y0 + pt + e, pz, x0 + pt + e, y1 - pt - e, pz + 0.04)
        _add_box(bm, x1 - pt - e, y0 + pt + e, pz, x1 + e, y1 - pt - e, pz + 0.04)
        objs.append(_new_mesh_obj("Roof_Coping", bm, collection, "roof", zinc))
        membrane = _simple_material("House_Membrane", (0.16, 0.15, 0.14),
                                    roughness=0.95)
        bm = bmesh.new()
        _add_box(bm, x0 + pt, y0 + pt, top_slab, x1 - pt, y1 - pt, top_slab + 0.012)
        objs.append(_new_mesh_obj("Roof_Membrane", bm, collection, "roof", membrane))
        print("[House] ✓ Finitions toit-terrasse: couvertine zinc + membrane")

    return objs


def build_roof_carpentry(props, collection, wall_height, effective_pitch,
                         o_eave, o_rake, tile_color=(0.34, 0.115, 0.062),
                         eave_exclusions=None):
    """La 'façon de faire les toits' V2: chevrons apparents sous les
    débords, planches de rive (fascia), bargeboards et couvertines —
    ce qu'on voit d'une vraie toiture en levant les yeux.
    ✅ v1.6: les 5 types de toit sont finis sérieusement.
    """
    if props.roof_type != 'GABLE':
        return _carpentry_other_roofs(props, collection, wall_height,
                                      effective_pitch, o_eave, o_rake)

    width = props.house_width
    length = props.house_length
    pitch_rad = math.radians(effective_pitch)
    h = wall_height
    ridge_along_y = length >= width

    wood = _simple_material("House_Rafter", (0.36, 0.25, 0.15), roughness=0.7)
    fascia_mat = _simple_material("House_Fascia", (0.92, 0.92, 0.90), roughness=0.5)
    rive_mat = _simple_material("House_Tile", tile_color, roughness=0.65)

    objs = []
    slope = math.tan(pitch_rad)
    cosp, sinp = math.cos(pitch_rad), math.sin(pitch_rad)
    z_eave = h - o_eave * slope
    rt = 0.15  # épaisseur dalle (ROOF_THICKNESS_PITCHED)

    # --- CHEVRONS sous les débords d'égout (maths exactes) ---
    # Le dessous de la dalle au point x (pente gauche): z = h + slope*x - rt
    # Chevron: parallèle à la pente, sa face SUPÉRIEURE collée au dessous
    # de la dalle, courant de l'égout (x=-o_eave) jusque dans le mur (+0.3)
    bm = bmesh.new()
    sec_w, sec_h = 0.06, 0.09
    inner = 0.30                        # entrée du chevron dans le mur
    tail_len = (o_eave + inner) / cosp  # longueur le long de la pente

    def gable_rafter(sign_axis, coord_along, axis='Y'):
        """Un chevron sur l'égout. sign_axis: -1 = égout bas de pente
        côté négatif, +1 = côté positif. axis: axe du faîtage."""
        ret = bmesh.ops.create_cube(bm, size=1.0)
        if axis == 'Y':
            # Faîtage Y → chevrons le long de X, inclinés autour de Y
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Diagonal((tail_len, sec_w, sec_h, 1.0)))
            ang = -pitch_rad if sign_axis < 0 else pitch_rad
            rot = Matrix.Rotation(ang, 4, 'Y')
            # Centre horizontal du chevron
            xc = (-o_eave + inner) / 2 if sign_axis < 0 else width - (-o_eave + inner) / 2
            # Dessous de dalle au centre (plan passant par la façade à z=h)
            x_from_wall = xc if sign_axis < 0 else width - xc
            z_under = h + slope * x_from_wall - rt
            center = Vector((xc, coord_along, z_under - (sec_h / 2) / cosp + 0.005))
        else:
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Diagonal((sec_w, tail_len, sec_h, 1.0)))
            ang = pitch_rad if sign_axis < 0 else -pitch_rad
            rot = Matrix.Rotation(ang, 4, 'X')
            yc = (-o_eave + inner) / 2 if sign_axis < 0 else length - (-o_eave + inner) / 2
            y_from_wall = yc if sign_axis < 0 else length - yc
            z_under = h + slope * y_from_wall - rt
            center = Vector((coord_along, yc, z_under - (sec_h / 2) / cosp + 0.005))
        bmesh.ops.transform(bm, verts=ret['verts'],
                            matrix=Matrix.Translation(center) @ rot)

    spacing = 0.6
    ex = eave_exclusions or {}

    def excluded(wall, coord):
        return any(e0 <= coord <= e1 for (e0, e1) in ex.get(wall, []))

    if ridge_along_y:
        n = max(2, int((length + 2 * o_rake) / spacing))
        for i in range(n + 1):
            y = -o_rake + 0.06 + i * (length + 2 * o_rake - 0.12) / n
            if not excluded('left', y):
                gable_rafter(-1, y, axis='Y')
            if not excluded('right', y):
                gable_rafter(+1, y, axis='Y')
    else:
        n = max(2, int((width + 2 * o_rake) / spacing))
        for i in range(n + 1):
            x = -o_rake + 0.06 + i * (width + 2 * o_rake - 0.12) / n
            if not excluded('front', x):
                gable_rafter(-1, x, axis='X')
            if not excluded('back', x):
                gable_rafter(+1, x, axis='X')

    if len(bm.verts):
        objs.append(_new_mesh_obj("Roof_Rafters", bm, collection, "roof", wood))
    else:
        bm.free()

    # --- PLANCHE DE RIVE (fascia) le long des égouts ---
    bm = bmesh.new()
    fh, ft = 0.18, 0.022
    if ridge_along_y:
        y0, y1 = -o_rake, length + o_rake
        for (s0, s1) in _split_interval(y0, y1, ex.get('left')):
            _add_box(bm, -o_eave - ft, s0, z_eave - rt - fh + 0.06,
                     -o_eave, s1, z_eave - rt + 0.06)
        for (s0, s1) in _split_interval(y0, y1, ex.get('right')):
            _add_box(bm, width + o_eave, s0, z_eave - rt - fh + 0.06,
                     width + o_eave + ft, s1, z_eave - rt + 0.06)
    else:
        x0, x1 = -o_rake, width + o_rake
        for (s0, s1) in _split_interval(x0, x1, ex.get('front')):
            _add_box(bm, s0, -o_eave - ft, z_eave - rt - fh + 0.06,
                     s1, -o_eave, z_eave - rt + 0.06)
        for (s0, s1) in _split_interval(x0, x1, ex.get('back')):
            _add_box(bm, s0, length + o_eave, z_eave - rt - fh + 0.06,
                     s1, length + o_eave + ft, z_eave - rt + 0.06)
    objs.append(_new_mesh_obj("Roof_Fascia", bm, collection, "roof", fascia_mat))

    # --- PLANCHES DE RIVE DE PIGNON (bargeboards) le long des rampants ---
    # Elles ferment visuellement le jeu entre le rampant de la dalle et la
    # diagonale des briques coupées du pignon (détail de construction réel).
    bm = bmesh.new()
    bb_h, bb_t = 0.28, 0.025

    def rake_board(p0, p1, y_out, sign_y):
        """Planche suivant le rampant de p0 (égout) à p1 (faîtage), plaquée
        au nu du pignon (y_out), épaisseur vers l'extérieur."""
        axis = (p1 - p0)
        run = axis.length
        quat = axis.normalized().to_track_quat('Z', 'Y')
        box = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.transform(bm, verts=box['verts'],
                            matrix=Matrix.Diagonal((bb_h, bb_t, run, 1.0)))
        center = (p0 + p1) / 2 + Vector((0, sign_y * bb_t / 2, -bb_h * 0.25))
        center.y = y_out + sign_y * bb_t / 2
        bmesh.ops.transform(bm, verts=box['verts'],
                            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())

    if ridge_along_y:
        half = width / 2
        peak = h + half * slope
        for y_out, sgn in ((-o_rake, -1), (length + o_rake, 1)):
            for x0, x1 in ((-o_eave, half), (width + o_eave, half)):
                p0 = Vector((x0, y_out, z_eave))
                p1 = Vector((x1, y_out, peak))
                rake_board(p0, p1, y_out, sgn)
    else:
        half = length / 2
        peak = h + half * slope
        for x_out, sgn in ((-o_rake, -1), (width + o_rake, 1)):
            for y0, y1 in ((-o_eave, half), (length + o_eave, half)):
                p0 = Vector((x_out, y0, z_eave))
                p1 = Vector((x_out, y1, peak))
                axis = (p1 - p0)
                run = axis.length
                quat = axis.normalized().to_track_quat('Z', 'Y')
                box = bmesh.ops.create_cube(bm, size=1.0)
                bmesh.ops.transform(bm, verts=box['verts'],
                                    matrix=Matrix.Diagonal((bb_t, bb_h, run, 1.0)))
                center = (p0 + p1) / 2 + Vector((sgn * bb_t / 2, 0, -bb_h * 0.25))
                center.x = x_out + sgn * bb_t / 2
                bmesh.ops.transform(bm, verts=box['verts'],
                                    matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
    if len(bm.verts):
        objs.append(_new_mesh_obj("Roof_Bargeboard", bm, collection, "roof", fascia_mat))
    else:
        bm.free()

    # --- TUILES DE RIVE le long des pignons (demi-ronds inclinés) ---
    bm = bmesh.new()
    r = 0.07
    if ridge_along_y:
        half = width / 2
        peak = h + half * slope
        run = math.sqrt((half + o_eave) ** 2 + (peak - z_eave) ** 2)
        for y in (-o_rake, length + o_rake):
            for sgn, x_start in ((1, -o_eave), (-1, width + o_eave)):
                seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=8,
                                            radius1=r, radius2=r, depth=run)
                direction = Vector((sgn * (half + o_eave), 0, peak - z_eave)).normalized()
                quat = direction.to_track_quat('Z', 'Y')
                center = Vector((x_start + sgn * (half + o_eave) / 2, y,
                                 (z_eave + peak) / 2 + 0.06))
                bmesh.ops.transform(bm, verts=seg['verts'],
                                    matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
    else:
        half = length / 2
        peak = h + half * slope
        run = math.sqrt((half + o_eave) ** 2 + (peak - z_eave) ** 2)
        for x in (-o_rake, width + o_rake):
            for sgn, y_start in ((1, -o_eave), (-1, length + o_eave)):
                seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=8,
                                            radius1=r, radius2=r, depth=run)
                direction = Vector((0, sgn * (half + o_eave), peak - z_eave)).normalized()
                quat = direction.to_track_quat('Z', 'Y')
                center = Vector((x, y_start + sgn * (half + o_eave) / 2,
                                 (z_eave + peak) / 2 + 0.06))
                bmesh.ops.transform(bm, verts=seg['verts'],
                                    matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
    objs.append(_new_mesh_obj("Roof_Verge", bm, collection, "roof", rive_mat))

    print("[House] ✓ Charpente: chevrons + planches de rive + tuiles de rive")
    return objs

# ============================================================
# ✅ v1.7 — ② ENVIRONNEMENT DE RENDU
# ============================================================

def build_environment(props, collection, garage_front=None, door_x=None):
    """Terrain gazonné, allée d'entrée, arbres simples, ciel physique
    Nishita + AgX, et caméra cadrée automatiquement.

    C'est le chantier "photo": la maison était finie, le plateau ne
    l'était pas. Aucun fichier externe (ciel procédural Nishita).
    """
    from . import look
    W, L = props.house_width, props.house_length
    cx, cy = W / 2, L / 2
    objs = []

    # --- TERRAIN: grand disque de pelouse ---
    bm = bmesh.new()
    disc = bmesh.ops.create_cone(bm, cap_ends=True, segments=48,
                                 radius1=160.0, radius2=160.0, depth=0.05)
    bmesh.ops.transform(bm, verts=disc['verts'],
                        matrix=Matrix.Translation(Vector((cx, cy, -0.028))))
    objs.append(_new_mesh_obj("Env_Ground", bm, collection, "environment",
                              look.ground_material()))

    # --- ALLÉE d'entrée (béton balayé) ---
    if door_x is None:
        door_x = W / 2
    bm = bmesh.new()
    _add_box(bm, door_x - 1.1, -9.0, -0.005, door_x + 1.1, -0.2, 0.015)
    if garage_front is not None:
        gx0, gx1 = garage_front
        _add_box(bm, gx0, -9.0, -0.005, gx1, -0.2, 0.015)
    conc = _simple_material("Env_Driveway", (0.52, 0.51, 0.49), roughness=0.9)
    objs.append(_new_mesh_obj("Env_Driveway", bm, collection, "environment", conc))

    # --- ARBRES simples (tronc + 2 boules de feuillage) ---
    bark = _simple_material("Env_Bark", (0.21, 0.14, 0.09), roughness=0.9)
    leaf = _simple_material("Env_Leaves", (0.08, 0.16, 0.05), roughness=0.85)
    bm_t = bmesh.new()
    bm_l = bmesh.new()
    spots = [(-6.0, L + 5.0, 1.00), (W + 7.0, L + 3.0, 1.25),
             (W + 6.5, -5.5, 0.85), (-7.5, -3.0, 1.1)]
    for (tx, ty, s) in spots:
        trunk = bmesh.ops.create_cone(bm_t, cap_ends=True, segments=8,
                                      radius1=0.16 * s, radius2=0.11 * s,
                                      depth=2.2 * s)
        bmesh.ops.transform(bm_t, verts=trunk['verts'],
                            matrix=Matrix.Translation(Vector((tx, ty, 1.1 * s))))
        for (dz, r) in ((2.6 * s, 1.35 * s), (3.5 * s, 0.95 * s)):
            ball = bmesh.ops.create_icosphere(bm_l, subdivisions=2,
                                              radius=r)
            bmesh.ops.transform(bm_l, verts=ball['verts'],
                                matrix=Matrix.Translation(Vector((tx, ty, dz))))
    objs.append(_new_mesh_obj("Env_Trunks", bm_t, collection, "environment", bark))
    leaves = _new_mesh_obj("Env_Leaves", bm_l, collection, "environment", leaf)
    for poly in leaves.data.polygons:
        poly.use_smooth = True
    objs.append(leaves)

    # --- HAIE périphérique (parcelle) ---
    hedge = _simple_material("Env_Hedge", (0.06, 0.13, 0.04), roughness=0.9)
    bm = bmesh.new()
    px0, py0 = cx - 16.0, -10.5
    px1, py1 = cx + 16.0, cy + 14.0
    hh, ht = 1.1, 0.5
    gate = (door_x - 2.2, door_x + 2.2) if door_x is not None else (cx - 2.2, cx + 2.2)
    _add_box(bm, px0, py0, 0, max(px0 + 0.1, gate[0]), py0 + ht, hh)
    _add_box(bm, min(px1 - 0.1, gate[1]), py0, 0, px1, py0 + ht, hh)
    _add_box(bm, px0, py1 - ht, 0, px1, py1, hh)
    _add_box(bm, px0, py0, 0, px0 + ht, py1, hh)
    _add_box(bm, px1 - ht, py0, 0, px1, py1, hh)
    objs.append(_new_mesh_obj("Env_Hedge", bm, collection, "environment", hedge))

    # --- CIEL physique + color management (exposition photo) ---
    look.setup_sky_and_view(sun_elevation_deg=35.0, sun_rotation_deg=150.0,
                            exposure=-4.6)

    # --- CAMÉRA cadrée automatiquement sur l'EMPRISE RÉELLE bâtie ---
    import bpy as _bpy
    scene = _bpy.context.scene
    xs, ys, zs = [], [], []
    for ob in collection.objects:
        if ob.type != 'MESH' or ob.get("house_part") == "environment":
            continue
        for c in ob.bound_box:
            wc = ob.matrix_world @ Vector(c)
            xs.append(wc.x); ys.append(wc.y); zs.append(wc.z)
    if xs:
        cx_b = (min(xs) + max(xs)) / 2
        cy_b = (min(ys) + max(ys)) / 2
        extent = max(max(xs) - min(xs), max(ys) - min(ys), 6.0)
    else:
        cx_b, cy_b, extent = W / 2, L / 2, max(W, L)
    cam_data = _bpy.data.cameras.get("House_Camera") or \
        _bpy.data.cameras.new("House_Camera")
    cam = _bpy.data.objects.get("House_Camera")
    if cam is None:
        cam = _bpy.data.objects.new("House_Camera", cam_data)
        collection.objects.link(cam)
    dist = extent * 1.25 + 6.0
    cam.location = Vector((cx_b + dist * 0.62, cy_b - dist * 0.72,
                           1.6 + dist * 0.16))
    target = Vector((cx_b, cy_b, 1.9))
    d = target - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = 35
    scene.camera = cam

    print("[House] ✓ Environnement: terrain + allée + arbres + ciel Nishita + caméra")
    return objs
