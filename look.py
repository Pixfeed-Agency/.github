# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Look Development Module (matériaux photoréalistes + scène)
#  Copyright (C) 2025 mvaertan
#
#  Tous les matériaux "montée en gamme": chaque surface a de la variation
#  (par instance via Object Info Random, par position via bruits), du
#  micro-relief (bump) et une rugosité crédible. Plus la mise en scène:
#  ciel physique Nishita, color management AgX, sol habillé.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import math
import os


# ============================================================
# OUTILS NODES
# ============================================================

def _new_mat(name):
    """Matériau à node tree vierge (recréé à chaque génération pour
    garantir la dernière version du look)"""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


def _basic(mat, x=0):
    """Principled + Output, retourne (nodes, links, bsdf)"""
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (x + 300, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (x, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return nodes, links, bsdf


def _instance_random(nodes, links, x, y):
    """Object Info → Random: varie PAR INSTANCE (chaque brique/tuile!)"""
    info = nodes.new('ShaderNodeObjectInfo')
    info.location = (x, y)
    return info.outputs['Random']


# ============================================================
# ✅ v1.28 — IMPERFECTIONS PHOTO (anti-maquette)
# Les trois règles des rendus qui trompent l'œil:
#   1. JAMAIS de roughness uniforme (le "vernis CG")
#   2. Les arêtes vives n'existent pas (bevel au shading)
#   3. Une façade vit: coulures, creux salis, pied de mur terni
# Tout est OPT-IN au niveau de détail PHOTO — le rendu NORMAL reste
# bit-identique (banc visuel).
# ============================================================

def _photo():
    """True au niveau de détail PHOTO."""
    try:
        return bpy.context.scene.house_generator.detail_level == 'PHOTO'
    except Exception:
        return False


def _rough_noise(nodes, links, bsdf, base_rough, amount=0.08, scale=8.0,
                 x=-420, y=-460):
    """Bruit de roughness ±amount autour de la valeur nominale."""
    n = nodes.new('ShaderNodeTexNoise')
    n.location = (x, y)
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = 4.0
    mr = nodes.new('ShaderNodeMapRange')
    mr.location = (x + 200, y)
    mr.inputs['To Min'].default_value = max(0.0, base_rough - amount)
    mr.inputs['To Max'].default_value = min(1.0, base_rough + amount)
    links.new(n.outputs['Fac'], mr.inputs['Value'])
    links.new(mr.outputs['Result'], bsdf.inputs['Roughness'])


def _edge_bevel(nodes, links, bsdf, radius=0.006, x=-420, y=-680):
    """Node Bevel (Cycles): arêtes adoucies au shading. Se chaîne
    AVANT un éventuel Bump déjà branché sur Normal."""
    bv = nodes.new('ShaderNodeBevel')
    bv.location = (x, y)
    bv.samples = 4
    bv.inputs['Radius'].default_value = radius
    tgt = bsdf.inputs['Normal']
    if tgt.is_linked:
        up = tgt.links[0].from_node
        if up.type == 'BUMP' and not up.inputs['Normal'].is_linked:
            links.new(bv.outputs['Normal'], up.inputs['Normal'])
            return
    links.new(bv.outputs['Normal'], tgt)


def _grime(nodes, links, bsdf, streaks=0.06, cavities=0.12,
           x=-420, y=-900):
    """Salissures: COULURES verticales (bruit étiré par la gravité) et
    CREUX salis (Ambient Occlusion), multipliés sur la Base Color.
    Nécessite une Base Color déjà câblée."""
    src = bsdf.inputs['Base Color']
    if not src.is_linked:
        return
    from_sock = src.links[0].from_socket

    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = (x - 560, y)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (x - 380, y)
    # étirement vertical: les traînées suivent la pluie
    mapping.inputs['Scale'].default_value = (7.0, 7.0, 0.45)
    links.new(geo.outputs['Position'], mapping.inputs['Vector'])
    sn = nodes.new('ShaderNodeTexNoise')
    sn.location = (x - 190, y)
    sn.inputs['Scale'].default_value = 1.0
    sn.inputs['Detail'].default_value = 5.0
    links.new(mapping.outputs['Vector'], sn.inputs['Vector'])
    smap = nodes.new('ShaderNodeMapRange')
    smap.location = (x, y)
    smap.inputs['To Min'].default_value = 1.0 - streaks
    smap.inputs['To Max'].default_value = 1.0
    links.new(sn.outputs['Fac'], smap.inputs['Value'])

    ao = nodes.new('ShaderNodeAmbientOcclusion')
    ao.location = (x - 190, y - 220)
    ao.samples = 4
    ao.inputs['Distance'].default_value = 0.35
    amap = nodes.new('ShaderNodeMapRange')
    amap.location = (x, y - 220)
    amap.inputs['To Min'].default_value = 1.0 - cavities
    amap.inputs['To Max'].default_value = 1.0
    links.new(ao.outputs['AO'], amap.inputs['Value'])

    m1 = nodes.new('ShaderNodeMix')
    m1.data_type = 'RGBA'
    m1.blend_type = 'MULTIPLY'
    m1.location = (x + 200, y)
    m1.inputs['Factor'].default_value = 1.0
    links.new(from_sock, m1.inputs[6])
    links.new(smap.outputs['Result'], m1.inputs[7])
    m2 = nodes.new('ShaderNodeMix')
    m2.data_type = 'RGBA'
    m2.blend_type = 'MULTIPLY'
    m2.location = (x + 380, y)
    m2.inputs['Factor'].default_value = 1.0
    links.new(m1.outputs[2], m2.inputs[6])
    links.new(amap.outputs['Result'], m2.inputs[7])
    links.new(m2.outputs[2], bsdf.inputs['Base Color'])


# ============================================================
# TUILES TERRE CUITE
# ============================================================

def chimney_brick_material(mortar_color=(0.72, 0.69, 0.64)):
    """Brique de cheminée: Brick Texture procédural à l'échelle réelle
    (22×6.5cm, joints 12mm), teinte terracotta profonde + bump des joints.
    Le vecteur (x+y, z) projette le motif sur les 4 faces verticales."""
    mat = _new_mat("House_Chimney_V2")
    nodes, links, bsdf = _basic(mat)

    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = (-1150, 200)
    sep = nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-980, 200)
    links.new(geo.outputs['Position'], sep.inputs['Vector'])
    add = nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.location = (-810, 260)
    links.new(sep.outputs['X'], add.inputs[0])
    links.new(sep.outputs['Y'], add.inputs[1])
    comb = nodes.new('ShaderNodeCombineXYZ')
    comb.location = (-650, 200)
    links.new(add.outputs['Value'], comb.inputs['X'])
    links.new(sep.outputs['Z'], comb.inputs['Y'])

    brick = nodes.new('ShaderNodeTexBrick')
    brick.location = (-450, 200)
    brick.inputs['Color1'].default_value = (0.30, 0.075, 0.042, 1)
    brick.inputs['Color2'].default_value = (0.42, 0.115, 0.058, 1)
    brick.inputs['Mortar'].default_value = (*mortar_color[:3], 1)
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.012
    brick.inputs['Mortar Smooth'].default_value = 0.4
    brick.inputs['Bias'].default_value = 0.0
    brick.inputs['Brick Width'].default_value = 0.232
    brick.inputs['Row Height'].default_value = 0.077
    links.new(comb.outputs['Vector'], brick.inputs['Vector'])
    links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.85

    # Joints en creux (le Fac du BrickTex = 1 sur le mortier)
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-220, -140)
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.004
    bump.invert = True
    links.new(brick.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def tile_material(base_color=(0.34, 0.115, 0.062), finish='AUTO'):
    """Matière de couverture PROCÉDURALE, au choix (chantier n°7):
    - AUTO / TERRE_CUITE: variation de cuisson par tuile + moucheté
    - ARDOISE: gris bleuté schisteux, reflets satinés par tuile
    - BETON: tuile béton grise mate, teinte terne homogène
    Le nom du matériau encode la finition (re-résolu à chaque build)."""
    if finish == 'ARDOISE':
        base_color = (0.070, 0.082, 0.098)
    elif finish == 'BETON':
        base_color = (0.30, 0.29, 0.27)
    elif finish == 'PLATE':
        base_color = (0.28, 0.10, 0.055)   # brun-rouge vieilli
    suffix = "" if finish in ('AUTO', 'TERRE_CUITE') else f"_{finish.title()}"
    mat = _new_mat("House_Tile" + suffix)
    nodes, links, bsdf = _basic(mat)

    # Variation de teinte par tuile (four de cuisson)
    rand = _instance_random(nodes, links, -900, 300)
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-700, 300)
    r, g, b = base_color
    ramp.color_ramp.elements[0].color = (r * 0.72, g * 0.62, b * 0.62, 1)
    ramp.color_ramp.elements[1].color = (min(1, r * 1.30), min(1, g * 1.25), min(1, b * 1.15), 1)
    # Nuance intermédiaire orangée
    e = ramp.color_ramp.elements.new(0.5)
    e.color = (min(1, r * 1.05), g * 0.95, b * 0.85, 1)
    if _photo():
        # ✅ v1.28.1: variation GROUPÉE PAR LOTS — l'aléa indépendant
        # par tuile faisait un damier de bruit blanc ("neige TV"),
        # LE marqueur procédural n°1 du toit. Sur un vrai toit les
        # teintes viennent par plaques (lots de cuisson posés
        # ensemble): 55% aléa tuile + 45% nappe spatiale.
        info_p = nodes.new('ShaderNodeObjectInfo')
        info_p.location = (-1150, 480)
        patch = nodes.new('ShaderNodeTexNoise')
        patch.location = (-960, 480)
        patch.inputs['Scale'].default_value = 0.30
        patch.inputs['Detail'].default_value = 2.0
        links.new(info_p.outputs['Location'], patch.inputs['Vector'])
        m1 = nodes.new('ShaderNodeMath')
        m1.operation = 'MULTIPLY'
        m1.location = (-780, 400)
        links.new(rand, m1.inputs[0])
        m1.inputs[1].default_value = 0.55
        m2 = nodes.new('ShaderNodeMath')
        m2.operation = 'MULTIPLY_ADD'
        m2.location = (-620, 400)
        links.new(patch.outputs['Fac'], m2.inputs[0])
        m2.inputs[1].default_value = 0.45
        links.new(m1.outputs['Value'], m2.inputs[2])
        links.new(m2.outputs['Value'], ramp.inputs['Fac'])
    else:
        links.new(rand, ramp.inputs['Fac'])

    # Moucheté de surface (dépôts, cuisson inégale)
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-700, 60)
    noise.inputs['Scale'].default_value = 35.0
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 0.55

    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-420, 220)
    mix.inputs['Factor'].default_value = 0.22
    links.new(ramp.outputs['Color'], mix.inputs[6])
    links.new(noise.outputs['Color'], mix.inputs[7])

    # ✅ v1.9.1: patine du versant (position monde, plaques 4-10m —
    # lichens/salissures qui cassent l'orange uniforme)
    geo_w = nodes.new('ShaderNodeNewGeometry')
    geo_w.location = (-650, 480)
    wnoise = nodes.new('ShaderNodeTexNoise')
    wnoise.location = (-460, 480)
    wnoise.inputs['Scale'].default_value = 0.13
    wnoise.inputs['Detail'].default_value = 6.0
    links.new(geo_w.outputs['Position'], wnoise.inputs['Vector'])
    w_map = nodes.new('ShaderNodeMapRange')
    w_map.location = (-280, 480)
    w_map.inputs['To Min'].default_value = 0.72
    w_map.inputs['To Max'].default_value = 1.0
    links.new(wnoise.outputs['Fac'], w_map.inputs['Value'])
    mix_w = nodes.new('ShaderNodeMix')
    mix_w.data_type = 'RGBA'
    mix_w.blend_type = 'MULTIPLY'
    mix_w.location = (-230, 300)
    mix_w.inputs['Factor'].default_value = 1.0
    links.new(mix.outputs[2], mix_w.inputs[6])
    links.new(w_map.outputs['Result'], mix_w.inputs[7])
    links.new(mix_w.outputs[2], bsdf.inputs['Base Color'])

    # Rugosité vivante (mate mais irrégulière) — l'ardoise est satinée
    r_ramp = nodes.new('ShaderNodeMapRange')
    r_ramp.location = (-420, -60)
    if finish == 'ARDOISE':
        r_ramp.inputs['To Min'].default_value = 0.30
        r_ramp.inputs['To Max'].default_value = 0.55
    else:
        r_ramp.inputs['To Min'].default_value = 0.55
        r_ramp.inputs['To Max'].default_value = 0.85
    links.new(noise.outputs['Fac'], r_ramp.inputs['Value'])
    links.new(r_ramp.outputs['Result'], bsdf.inputs['Roughness'])

    # Grain de surface (bump fin; feuilletage plus marqué en ardoise)
    bump_noise = nodes.new('ShaderNodeTexNoise')
    bump_noise.location = (-700, -260)
    bump_noise.inputs['Scale'].default_value = \
        90.0 if finish == 'ARDOISE' else 180.0
    bump_noise.inputs['Detail'].default_value = 4.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-420, -260)
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.002
    links.new(bump_noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    if _photo():
        # ~5% de tuiles FRANCHEMENT plus sombres (remplacées au fil des
        # ans) — l'étalement doux seul reste trop propre. On garde le
        # dégradé normal jusqu'à 0.94 puis on plonge vers le sombre.
        keep = ramp.color_ramp.elements.new(0.94)
        keep.color = (min(1, r * 1.30), min(1, g * 1.25),
                      min(1, b * 1.15), 1)
        dark = [el for el in ramp.color_ramp.elements
                if el.position >= 0.999][0]
        dark.color = (r * 0.40, g * 0.38, b * 0.40, 1)
        _edge_bevel(nodes, links, bsdf, 0.003)
    return mat


# ============================================================
# BRIQUES (par-instance!) + MORTIER
# ============================================================

def brick_material(base_colors=None):
    """Brique: variation PAR BRIQUE (Object Info Random — chaque brique
    est une instance!), marbrures de cuisson, grain de surface.

    Remplace la 'soupe ULTIMATE' de 685 lignes par ~40 nodes lisibles
    qui rendent MIEUX: la variation par brique est ce que l'œil attend.
    """
    if base_colors is None:
        # ✅ Palette terracotta profonde — valeurs LINÉAIRES basses et très
        # saturées pour compenser la désaturation AgX (retours de rendu:
        # les valeurs hautes rendaient rose pastel)
        base_colors = [
            (0.235, 0.048, 0.028), (0.30, 0.068, 0.038), (0.38, 0.095, 0.050),
            (0.46, 0.130, 0.068), (0.54, 0.175, 0.090),
        ]
    mat = _new_mat("House_Brick_V2")
    nodes, links, bsdf = _basic(mat)

    # 1. Couleur de base par brique (le facteur n°1 du réalisme brique)
    rand = _instance_random(nodes, links, -1100, 300)
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-900, 300)
    ramp.color_ramp.interpolation = 'B_SPLINE'
    ramp.color_ramp.elements[0].color = (*base_colors[0][:3], 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*base_colors[-1][:3], 1)
    for i, c in enumerate(base_colors[1:-1], start=1):
        e = ramp.color_ramp.elements.new(i / (len(base_colors) - 1))
        e.color = (*c[:3], 1)
    links.new(rand, ramp.inputs['Fac'])

    # 2. Marbrures de cuisson (grandes taches sombres irrégulières)
    marble = nodes.new('ShaderNodeTexNoise')
    marble.location = (-900, 60)
    marble.inputs['Scale'].default_value = 9.0
    marble.inputs['Detail'].default_value = 8.0
    marble.inputs['Distortion'].default_value = 1.4

    m_ramp = nodes.new('ShaderNodeValToRGB')
    m_ramp.location = (-680, 60)
    m_ramp.color_ramp.elements[0].position = 0.35
    m_ramp.color_ramp.elements[0].color = (0.55, 0.5, 0.5, 1)
    m_ramp.color_ramp.elements[1].position = 0.6
    m_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(marble.outputs['Fac'], m_ramp.inputs['Fac'])

    mix1 = nodes.new('ShaderNodeMix')
    mix1.data_type = 'RGBA'
    mix1.blend_type = 'MULTIPLY'
    mix1.location = (-440, 220)
    # ✅ v1.9.1: marbrures atténuées (le contraste par brique faisait
    # "damier de pixels" à l'échelle du bâtiment)
    mix1.inputs['Factor'].default_value = 0.30
    links.new(ramp.outputs['Color'], mix1.inputs[6])
    links.new(m_ramp.outputs['Color'], mix1.inputs[7])

    # ✅ v1.9.1: PATINE à l'échelle du MUR (position monde) — zones
    # d'humidité/salissure de 3-8m, ce que l'œil lit sur un vrai pignon
    geo_w = nodes.new('ShaderNodeNewGeometry')
    geo_w.location = (-900, 480)
    wnoise = nodes.new('ShaderNodeTexNoise')
    wnoise.location = (-680, 480)
    wnoise.inputs['Scale'].default_value = 0.16
    wnoise.inputs['Detail'].default_value = 5.0
    links.new(geo_w.outputs['Position'], wnoise.inputs['Vector'])
    w_ramp = nodes.new('ShaderNodeMapRange')
    w_ramp.location = (-460, 480)
    w_ramp.inputs['To Min'].default_value = 0.80
    w_ramp.inputs['To Max'].default_value = 1.0
    links.new(wnoise.outputs['Fac'], w_ramp.inputs['Value'])
    mix_w = nodes.new('ShaderNodeMix')
    mix_w.data_type = 'RGBA'
    mix_w.blend_type = 'MULTIPLY'
    mix_w.location = (-330, 320)
    mix_w.inputs['Factor'].default_value = 1.0
    links.new(mix1.outputs[2], mix_w.inputs[6])
    links.new(w_ramp.outputs['Result'], mix_w.inputs[7])

    # 3. Sable/grain clair en surface
    grain = nodes.new('ShaderNodeTexNoise')
    grain.location = (-900, -160)
    grain.inputs['Scale'].default_value = 90.0
    grain.inputs['Detail'].default_value = 5.0

    mix2 = nodes.new('ShaderNodeMix')
    mix2.data_type = 'RGBA'
    mix2.blend_type = 'OVERLAY'
    mix2.location = (-220, 180)
    mix2.inputs['Factor'].default_value = 0.10
    links.new(mix_w.outputs[2], mix2.inputs[6])
    links.new(grain.outputs['Color'], mix2.inputs[7])
    links.new(mix2.outputs[2], bsdf.inputs['Base Color'])

    # 4. Rugosité brique (mate, varie avec le grain)
    r_map = nodes.new('ShaderNodeMapRange')
    r_map.location = (-220, -60)
    r_map.inputs['To Min'].default_value = 0.72
    r_map.inputs['To Max'].default_value = 0.95
    links.new(grain.outputs['Fac'], r_map.inputs['Value'])
    links.new(r_map.outputs['Result'], bsdf.inputs['Roughness'])

    # 5. Micro-relief de surface
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-220, -260)
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.0035
    links.new(grain.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def mortar_material(color=(0.78, 0.75, 0.70)):
    """Mortier sable: granuleux, mat, légèrement irrégulier"""
    mat = _new_mat("House_Mortar_V2")
    nodes, links, bsdf = _basic(mat)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-600, 100)
    noise.inputs['Scale'].default_value = 220.0
    noise.inputs['Detail'].default_value = 5.0

    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-320, 150)
    mix.inputs['Factor'].default_value = 0.25
    mix.inputs[6].default_value = (*color[:3], 1)
    links.new(noise.outputs['Color'], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.95

    bump = nodes.new('ShaderNodeBump')
    bump.location = (-320, -150)
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.004
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


# ============================================================
# BOIS (porte, volets, terrasse)
# ============================================================

def wood_material(name, base=(0.32, 0.19, 0.10), rough=0.45, along='Z'):
    """Bois verni/peint avec veinage étiré et rugosité anisotrope simple"""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)

    coord = nodes.new('ShaderNodeTexCoord')
    coord.location = (-1100, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-920, 0)
    # Étirement du veinage dans le sens des fibres
    if along == 'Z':
        mapping.inputs['Scale'].default_value = (14.0, 14.0, 1.4)
    else:
        mapping.inputs['Scale'].default_value = (1.4, 14.0, 14.0)
    links.new(coord.outputs['Object'], mapping.inputs['Vector'])

    wave = nodes.new('ShaderNodeTexNoise')
    wave.location = (-700, 0)
    wave.inputs['Scale'].default_value = 3.0
    wave.inputs['Detail'].default_value = 10.0
    wave.inputs['Distortion'].default_value = 0.8
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-480, 0)
    r, g, b = base
    ramp.color_ramp.elements[0].color = (r * 0.55, g * 0.5, b * 0.5, 1)
    ramp.color_ramp.elements[1].color = (min(1, r * 1.25), min(1, g * 1.2), min(1, b * 1.15), 1)
    links.new(wave.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = rough
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = 0.15  # léger vernis

    bump = nodes.new('ShaderNodeBump')
    bump.location = (-220, -200)
    bump.inputs['Strength'].default_value = 0.1
    bump.inputs['Distance'].default_value = 0.001
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    if _photo():
        _rough_noise(nodes, links, bsdf, rough, 0.08, scale=18.0)
        _edge_bevel(nodes, links, bsdf, 0.004)
    return mat


# ============================================================
# MÉTAUX, CRÉPI, BÉTON, VERRE
# ============================================================

def zinc_material():
    """Zinc de gouttière: métal brossé gris clair"""
    mat = _new_mat("House_Gutter")
    nodes, links, bsdf = _basic(mat)
    bsdf.inputs['Base Color'].default_value = (0.62, 0.64, 0.66, 1)
    bsdf.inputs['Metallic'].default_value = 1.0
    bsdf.inputs['Roughness'].default_value = 0.38

    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-500, -100)
    noise.inputs['Scale'].default_value = 60.0
    r_map = nodes.new('ShaderNodeMapRange')
    r_map.location = (-280, -100)
    r_map.inputs['To Min'].default_value = 0.30
    r_map.inputs['To Max'].default_value = 0.5
    links.new(noise.outputs['Fac'], r_map.inputs['Value'])
    links.new(r_map.outputs['Result'], bsdf.inputs['Roughness'])
    return mat


