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


def tile_material(base_color=(0.34, 0.115, 0.062)):
    """Terre cuite: variation de cuisson PAR TUILE + moucheté + bump grain"""
    mat = _new_mat("House_Tile")
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

    # Rugosité vivante (mate mais irrégulière)
    r_ramp = nodes.new('ShaderNodeMapRange')
    r_ramp.location = (-420, -60)
    r_ramp.inputs['To Min'].default_value = 0.55
    r_ramp.inputs['To Max'].default_value = 0.85
    links.new(noise.outputs['Fac'], r_ramp.inputs['Value'])
    links.new(r_ramp.outputs['Result'], bsdf.inputs['Roughness'])

    # Grain de terre cuite (bump fin)
    bump_noise = nodes.new('ShaderNodeTexNoise')
    bump_noise.location = (-700, -260)
    bump_noise.inputs['Scale'].default_value = 180.0
    bump_noise.inputs['Detail'].default_value = 4.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-420, -260)
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.002
    links.new(bump_noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

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


def stucco_material(name="House_Stucco", base=(0.475, 0.40, 0.30)):
    """✅ v1.9.1: ENDUIT TALOCHÉ (crépi) — le matériau des pavillons
    français. Grain fin serré + nuages de teinte à l'échelle du mur +
    micro-salissure au pied. L'aplat lisse faisait maquette."""
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

    # grain taloché fin (bump serré)
    grain = nodes.new('ShaderNodeTexNoise')
    grain.location = (-660, -180)
    grain.inputs['Scale'].default_value = 320.0
    grain.inputs['Detail'].default_value = 3.0
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-440, -180)
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.0016
    links.new(grain.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
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
    glass.inputs['Roughness'].default_value = 0.02
    links.new(glass.outputs['BSDF'], out.inputs['Surface'])
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
    """Pelouse: patchs de verts variés + grain (sans particules pour l'instant)"""
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
    ramp.color_ramp.elements[0].color = (0.075, 0.115, 0.035, 1)
    ramp.color_ramp.elements[1].color = (0.155, 0.185, 0.06, 1)
    e = ramp.color_ramp.elements.new(0.55)
    e.color = (0.105, 0.15, 0.048, 1)
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
        scene.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass  # Fallback: transform par défaut
    # ✅ Le soleil Nishita est PHYSIQUE (~100k lux): il faut exposer
    # comme un appareil photo (≈ -5 stops en plein soleil avec AgX)
    scene.view_settings.exposure = exposure

    # Monde: Sky Texture Nishita
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
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.location = (-200, 0)
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = math.radians(sun_elevation_deg)
    sky.sun_rotation = math.radians(sun_rotation_deg)
    sky.sun_intensity = 0.85
    # ✅ disque solaire élargi → ombres DOUCES (fini le rasoir CG)
    sky.sun_size = math.radians(1.6)
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