def stone_material(name="House_Pierre", base=(0.72, 0.66, 0.55),
                   scale=1.1, joint=(0.62, 0.57, 0.48)):
    """✅ v1.28 PIERRE VUE en MOELLONS ASSISÉS (zéro texture).

    Le Voronoï v1.25 faisait de l'opus incertum (pierres polygonales)
    — or le "pierre vue" des longères est du moellon ASSISÉ: rangées
    horizontales, hauteurs d'assises quasi constantes, longueurs de
    pierres variables, joints beurrés irréguliers. Le node Brick
    Texture fait exactement cet appareillage: chaque brique = un
    moellon (teinte aléatoire), Fac = le joint.

    `scale` conserve sa sémantique v1.25: plus grand = pierres plus
    petites (moellons de soubassement scale≈2.3)."""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)
    r, g, b = base[:3]

    # projection façade: (x+y, z) comme la brique de cheminée
    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = (-1250, 200)
    sep = nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-1080, 200)
    links.new(geo.outputs['Position'], sep.inputs['Vector'])
    add = nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.location = (-910, 260)
    links.new(sep.outputs['X'], add.inputs[0])
    links.new(sep.outputs['Y'], add.inputs[1])
    comb = nodes.new('ShaderNodeCombineXYZ')
    comb.location = (-750, 200)
    links.new(add.outputs['Value'], comb.inputs['X'])
    links.new(sep.outputs['Z'], comb.inputs['Y'])

    # assises pas tirées au laser: micro-ondulation du calepin
    warp = nodes.new('ShaderNodeTexNoise')
    warp.location = (-750, -40)
    warp.inputs['Scale'].default_value = 0.6
    warp.inputs['Detail'].default_value = 2.0
    wsub = nodes.new('ShaderNodeVectorMath')
    wsub.operation = 'SUBTRACT'
    wsub.location = (-590, -40)
    links.new(warp.outputs['Color'], wsub.inputs[0])
    wsub.inputs[1].default_value = (0.5, 0.5, 0.5)
    wmul = nodes.new('ShaderNodeVectorMath')
    wmul.operation = 'SCALE'
    wmul.location = (-430, -40)
    links.new(wsub.outputs['Vector'], wmul.inputs[0])
    wmul.inputs['Scale'].default_value = 0.06
    wadd = nodes.new('ShaderNodeVectorMath')
    wadd.operation = 'ADD'
    wadd.location = (-590, 200)
    links.new(comb.outputs['Vector'], wadd.inputs[0])
    links.new(wmul.outputs['Vector'], wadd.inputs[1])

    row_h = 0.20 / max(0.3, scale)      # hauteur d'assise (~18cm façade)
    brick = nodes.new('ShaderNodeTexBrick')
    brick.location = (-260, 220)
    brick.offset = 0.5                   # décalage d'un demi-moellon
    brick.offset_frequency = 2
    brick.squash = 1.35                  # longueurs variées par rangée
    brick.squash_frequency = 3
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.009
    brick.inputs['Mortar Smooth'].default_value = 0.65
    brick.inputs['Bias'].default_value = 0.0
    brick.inputs['Brick Width'].default_value = row_h * 2.2
    brick.inputs['Row Height'].default_value = row_h
    # teintes calcaire par moellon (Color1↔Color2 au hasard par pierre)
    # — écart FRANC: la version trop douce lisait "parpaing peint"
    brick.inputs['Color1'].default_value = (r * 0.80, g * 0.78,
                                            b * 0.74, 1)
    brick.inputs['Color2'].default_value = (min(1, r * 1.12),
                                            min(1, g * 1.09),
                                            min(1, b * 1.04), 1)
    brick.inputs['Mortar'].default_value = (*joint[:3], 1)
    links.new(wadd.outputs['Vector'], brick.inputs['Vector'])

    # nuages de teinte à l'échelle du mur (une façade n'est jamais unie)
    cloud = nodes.new('ShaderNodeTexNoise')
    cloud.location = (-260, -20)
    cloud.inputs['Scale'].default_value = 0.4
    cloud.inputs['Detail'].default_value = 4.0
    links.new(geo.outputs['Position'], cloud.inputs['Vector'])
    cmap = nodes.new('ShaderNodeMapRange')
    cmap.location = (-80, -20)
    cmap.inputs['To Min'].default_value = 0.87
    cmap.inputs['To Max'].default_value = 1.07
    links.new(cloud.outputs['Fac'], cmap.inputs['Value'])
    mixc = nodes.new('ShaderNodeMix')
    mixc.data_type = 'RGBA'
    mixc.blend_type = 'MULTIPLY'
    mixc.location = (100, 160)
    mixc.inputs['Factor'].default_value = 1.0
    links.new(brick.outputs['Color'], mixc.inputs[6])
    links.new(cmap.outputs['Result'], mixc.inputs[7])
    links.new(mixc.outputs[2], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.92

    # relief: joints en creux (Fac) + grain de taille + bosselage
    # doux par moellon (une pierre n'est pas plane)
    grain = nodes.new('ShaderNodeTexNoise')
    grain.location = (-260, -260)
    grain.inputs['Scale'].default_value = 55.0
    grain.inputs['Detail'].default_value = 5.0
    links.new(wadd.outputs['Vector'], grain.inputs['Vector'])
    boss = nodes.new('ShaderNodeTexNoise')
    boss.location = (-260, -480)
    boss.inputs['Scale'].default_value = 6.5
    boss.inputs['Detail'].default_value = 2.0
    links.new(wadd.outputs['Vector'], boss.inputs['Vector'])
    inv = nodes.new('ShaderNodeMath')                # 1 - joint
    inv.operation = 'SUBTRACT'
    inv.location = (-80, -160)
    inv.inputs[0].default_value = 1.0
    links.new(brick.outputs['Fac'], inv.inputs[1])
    hsum = nodes.new('ShaderNodeMath')
    hsum.operation = 'MULTIPLY_ADD'                  # grain*0.2 + pierre
    hsum.location = (80, -220)
    links.new(grain.outputs['Fac'], hsum.inputs[0])
    hsum.inputs[1].default_value = 0.20
    links.new(inv.outputs['Value'], hsum.inputs[2])
    hsum2 = nodes.new('ShaderNodeMath')
    hsum2.operation = 'MULTIPLY_ADD'                 # + bosselage*0.5
    hsum2.location = (240, -220)
    links.new(boss.outputs['Fac'], hsum2.inputs[0])
    hsum2.inputs[1].default_value = 0.28
    links.new(hsum.outputs['Value'], hsum2.inputs[2])
    bump = nodes.new('ShaderNodeBump')
    bump.location = (400, -160)
    bump.inputs['Strength'].default_value = 0.38
    bump.inputs['Distance'].default_value = 0.006
    links.new(hsum2.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    if _photo():
        _rough_noise(nodes, links, bsdf, 0.92, 0.06, scale=12.0)
        _edge_bevel(nodes, links, bsdf, 0.008)
        _grime(nodes, links, bsdf, streaks=0.05, cavities=0.10)
    return mat


def cut_stone_material(name="House_Pierre_Taille",
                       base=(0.80, 0.75, 0.66)):
    """Pierre de TAILLE lisse (encadrements, chaînages): calcaire
    clair finement grené, arêtes nettes."""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)
    n = nodes.new('ShaderNodeTexNoise')
    n.location = (-400, 100)
    n.inputs['Scale'].default_value = 90.0
    n.inputs['Detail'].default_value = 4.0
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-180, 140)
    mix.inputs['Factor'].default_value = 0.10
    mix.inputs[6].default_value = (*base[:3], 1)
    links.new(n.outputs['Color'], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-180, -120)
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.001
    links.new(n.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    if _photo():
        _rough_noise(nodes, links, bsdf, 0.85, 0.05, scale=20.0)
        _edge_bevel(nodes, links, bsdf, 0.006)
        _grime(nodes, links, bsdf, streaks=0.04, cavities=0.08)
    return mat


def pbr_material(name, maps, size=2.5):
    """✅ v1.29 PACK RÉALISME: matériau depuis un set PBR SCANNÉ
    (le standard Revit/Enscape). Box-mapping en coordonnées objet
    (aucun UV requis), `size` = taille physique couverte par une
    répétition (m). Maps reconnues: color(+ao), roughness, normal,
    height."""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)

    coord = nodes.new('ShaderNodeTexCoord')
    coord.location = (-1000, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-820, 0)
    s = 1.0 / max(0.05, size)
    mapping.inputs['Scale'].default_value = (s, s, s)
    links.new(coord.outputs['Object'], mapping.inputs['Vector'])

    def img_node(path, y, non_color=True):
        img = bpy.data.images.load(path, check_existing=True)
        if non_color:
            img.colorspace_settings.name = 'Non-Color'
        n = nodes.new('ShaderNodeTexImage')
        n.location = (-560, y)
        n.image = img
        n.projection = 'BOX'
        n.projection_blend = 0.25
        links.new(mapping.outputs['Vector'], n.inputs['Vector'])
        return n

    col = img_node(maps['color'], 260, non_color=False)
    color_out = col.outputs['Color']
    if 'ao' in maps:
        ao = img_node(maps['ao'], 20)
        mx = nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.location = (-260, 200)
        mx.inputs['Factor'].default_value = 1.0
        links.new(color_out, mx.inputs[6])
        links.new(ao.outputs['Color'], mx.inputs[7])
        color_out = mx.outputs[2]
    links.new(color_out, bsdf.inputs['Base Color'])

    if 'roughness' in maps:
        rg = img_node(maps['roughness'], -220)
        links.new(rg.outputs['Color'], bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = 0.85

    normal_out = None
    if 'normal' in maps:
        nm = img_node(maps['normal'], -460)
        nmap = nodes.new('ShaderNodeNormalMap')
        nmap.location = (-260, -460)
        links.new(nm.outputs['Color'], nmap.inputs['Color'])
        normal_out = nmap.outputs['Normal']
    if 'height' in maps:
        hg = img_node(maps['height'], -700)
        bmp = nodes.new('ShaderNodeBump')
        bmp.location = (-60, -560)
        bmp.inputs['Strength'].default_value = 0.35
        bmp.inputs['Distance'].default_value = 0.02
        links.new(hg.outputs['Color'], bmp.inputs['Height'])
        if normal_out is not None:
            links.new(normal_out, bmp.inputs['Normal'])
        normal_out = bmp.outputs['Normal']
    if normal_out is not None:
        links.new(normal_out, bsdf.inputs['Normal'])

    if _photo():
        _edge_bevel(nodes, links, bsdf, 0.006)
    print(f"[Look] ✓ Matériau PBR scanné: {name} "
          f"({len(maps)} maps, {size:.1f}m)")
    return mat


def _realism_maps(slot):
    """Maps du pack réalisme pour un slot, ou None (procédural)."""
    try:
        from . import realism
        p = bpy.context.scene.house_generator
        return realism.maps_for(p, slot)
    except Exception:
        return None


def wall_material(base, finish='AUTO'):
    """✅ v1.15: finition murale PROCÉDURALE au choix (chantier n°7):
    AUTO/CREPI_FIN = enduit taloché actuel, CREPI_GROS = crépi projeté
    à gros grain, LISSE = peinture mate unie. Point d'entrée unique
    pour les murs SIMPLE (maison + ailes + _apply_materials).
    ✅ v1.29: le PACK RÉALISME (textures scannées) prime quand le slot
    correspondant est rempli."""
    if finish == 'PIERRE':
        maps = _realism_maps('pierre')
        if maps:
            return pbr_material("House_Pierre_PBR", maps, size=2.5)
        return stone_material(base=base)
    if finish == 'LISSE':
        mat = _new_mat("House_Wall_Lisse")
        nodes, links, bsdf = _basic(mat)
        bsdf.inputs['Base Color'].default_value = (*base[:3], 1)
        bsdf.inputs['Roughness'].default_value = 0.9
        return mat
    maps = _realism_maps('enduit')
    if maps:
        return pbr_material("House_Stucco_PBR", maps, size=3.0)
    grain = 'GROS' if finish == 'CREPI_GROS' else 'FIN'
    return stucco_material("House_Stucco", base, grain=grain)


def stucco_material(name="House_Stucco", base=(0.475, 0.40, 0.30),
                    grain='FIN'):
    """✅ v1.9.1: ENDUIT TALOCHÉ (crépi) — le matériau des pavillons
    français. Grain fin serré + nuages de teinte à l'échelle du mur +
    micro-salissure au pied. L'aplat lisse faisait maquette.
    ✅ v1.15: grain='GROS' = crépi projeté (relief net, ombré)."""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)
    r, g, b = base[:3]

    # nuages de teinte (2-6m, position monde)
    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = (-1100, 260)
    cloud = nodes.new('ShaderNodeTexNoise')
    cloud.location = (-880, 260)
    cloud.inputs['Scale'].default_value = 0.22
    cloud.inputs['Detail'].default_value = 6.0
    links.new(geo.outputs['Position'], cloud.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-660, 260)
    ramp.color_ramp.elements[0].color = (r * 0.86, g * 0.86, b * 0.84, 1)
    ramp.color_ramp.elements[1].color = (min(1, r * 1.08), min(1, g * 1.08),
                                         min(1, b * 1.06), 1)
    links.new(cloud.outputs['Fac'], ramp.inputs['Fac'])

    # pied de mur légèrement sali (dégradé sur 60cm)
    sep = nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-880, 60)
    links.new(geo.outputs['Position'], sep.inputs['Vector'])
    zmap = nodes.new('ShaderNodeMapRange')
    zmap.location = (-660, 60)
    zmap.inputs['From Min'].default_value = 0.0
    zmap.inputs['From Max'].default_value = 0.6
    zmap.inputs['To Min'].default_value = 0.86
    zmap.inputs['To Max'].default_value = 1.0
    zmap.clamp = True
    links.new(sep.outputs['Z'], zmap.inputs['Value'])
    mixd = nodes.new('ShaderNodeMix')
    mixd.data_type = 'RGBA'
    mixd.blend_type = 'MULTIPLY'
    mixd.location = (-440, 200)
    mixd.inputs['Factor'].default_value = 1.0
    links.new(ramp.outputs['Color'], mixd.inputs[6])
    links.new(zmap.outputs['Result'], mixd.inputs[7])
    links.new(mixd.outputs[2], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.93

    # grain taloché fin (bump serré) / crépi projeté (gros grain)
    gnoise = nodes.new('ShaderNodeTexNoise')
    gnoise.location = (-660, -180)
    if grain == 'GROS':
        gnoise.inputs['Scale'].default_value = 95.0
        gnoise.inputs['Detail'].default_value = 5.0
    else:
        gnoise.inputs['Scale'].default_value = 320.0
        gnoise.inputs['Detail'].default_value = 3.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-440, -180)
    if grain == 'GROS':
        bump.inputs['Strength'].default_value = 0.85
        bump.inputs['Distance'].default_value = 0.005
    else:
        bump.inputs['Strength'].default_value = 0.35
        bump.inputs['Distance'].default_value = 0.0016
    links.new(gnoise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    if _photo():
        _rough_noise(nodes, links, bsdf, 0.93, 0.05, scale=14.0)
        _edge_bevel(nodes, links, bsdf, 0.005)
        _grime(nodes, links, bsdf, streaks=0.06, cavities=0.10)
    return mat


def plaster_material(name="House_Garage_Wall", base=(0.86, 0.84, 0.78)):
    """Crépi/enduit: gros grain mat, salissures légères en bas"""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-600, 100)
    noise.inputs['Scale'].default_value = 55.0
    noise.inputs['Detail'].default_value = 7.0

    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-320, 150)
    mix.inputs['Factor'].default_value = 0.12
    mix.inputs[6].default_value = (*base[:3], 1)
    links.new(noise.outputs['Color'], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.9

    bump = nodes.new('ShaderNodeBump')
    bump.location = (-320, -150)
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.003
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def concrete_material(name="Foundation_Material", base=(0.58, 0.57, 0.55)):
    """Béton: taches, grain, mat"""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)

    big = nodes.new('ShaderNodeTexNoise')
    big.location = (-620, 150)
    big.inputs['Scale'].default_value = 4.0
    big.inputs['Detail'].default_value = 6.0

    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-340, 180)
    mix.inputs['Factor'].default_value = 0.18
    mix.inputs[6].default_value = (*base[:3], 1)
    links.new(big.outputs['Color'], mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs['Base Color'])

    fine = nodes.new('ShaderNodeTexNoise')
    fine.location = (-620, -120)
    fine.inputs['Scale'].default_value = 150.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-340, -120)
    bump.inputs['Strength'].default_value = 0.2
    bump.inputs['Distance'].default_value = 0.002
    links.new(fine.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bsdf.inputs['Roughness'].default_value = 0.85
    return mat


def glass_material(name="Window_Glass_V2"):
    """Vitrage: verre légèrement teinté, reflets nets"""
    mat = _new_mat(name)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    glass = nodes.new('ShaderNodeBsdfGlass')
    glass.location = (0, 0)
    glass.inputs['Color'].default_value = (0.82, 0.89, 0.92, 1)
    glass.inputs['IOR'].default_value = 1.45
    glass.inputs['Roughness'].default_value = 0.005
    if _photo():
        # reflets pas au miroir absolu: micro-voile + irrégularité
        gn = nodes.new('ShaderNodeTexNoise')
        gn.location = (-300, -220)
        gn.inputs['Scale'].default_value = 2.5
        gmap = nodes.new('ShaderNodeMapRange')
        gmap.location = (-120, -220)
        gmap.inputs['To Min'].default_value = 0.015
        gmap.inputs['To Max'].default_value = 0.045
        links.new(gn.outputs['Fac'], gmap.inputs['Value'])
        links.new(gmap.outputs['Result'], glass.inputs['Roughness'])
    # ✅ Reflet de CIEL: une vitre réelle en plein jour est un miroir
    # partiel — mix d'un glossy net par Fresnel (les vitres "mortes"
    # étaient un tell d'audit)
    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.location = (0, -160)
    gloss.inputs['Roughness'].default_value = 0.02
    fres = nodes.new('ShaderNodeFresnel')
    fres.location = (-200, -80)
    fres.inputs['IOR'].default_value = 1.45
    mixg = nodes.new('ShaderNodeMixShader')
    mixg.location = (180, -40)
    links.new(fres.outputs['Fac'], mixg.inputs['Fac'])
    links.new(glass.outputs['BSDF'], mixg.inputs[1])
    links.new(gloss.outputs['BSDF'], mixg.inputs[2])
    links.new(mixg.outputs['Shader'], out.inputs['Surface'])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = 'BLENDED'
    elif hasattr(mat, "blend_method"):
        mat.blend_method = 'BLEND'
    return mat


def pvc_material(name, base=(0.92, 0.92, 0.90)):
    """PVC/alu laqué des menuiseries: satiné propre"""
    mat = _new_mat(name)
    nodes, links, bsdf = _basic(mat)
    bsdf.inputs['Base Color'].default_value = (*base[:3], 1)
    bsdf.inputs['Roughness'].default_value = 0.28
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = 0.3
    return mat


# ============================================================
# SOL / CONTEXTE
# ============================================================

def ground_material():
    """Pelouse: patchs de verts variés + grain (sans particules pour l'instant)
    ✅ v1.29: slot 'sol' du pack réalisme prioritaire (texture scannée)."""
    maps = _realism_maps('sol')
    if maps:
        return pbr_material("House_Ground_PBR", maps, size=2.0)
    mat = _new_mat("House_Ground")
    nodes, links, bsdf = _basic(mat)

    patches = nodes.new('ShaderNodeTexNoise')
    patches.location = (-650, 150)
    # ✅ v1.9.1: 2 échelles réelles — plaques d'herbe sèche (3-6m) +
    # micro-variation; verts moins saturés (pelouse réelle)
    patches.inputs['Scale'].default_value = 0.18
    patches.inputs['Detail'].default_value = 10.0
    patches.inputs['Roughness'].default_value = 0.65

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-420, 150)
    ramp.color_ramp.elements[0].color = (0.070, 0.095, 0.040, 1)
    ramp.color_ramp.elements[1].color = (0.135, 0.150, 0.070, 1)
    e = ramp.color_ramp.elements.new(0.55)
    e.color = (0.095, 0.120, 0.055, 1)
    links.new(patches.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.95

    fine = nodes.new('ShaderNodeTexNoise')
    fine.location = (-650, -120)
    fine.inputs['Scale'].default_value = 120.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-420, -120)
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.01
    links.new(fine.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


# ============================================================
# CIEL PHYSIQUE + COLOR MANAGEMENT
# ============================================================

def setup_sky_and_view(sun_elevation_deg=38.0, sun_rotation_deg=145.0,
                       exposure=-4.6):
    """✅ LE grand saut lumière: ciel physique Nishita (soleil + atmosphère
    réels, sans fichier HDRI) + color management AgX.

    Le Sky Texture Nishita fournit soleil, dégradé d'horizon et lumière
    d'ambiance physiquement corrects — remplace les 2 soleils + fond uni.
    """
    scene = bpy.context.scene

    # Color management filmique moderne
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass  # Fallback: transform par défaut
    # ✅ Le soleil Nishita est PHYSIQUE (~100k lux): il faut exposer
    # comme un appareil photo (≈ -5 stops en plein soleil avec AgX)
    scene.view_settings.exposure = exposure

    # Monde: Sky Texture Nishita — ou HDRI du pack réalisme s'il y en
    # a un (un vrai ciel photographié se REFLÈTE dans les vitres: le
    # standard des moteurs d'archviz)
    world = bpy.data.worlds.get("House_World") or bpy.data.worlds.new("House_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (300, 0)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.location = (100, 0)
    bg.inputs['Strength'].default_value = 1.0
    hdri = None
    try:
        from . import realism
        hdri = realism.active(
            bpy.context.scene.house_generator).get('hdri')
    except Exception:
        pass
    if hdri:
        # ✅ v1.29.2: VALIDER l'image avant de s'en servir — un .hdr
        # tronqué/corrompu se charge en magenta "texture manquante" et
        # le rendu part tout noir sans explication (vécu au banc)
        himg = None
        try:
            himg = bpy.data.images.load(hdri, check_existing=True)
            if himg.size[0] < 8 or himg.size[1] < 8:
                raise ValueError(f"image vide ({himg.size[0]}x"
                                 f"{himg.size[1]})")
        except Exception as ex:
            print(f"[Look] ⚠️ Ciel HDRI '{os.path.basename(hdri)}' "
                  f"illisible ({ex}) → ciel Nishita procédural")
            if himg is not None:
                try:
                    bpy.data.images.remove(himg)
                except Exception:
                    pass
            himg = None
        if himg is None:
            hdri = None
    if hdri:
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.location = (-200, 0)
        env.image = himg
        mapv = nt.nodes.new('ShaderNodeMapping')
        mapv.location = (-420, 0)
        mapv.inputs['Rotation'].default_value = \
            (0.0, 0.0, math.radians(sun_rotation_deg))
        tc = nt.nodes.new('ShaderNodeTexCoord')
        tc.location = (-620, 0)
        nt.links.new(tc.outputs['Generated'], mapv.inputs['Vector'])
        nt.links.new(mapv.outputs['Vector'], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        for obj in list(bpy.data.objects):
            if obj.name.startswith("House_Sun") or \
                    obj.name.startswith("House_Fill"):
                bpy.data.objects.remove(obj, do_unlink=True)
        print(f"[Look] ✓ Ciel HDRI du pack réalisme: "
              f"{os.path.basename(hdri)}")
        return
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.location = (-200, 0)
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = math.radians(sun_elevation_deg)
    sky.sun_rotation = math.radians(sun_rotation_deg)
    sky.sun_intensity = 1.0
    # ✅ disque solaire élargi → ombres DOUCES (fini le rasoir CG)
    sky.sun_size = math.radians(0.7)
    sky.altitude = 60
    sky.air_density = 1.0
    sky.dust_density = 0.45   # ciel bleu net
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    # ✅ FIX: le lien Background → Output manquait (monde noir!)
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

    # Supprimer les anciens soleils lampes (Nishita inclut le soleil)
    for obj in list(bpy.data.objects):
        if obj.name.startswith("House_Sun") or obj.name.startswith("House_Fill"):
            bpy.data.objects.remove(obj, do_unlink=True)

    print("[Look] ✓ Ciel Nishita + AgX (soleil physique intégré)")
