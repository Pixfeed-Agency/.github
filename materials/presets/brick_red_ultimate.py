import bpy
import math

def create_ultimate_red_brick_material_v4_final():
    """Crée un matériau de brique rouge ULTIMATE v4 FINAL avec 12 améliorations avancées"""
    
    mat = bpy.data.materials.new(name="Brique_Rouge_ULTIMATE_v4_FINAL")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    # Activer le displacement
    mat.cycles.displacement_method = 'BOTH'
    
    # === SORTIE ===
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (3000, 0)
    
    # === PRINCIPLED BSDF ===
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (2700, 0)
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    bsdf.inputs['Sheen Weight'].default_value = 0.05
    # Coat Weight sera modulé dynamiquement
    bsdf.inputs['Coat Roughness'].default_value = 0.4
    # Subsurface Weight sera modulé dynamiquement
    bsdf.inputs['Subsurface Radius'].default_value = (0.8, 0.3, 0.2)
    bsdf.inputs['Anisotropic'].default_value = 0.18
    
    # === TEXTURE COORDINATES ===
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-3400, 0)
    
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-3200, 0)
    mapping.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
    
    # === GEOMETRY NODE ===
    geometry = nodes.new('ShaderNodeNewGeometry')
    geometry.location = (-3400, -800)
    
    # === AMBIENT OCCLUSION ===
    ao = nodes.new('ShaderNodeAmbientOcclusion')
    ao.location = (-3400, -1000)
    ao.samples = 16
    ao.inputs['Distance'].default_value = 0.08
    ao.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    
    # === SEPARATE XYZ ===
    separate_xyz = nodes.new('ShaderNodeSeparateXYZ')
    separate_xyz.location = (-3400, -1200)
    links.new(tex_coord.outputs['Object'], separate_xyz.inputs['Vector'])
    
    # === GRADIENT VERTICAL ===
    ramp_vertical = nodes.new('ShaderNodeValToRGB')
    ramp_vertical.location = (-3100, -1200)
    ramp_vertical.color_ramp.elements[0].position = 0.0
    ramp_vertical.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_vertical.color_ramp.elements[1].position = 0.3
    ramp_vertical.color_ramp.elements[1].color = (0.5, 0.5, 0.5, 1.0)
    ramp_vertical.color_ramp.elements.new(1.0)
    ramp_vertical.color_ramp.elements[2].color = (1.0, 1.0, 1.0, 1.0)
    links.new(separate_xyz.outputs['Z'], ramp_vertical.inputs['Fac'])
    
    # === NOUVEAU: COLOR VARIATION PAR BRIQUE (SAFE - Luminosité uniquement) ===
    
    voronoi_brick = nodes.new('ShaderNodeTexVoronoi')
    voronoi_brick.location = (-2900, 1200)
    voronoi_brick.voronoi_dimensions = '3D'
    voronoi_brick.feature = 'F1'
    voronoi_brick.inputs['Scale'].default_value = 6.0
    voronoi_brick.inputs['Randomness'].default_value = 1.0
    links.new(mapping.outputs['Vector'], voronoi_brick.inputs['Vector'])
    
    # MapRange pour variation SAFE de luminosité (0.93 à 1.07)
    map_range_brick_value = nodes.new('ShaderNodeMapRange')
    map_range_brick_value.location = (-2600, 1200)
    map_range_brick_value.inputs['From Min'].default_value = 0.0
    map_range_brick_value.inputs['From Max'].default_value = 1.0
    map_range_brick_value.inputs['To Min'].default_value = 0.93  # SAFE range
    map_range_brick_value.inputs['To Max'].default_value = 1.07  # SAFE range
    links.new(voronoi_brick.outputs['Distance'], map_range_brick_value.inputs['Value'])
    
    # === NOUVEAU: TRANSLUCENCY MAPPING (Subsurface variable) ===
    
    # Voronoi pour détecter zones poreuses
    voronoi_porous = nodes.new('ShaderNodeTexVoronoi')
    voronoi_porous.location = (-2900, 1000)
    voronoi_porous.voronoi_dimensions = '3D'
    voronoi_porous.feature = 'DISTANCE_TO_EDGE'
    voronoi_porous.inputs['Scale'].default_value = 45.0  # Haute fréquence pour porosité
    voronoi_porous.inputs['Randomness'].default_value = 1.0
    links.new(mapping.outputs['Vector'], voronoi_porous.inputs['Vector'])
    
    # ColorRamp pour accentuer zones poreuses
    ramp_porous = nodes.new('ShaderNodeValToRGB')
    ramp_porous.location = (-2600, 1000)
    ramp_porous.color_ramp.elements[0].position = 0.4
    ramp_porous.color_ramp.elements[1].position = 0.7
    links.new(voronoi_porous.outputs['Distance'], ramp_porous.inputs['Fac'])
    
    # MapRange pour Subsurface Weight (0.005 à 0.015)
    map_range_subsurface = nodes.new('ShaderNodeMapRange')
    map_range_subsurface.location = (-2300, 1000)
    map_range_subsurface.inputs['From Min'].default_value = 0.0
    map_range_subsurface.inputs['From Max'].default_value = 1.0
    map_range_subsurface.inputs['To Min'].default_value = 0.005
    map_range_subsurface.inputs['To Max'].default_value = 0.015
    links.new(ramp_porous.outputs['Color'], map_range_subsurface.inputs['Value'])
    
    # === COUCHE 1: COULEUR BASE COMPLEXE ===
    
    voronoi_organic = nodes.new('ShaderNodeTexVoronoi')
    voronoi_organic.location = (-2900, 800)
    voronoi_organic.voronoi_dimensions = '3D'
    voronoi_organic.feature = 'F2'
    voronoi_organic.inputs['Scale'].default_value = 2.8
    voronoi_organic.inputs['Randomness'].default_value = 1.0
    links.new(mapping.outputs['Vector'], voronoi_organic.inputs['Vector'])
    
    noise_organic_mod = nodes.new('ShaderNodeTexNoise')
    noise_organic_mod.location = (-2900, 600)
    noise_organic_mod.inputs['Scale'].default_value = 4.5
    noise_organic_mod.inputs['Detail'].default_value = 10.0
    noise_organic_mod.inputs['Roughness'].default_value = 0.6
    noise_organic_mod.inputs['Distortion'].default_value = 1.2
    links.new(mapping.outputs['Vector'], noise_organic_mod.inputs['Vector'])
    
    mix_organic = nodes.new('ShaderNodeMix')
    mix_organic.data_type = 'FLOAT'
    mix_organic.blend_type = 'MULTIPLY'
    mix_organic.location = (-2600, 700)
    mix_organic.inputs[0].default_value = 1.0
    links.new(voronoi_organic.outputs['Distance'], mix_organic.inputs[2])
    links.new(noise_organic_mod.outputs['Fac'], mix_organic.inputs[3])
    
    noise_large = nodes.new('ShaderNodeTexNoise')
    noise_large.location = (-2900, 400)
    noise_large.inputs['Scale'].default_value = 5.0
    noise_large.inputs['Detail'].default_value = 4.0
    noise_large.inputs['Roughness'].default_value = 0.5
    noise_large.inputs['Distortion'].default_value = 0.8
    links.new(mapping.outputs['Vector'], noise_large.inputs['Vector'])
    
    noise_medium = nodes.new('ShaderNodeTexNoise')
    noise_medium.location = (-2900, 200)
    noise_medium.inputs['Scale'].default_value = 18.0
    noise_medium.inputs['Detail'].default_value = 12.0
    noise_medium.inputs['Roughness'].default_value = 0.65
    noise_medium.inputs['Distortion'].default_value = 0.3
    links.new(mapping.outputs['Vector'], noise_medium.inputs['Vector'])
    
    noise_fine = nodes.new('ShaderNodeTexNoise')
    noise_fine.location = (-2900, 0)
    noise_fine.inputs['Scale'].default_value = 45.0
    noise_fine.inputs['Detail'].default_value = 16.0
    noise_fine.inputs['Roughness'].default_value = 0.75
    links.new(mapping.outputs['Vector'], noise_fine.inputs['Vector'])
    
    mix_organic_large = nodes.new('ShaderNodeMix')
    mix_organic_large.data_type = 'FLOAT'
    mix_organic_large.blend_type = 'ADD'
    mix_organic_large.location = (-2400, 550)
    mix_organic_large.inputs[0].default_value = 0.45
    links.new(mix_organic.outputs[1], mix_organic_large.inputs[2])
    links.new(noise_large.outputs['Fac'], mix_organic_large.inputs[3])
    
    mix_freq1 = nodes.new('ShaderNodeMix')
    mix_freq1.data_type = 'FLOAT'
    mix_freq1.blend_type = 'ADD'
    mix_freq1.location = (-2200, 350)
    mix_freq1.inputs[0].default_value = 0.6
    links.new(mix_organic_large.outputs[1], mix_freq1.inputs[2])
    links.new(noise_medium.outputs['Fac'], mix_freq1.inputs[3])
    
    mix_freq2 = nodes.new('ShaderNodeMix')
    mix_freq2.data_type = 'FLOAT'
    mix_freq2.blend_type = 'ADD'
    mix_freq2.location = (-2000, 350)
    mix_freq2.inputs[0].default_value = 0.3
    links.new(mix_freq1.outputs[1], mix_freq2.inputs[2])
    links.new(noise_fine.outputs['Fac'], mix_freq2.inputs[3])
    
    ramp_color = nodes.new('ShaderNodeValToRGB')
    ramp_color.location = (-1800, 350)
    ramp_color.color_ramp.interpolation = 'B_SPLINE'
    
    ramp_color.color_ramp.elements[0].position = 0.0
    ramp_color.color_ramp.elements[0].color = (0.38, 0.10, 0.07, 1.0)
    
    ramp_color.color_ramp.elements.new(0.25)
    ramp_color.color_ramp.elements[1].color = (0.52, 0.15, 0.10, 1.0)
    
    ramp_color.color_ramp.elements.new(0.5)
    ramp_color.color_ramp.elements[2].color = (0.61, 0.19, 0.13, 1.0)
    
    ramp_color.color_ramp.elements.new(0.75)
    ramp_color.color_ramp.elements[3].color = (0.68, 0.24, 0.17, 1.0)
    
    ramp_color.color_ramp.elements[4].position = 1.0
    ramp_color.color_ramp.elements[4].color = (0.74, 0.30, 0.21, 1.0)
    
    links.new(mix_freq2.outputs[1], ramp_color.inputs['Fac'])
    
    # NOUVEAU: Appliquer variation SAFE de luminosité par brique (RGB Mix)
    mix_brick_brightness = nodes.new('ShaderNodeMix')
    mix_brick_brightness.data_type = 'RGBA'
    mix_brick_brightness.blend_type = 'MULTIPLY'
    mix_brick_brightness.location = (-1600, 350)
    mix_brick_brightness.inputs[0].default_value = 1.0
    links.new(ramp_color.outputs['Color'], mix_brick_brightness.inputs[6])
    
    # Convertir MapRange (float) en RGB pour multiplication
    combine_rgb_brightness = nodes.new('ShaderNodeCombineColor')
    combine_rgb_brightness.location = (-1800, 200)
    links.new(map_range_brick_value.outputs['Result'], combine_rgb_brightness.inputs['Red'])
    links.new(map_range_brick_value.outputs['Result'], combine_rgb_brightness.inputs['Green'])
    links.new(map_range_brick_value.outputs['Result'], combine_rgb_brightness.inputs['Blue'])
    links.new(combine_rgb_brightness.outputs['Color'], mix_brick_brightness.inputs[7])
    
    # === COUCHE 2: SALISSURES ===
    
    voronoi_dirt = nodes.new('ShaderNodeTexVoronoi')
    voronoi_dirt.location = (-2900, -200)
    voronoi_dirt.voronoi_dimensions = '3D'
    voronoi_dirt.feature = 'DISTANCE_TO_EDGE'
    voronoi_dirt.inputs['Scale'].default_value = 12.0
    voronoi_dirt.inputs['Randomness'].default_value = 0.8
    links.new(mapping.outputs['Vector'], voronoi_dirt.inputs['Vector'])
    
    noise_stains = nodes.new('ShaderNodeTexNoise')
    noise_stains.location = (-2900, -400)
    noise_stains.inputs['Scale'].default_value = 6.5
    noise_stains.inputs['Detail'].default_value = 15.0
    noise_stains.inputs['Roughness'].default_value = 0.7
    noise_stains.inputs['Distortion'].default_value = 1.5
    links.new(mapping.outputs['Vector'], noise_stains.inputs['Vector'])
    
    ramp_stains = nodes.new('ShaderNodeValToRGB')
    ramp_stains.location = (-2600, -400)
    ramp_stains.color_ramp.elements[0].position = 0.35
    ramp_stains.color_ramp.elements[1].position = 0.65
    links.new(noise_stains.outputs['Fac'], ramp_stains.inputs['Fac'])
    
    noise_efflo = nodes.new('ShaderNodeTexNoise')
    noise_efflo.location = (-2900, -600)
    noise_efflo.inputs['Scale'].default_value = 30.0
    noise_efflo.inputs['Detail'].default_value = 10.0
    links.new(mapping.outputs['Vector'], noise_efflo.inputs['Vector'])
    
    ramp_efflo = nodes.new('ShaderNodeValToRGB')
    ramp_efflo.location = (-2600, -600)
    ramp_efflo.color_ramp.elements[0].position = 0.75
    ramp_efflo.color_ramp.elements[1].position = 0.85
    links.new(noise_efflo.outputs['Fac'], ramp_efflo.inputs['Fac'])
    
    # === MOISTURE MAP ===
    
    noise_moisture = nodes.new('ShaderNodeTexNoise')
    noise_moisture.location = (-2900, -800)
    noise_moisture.inputs['Scale'].default_value = 4.0
    noise_moisture.inputs['Detail'].default_value = 8.0
    noise_moisture.inputs['Roughness'].default_value = 0.6
    noise_moisture.inputs['Distortion'].default_value = 2.5
    links.new(mapping.outputs['Vector'], noise_moisture.inputs['Vector'])
    
    ramp_moisture = nodes.new('ShaderNodeValToRGB')
    ramp_moisture.location = (-2600, -800)
    ramp_moisture.color_ramp.elements[0].position = 0.65
    ramp_moisture.color_ramp.elements[1].position = 0.78
    links.new(noise_moisture.outputs['Fac'], ramp_moisture.inputs['Fac'])
    
    invert_vertical = nodes.new('ShaderNodeInvert')
    invert_vertical.location = (-2800, -1200)
    links.new(ramp_vertical.outputs['Color'], invert_vertical.inputs['Color'])
    
    mix_moisture_vertical = nodes.new('ShaderNodeMix')
    mix_moisture_vertical.data_type = 'FLOAT'
    mix_moisture_vertical.blend_type = 'MULTIPLY'
    mix_moisture_vertical.location = (-2400, -900)
    mix_moisture_vertical.inputs[0].default_value = 1.0
    links.new(ramp_moisture.outputs['Color'], mix_moisture_vertical.inputs[2])
    links.new(invert_vertical.outputs['Color'], mix_moisture_vertical.inputs[3])
    
    # === WEATHERING LAYERS ===
    
    invert_ao = nodes.new('ShaderNodeInvert')
    invert_ao.location = (-3100, -1000)
    links.new(ao.outputs['AO'], invert_ao.inputs['Color'])
    
    ramp_weathering = nodes.new('ShaderNodeValToRGB')
    ramp_weathering.location = (-2900, -1000)
    ramp_weathering.color_ramp.elements[0].position = 0.3
    ramp_weathering.color_ramp.elements[1].position = 0.7
    links.new(invert_ao.outputs['Color'], ramp_weathering.inputs['Fac'])
    
    noise_weathering = nodes.new('ShaderNodeTexNoise')
    noise_weathering.location = (-2900, -1150)
    noise_weathering.inputs['Scale'].default_value = 20.0
    noise_weathering.inputs['Detail'].default_value = 12.0
    links.new(mapping.outputs['Vector'], noise_weathering.inputs['Vector'])
    
    mix_weathering = nodes.new('ShaderNodeMix')
    mix_weathering.data_type = 'FLOAT'
    mix_weathering.blend_type = 'MULTIPLY'
    mix_weathering.location = (-2600, -1075)
    mix_weathering.inputs[0].default_value = 1.0
    links.new(ramp_weathering.outputs['Color'], mix_weathering.inputs[2])
    links.new(noise_weathering.outputs['Fac'], mix_weathering.inputs[3])
    
    # === EDGE WEAR ===
    
    ramp_edge = nodes.new('ShaderNodeValToRGB')
    ramp_edge.location = (-3100, -800)
    ramp_edge.color_ramp.elements[0].position = 0.82
    ramp_edge.color_ramp.elements[1].position = 0.92
    links.new(geometry.outputs['Pointiness'], ramp_edge.inputs['Fac'])
    
    rgb_edge_color = nodes.new('ShaderNodeRGB')
    rgb_edge_color.location = (-2900, -900)
    rgb_edge_color.outputs[0].default_value = (0.78, 0.36, 0.26, 1.0)
    
    # === MIXAGE COULEURS ===
    
    mix_stains = nodes.new('ShaderNodeMix')
    mix_stains.data_type = 'RGBA'
    mix_stains.blend_type = 'MULTIPLY'
    mix_stains.location = (-1400, 250)
    mix_stains.inputs[7].default_value = (0.12, 0.08, 0.06, 1.0)
    links.new(ramp_stains.outputs['Color'], mix_stains.inputs[0])
    links.new(mix_brick_brightness.outputs[2], mix_stains.inputs[6])
    
    mix_efflo = nodes.new('ShaderNodeMix')
    mix_efflo.data_type = 'RGBA'
    mix_efflo.blend_type = 'MIX'
    mix_efflo.location = (-1200, 250)
    mix_efflo.inputs[7].default_value = (0.85, 0.82, 0.78, 1.0)
    links.new(ramp_efflo.outputs['Color'], mix_efflo.inputs[0])
    links.new(mix_stains.outputs[2], mix_efflo.inputs[6])
    
    mix_weathering_color = nodes.new('ShaderNodeMix')
    mix_weathering_color.data_type = 'RGBA'
    mix_weathering_color.blend_type = 'MULTIPLY'
    mix_weathering_color.location = (-1000, 250)
    mix_weathering_color.inputs[7].default_value = (0.25, 0.18, 0.15, 1.0)
    links.new(mix_weathering.outputs[1], mix_weathering_color.inputs[0])
    links.new(mix_efflo.outputs[2], mix_weathering_color.inputs[6])
    
    mix_ao_color = nodes.new('ShaderNodeMix')
    mix_ao_color.data_type = 'RGBA'
    mix_ao_color.blend_type = 'MULTIPLY'
    mix_ao_color.location = (-800, 250)
    mix_ao_color.inputs[0].default_value = 0.4
    links.new(ao.outputs['Color'], mix_ao_color.inputs[0])
    links.new(mix_weathering_color.outputs[2], mix_ao_color.inputs[6])
    rgb_ao_darken = nodes.new('ShaderNodeRGB')
    rgb_ao_darken.location = (-1000, 50)
    rgb_ao_darken.outputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    links.new(rgb_ao_darken.outputs[0], mix_ao_color.inputs[7])
    
    mix_vertical_color = nodes.new('ShaderNodeMix')
    mix_vertical_color.data_type = 'RGBA'
    mix_vertical_color.blend_type = 'MULTIPLY'
    mix_vertical_color.location = (-600, 250)
    links.new(ramp_vertical.outputs['Color'], mix_vertical_color.inputs[0])
    links.new(mix_ao_color.outputs[2], mix_vertical_color.inputs[6])
    rgb_dark_bottom = nodes.new('ShaderNodeRGB')
    rgb_dark_bottom.location = (-800, 50)
    rgb_dark_bottom.outputs[0].default_value = (0.7, 0.7, 0.7, 1.0)
    links.new(rgb_dark_bottom.outputs[0], mix_vertical_color.inputs[7])
    
    mix_moisture_color = nodes.new('ShaderNodeMix')
    mix_moisture_color.data_type = 'RGBA'
    mix_moisture_color.blend_type = 'MULTIPLY'
    mix_moisture_color.location = (-400, 250)
    mix_moisture_color.inputs[7].default_value = (0.65, 0.65, 0.65, 1.0)
    links.new(mix_moisture_vertical.outputs[1], mix_moisture_color.inputs[0])
    links.new(mix_vertical_color.outputs[2], mix_moisture_color.inputs[6])
    
    mix_edge = nodes.new('ShaderNodeMix')
    mix_edge.data_type = 'RGBA'
    mix_edge.blend_type = 'MIX'
    mix_edge.location = (-200, 250)
    links.new(ramp_edge.outputs['Color'], mix_edge.inputs[0])
    links.new(mix_moisture_color.outputs[2], mix_edge.inputs[6])
    links.new(rgb_edge_color.outputs[0], mix_edge.inputs[7])
    
    hue_sat = nodes.new('ShaderNodeHueSaturation')
    hue_sat.location = (0, 250)
    hue_sat.inputs['Saturation'].default_value = 0.9
    hue_sat.inputs['Value'].default_value = 1.05
    links.new(mix_edge.outputs[2], hue_sat.inputs['Color'])
    links.new(hue_sat.outputs['Color'], bsdf.inputs['Base Color'])
    
    # === RELIEF (DOUBLE BUMP) ===
    
    voronoi_relief = nodes.new('ShaderNodeTexVoronoi')
    voronoi_relief.location = (-2900, -1500)
    voronoi_relief.voronoi_dimensions = '3D'
    voronoi_relief.feature = 'SMOOTH_F1'
    voronoi_relief.inputs['Scale'].default_value = 5.5
    voronoi_relief.inputs['Smoothness'].default_value = 0.8
    voronoi_relief.inputs['Randomness'].default_value = 1.0
    links.new(mapping.outputs['Vector'], voronoi_relief.inputs['Vector'])
    
    noise_relief_mod = nodes.new('ShaderNodeTexNoise')
    noise_relief_mod.location = (-2900, -1650)
    noise_relief_mod.inputs['Scale'].default_value = 7.0
    noise_relief_mod.inputs['Detail'].default_value = 8.0
    noise_relief_mod.inputs['Roughness'].default_value = 0.65
    noise_relief_mod.inputs['Distortion'].default_value = 0.8
    links.new(mapping.outputs['Vector'], noise_relief_mod.inputs['Vector'])
    
    mix_voronoi_relief = nodes.new('ShaderNodeMix')
    mix_voronoi_relief.data_type = 'FLOAT'
    mix_voronoi_relief.blend_type = 'MULTIPLY'
    mix_voronoi_relief.location = (-2600, -1575)
    mix_voronoi_relief.inputs[0].default_value = 1.0
    links.new(voronoi_relief.outputs['Distance'], mix_voronoi_relief.inputs[2])
    links.new(noise_relief_mod.outputs['Fac'], mix_voronoi_relief.inputs[3])
    
    noise_macro = nodes.new('ShaderNodeTexNoise')
    noise_macro.location = (-2900, -1800)
    noise_macro.inputs['Scale'].default_value = 8.0
    noise_macro.inputs['Detail'].default_value = 4.0
    noise_macro.inputs['Roughness'].default_value = 0.5
    links.new(mapping.outputs['Vector'], noise_macro.inputs['Vector'])
    
    noise_meso = nodes.new('ShaderNodeTexNoise')
    noise_meso.location = (-2900, -2000)
    noise_meso.inputs['Scale'].default_value = 35.0
    noise_meso.inputs['Detail'].default_value = 10.0
    noise_meso.inputs['Roughness'].default_value = 0.6
    links.new(mapping.outputs['Vector'], noise_meso.inputs['Vector'])
    
    noise_micro = nodes.new('ShaderNodeTexNoise')
    noise_micro.location = (-2900, -2200)
    noise_micro.inputs['Scale'].default_value = 120.0
    noise_micro.inputs['Detail'].default_value = 16.0
    noise_micro.inputs['Roughness'].default_value = 0.8
    links.new(mapping.outputs['Vector'], noise_micro.inputs['Vector'])
    
    noise_ultra_fine = nodes.new('ShaderNodeTexNoise')
    noise_ultra_fine.location = (-2900, -2400)
    noise_ultra_fine.inputs['Scale'].default_value = 250.0
    noise_ultra_fine.inputs['Detail'].default_value = 16.0
    noise_ultra_fine.inputs['Roughness'].default_value = 0.9
    links.new(mapping.outputs['Vector'], noise_ultra_fine.inputs['Vector'])
    
    voronoi_grain = nodes.new('ShaderNodeTexVoronoi')
    voronoi_grain.location = (-2900, -2600)
    voronoi_grain.voronoi_dimensions = '3D'
    voronoi_grain.feature = 'F1'
    voronoi_grain.inputs['Scale'].default_value = 200.0
    links.new(mapping.outputs['Vector'], voronoi_grain.inputs['Vector'])
    
    mix_organic_macro = nodes.new('ShaderNodeMix')
    mix_organic_macro.data_type = 'FLOAT'
    mix_organic_macro.blend_type = 'ADD'
    mix_organic_macro.location = (-2400, -1700)
    mix_organic_macro.inputs[0].default_value = 0.4
    links.new(mix_voronoi_relief.outputs[1], mix_organic_macro.inputs[2])
    links.new(noise_macro.outputs['Fac'], mix_organic_macro.inputs[3])
    
    mix_relief1 = nodes.new('ShaderNodeMix')
    mix_relief1.data_type = 'FLOAT'
    mix_relief1.blend_type = 'ADD'
    mix_relief1.location = (-2200, -1900)
    mix_relief1.inputs[0].default_value = 0.4
    links.new(mix_organic_macro.outputs[1], mix_relief1.inputs[2])
    links.new(noise_meso.outputs['Fac'], mix_relief1.inputs[3])
    
    mix_relief2 = nodes.new('ShaderNodeMix')
    mix_relief2.data_type = 'FLOAT'
    mix_relief2.blend_type = 'ADD'
    mix_relief2.location = (-2000, -1900)
    mix_relief2.inputs[0].default_value = 0.3
    links.new(mix_relief1.outputs[1], mix_relief2.inputs[2])
    links.new(noise_micro.outputs['Fac'], mix_relief2.inputs[3])
    
    mix_relief3 = nodes.new('ShaderNodeMix')
    mix_relief3.data_type = 'FLOAT'
    mix_relief3.blend_type = 'ADD'
    mix_relief3.location = (-1800, -1900)
    mix_relief3.inputs[0].default_value = 0.15
    links.new(mix_relief2.outputs[1], mix_relief3.inputs[2])
    links.new(voronoi_grain.outputs['Distance'], mix_relief3.inputs[3])
    
    map_range_bump = nodes.new('ShaderNodeMapRange')
    map_range_bump.location = (-1600, -1900)
    map_range_bump.inputs['From Min'].default_value = 0.0
    map_range_bump.inputs['From Max'].default_value = 3.5
    map_range_bump.inputs['To Min'].default_value = 0.0
    map_range_bump.inputs['To Max'].default_value = 1.0
    links.new(mix_relief3.outputs[1], map_range_bump.inputs['Value'])
    
    bump1 = nodes.new('ShaderNodeBump')
    bump1.location = (-1400, -1900)
    bump1.inputs['Strength'].default_value = 0.7
    bump1.inputs['Distance'].default_value = 0.018
    links.new(map_range_bump.outputs['Result'], bump1.inputs['Height'])
    
    bump2 = nodes.new('ShaderNodeBump')
    bump2.location = (-1200, -1900)
    bump2.inputs['Strength'].default_value = 0.4
    bump2.inputs['Distance'].default_value = 0.003
    links.new(noise_ultra_fine.outputs['Fac'], bump2.inputs['Height'])
    links.new(bump1.outputs['Normal'], bump2.inputs['Normal'])
    
    normal_map = nodes.new('ShaderNodeNormalMap')
    normal_map.location = (-1000, -1900)
    normal_map.inputs['Strength'].default_value = 0.5
    links.new(bump2.outputs['Normal'], normal_map.inputs['Color'])
    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    
    # === DISPLACEMENT ===
    
    displacement = nodes.new('ShaderNodeDisplacement')
    displacement.location = (3000, -400)
    displacement.inputs['Scale'].default_value = 0.005
    displacement.inputs['Midlevel'].default_value = 0.5
    
    mix_displacement = nodes.new('ShaderNodeMix')
    mix_displacement.data_type = 'FLOAT'
    mix_displacement.blend_type = 'MIX'
    mix_displacement.location = (2800, -400)
    mix_displacement.inputs[3].default_value = 0.3
    links.new(ramp_edge.outputs['Color'], mix_displacement.inputs[0])
    links.new(map_range_bump.outputs['Result'], mix_displacement.inputs[2])
    
    links.new(mix_displacement.outputs[1], displacement.inputs['Height'])
    links.new(displacement.outputs['Displacement'], output.inputs['Displacement'])
    
    # === ROUGHNESS ===
    
    noise_rough_base = nodes.new('ShaderNodeTexNoise')
    noise_rough_base.location = (-2900, -2800)
    noise_rough_base.inputs['Scale'].default_value = 25.0
    noise_rough_base.inputs['Detail'].default_value = 8.0
    links.new(mapping.outputs['Vector'], noise_rough_base.inputs['Vector'])
    
    noise_worn = nodes.new('ShaderNodeTexNoise')
    noise_worn.location = (-2900, -3000)
    noise_worn.inputs['Scale'].default_value = 8.0
    noise_worn.inputs['Detail'].default_value = 4.0
    links.new(mapping.outputs['Vector'], noise_worn.inputs['Vector'])
    
    ramp_worn = nodes.new('ShaderNodeValToRGB')
    ramp_worn.location = (-2600, -3000)
    ramp_worn.color_ramp.elements[0].position = 0.6
    ramp_worn.color_ramp.elements[1].position = 0.7
    links.new(noise_worn.outputs['Fac'], ramp_worn.inputs['Fac'])
    
    mix_rough = nodes.new('ShaderNodeMix')
    mix_rough.data_type = 'FLOAT'
    mix_rough.blend_type = 'MIX'
    mix_rough.location = (-2400, -2900)
    mix_rough.inputs[2].default_value = 0.78
    mix_rough.inputs[3].default_value = 0.55
    links.new(ramp_worn.outputs['Color'], mix_rough.inputs[0])
    
    map_range_rough = nodes.new('ShaderNodeMapRange')
    map_range_rough.location = (-2200, -2900)
    map_range_rough.inputs['From Min'].default_value = 0.0
    map_range_rough.inputs['From Max'].default_value = 1.0
    map_range_rough.inputs['To Min'].default_value = 0.65
    map_range_rough.inputs['To Max'].default_value = 0.88
    links.new(noise_rough_base.outputs['Fac'], map_range_rough.inputs['Value'])
    
    mix_rough_final = nodes.new('ShaderNodeMix')
    mix_rough_final.data_type = 'FLOAT'
    mix_rough_final.blend_type = 'MULTIPLY'
    mix_rough_final.location = (-2000, -2900)
    mix_rough_final.inputs[0].default_value = 0.5
    links.new(map_range_rough.outputs['Result'], mix_rough_final.inputs[2])
    links.new(mix_rough.outputs[1], mix_rough_final.inputs[3])
    
    mix_rough_weathering = nodes.new('ShaderNodeMix')
    mix_rough_weathering.data_type = 'FLOAT'
    mix_rough_weathering.blend_type = 'MIX'
    mix_rough_weathering.location = (-1800, -2900)
    mix_rough_weathering.inputs[3].default_value = 0.92
    links.new(mix_weathering.outputs[1], mix_rough_weathering.inputs[0])
    links.new(mix_rough_final.outputs[1], mix_rough_weathering.inputs[2])
    
    mix_rough_moisture = nodes.new('ShaderNodeMix')
    mix_rough_moisture.data_type = 'FLOAT'
    mix_rough_moisture.blend_type = 'MIX'
    mix_rough_moisture.location = (-1600, -2900)
    mix_rough_moisture.inputs[3].default_value = 0.35
    links.new(mix_moisture_vertical.outputs[1], mix_rough_moisture.inputs[0])
    links.new(mix_rough_weathering.outputs[1], mix_rough_moisture.inputs[2])
    
    mix_rough_edge = nodes.new('ShaderNodeMix')
    mix_rough_edge.data_type = 'FLOAT'
    mix_rough_edge.blend_type = 'MIX'
    mix_rough_edge.location = (-1400, -2900)
    mix_rough_edge.inputs[3].default_value = 0.45
    links.new(ramp_edge.outputs['Color'], mix_rough_edge.inputs[0])
    links.new(mix_rough_moisture.outputs[1], mix_rough_edge.inputs[2])
    
    links.new(mix_rough_edge.outputs[1], bsdf.inputs['Roughness'])
    
    # === ANISOTROPIE ===
    
    noise_aniso = nodes.new('ShaderNodeTexNoise')
    noise_aniso.location = (-2900, -3200)
    noise_aniso.inputs['Scale'].default_value = 15.0
    noise_aniso.inputs['Detail'].default_value = 8.0
    links.new(mapping.outputs['Vector'], noise_aniso.inputs['Vector'])
    
    map_range_aniso = nodes.new('ShaderNodeMapRange')
    map_range_aniso.location = (-2600, -3200)
    map_range_aniso.inputs['From Min'].default_value = 0.0
    map_range_aniso.inputs['From Max'].default_value = 1.0
    map_range_aniso.inputs['To Min'].default_value = 0.0
    map_range_aniso.inputs['To Max'].default_value = 0.35
    links.new(noise_aniso.outputs['Fac'], map_range_aniso.inputs['Value'])
    
    mix_aniso_vertical = nodes.new('ShaderNodeMix')
    mix_aniso_vertical.data_type = 'FLOAT'
    mix_aniso_vertical.blend_type = 'MIX'
    mix_aniso_vertical.location = (-2400, -3200)
    mix_aniso_vertical.inputs[0].default_value = 0.3
    mix_aniso_vertical.inputs[3].default_value = 0.15
    links.new(invert_vertical.outputs['Color'], mix_aniso_vertical.inputs[0])
    links.new(map_range_aniso.outputs['Result'], mix_aniso_vertical.inputs[2])
    
    links.new(mix_aniso_vertical.outputs[1], bsdf.inputs['Anisotropic Rotation'])
    
    # === NOUVEAU: CLEARCOAT INTELLIGENT ===
    
    # Coat Weight modulé par moisture + edge wear
    mix_coat_moisture = nodes.new('ShaderNodeMix')
    mix_coat_moisture.data_type = 'FLOAT'
    mix_coat_moisture.blend_type = 'MIX'
    mix_coat_moisture.location = (-1400, -3400)
    mix_coat_moisture.inputs[2].default_value = 0.02  # Coat normal (sec)
    mix_coat_moisture.inputs[3].default_value = 0.12  # Coat élevé (humide)
    links.new(mix_moisture_vertical.outputs[1], mix_coat_moisture.inputs[0])
    
    # Réduire coat sur zones usées (bords)
    mix_coat_edge = nodes.new('ShaderNodeMix')
    mix_coat_edge.data_type = 'FLOAT'
    mix_coat_edge.blend_type = 'MIX'
    mix_coat_edge.location = (-1200, -3400)
    mix_coat_edge.inputs[3].default_value = 0.005  # Coat très faible (usé)
    links.new(ramp_edge.outputs['Color'], mix_coat_edge.inputs[0])
    links.new(mix_coat_moisture.outputs[1], mix_coat_edge.inputs[2])
    
    # Augmenter coat dans zones sales/weathered (légèrement gras)
    mix_coat_weathering = nodes.new('ShaderNodeMix')
    mix_coat_weathering.data_type = 'FLOAT'
    mix_coat_weathering.blend_type = 'ADD'
    mix_coat_weathering.location = (-1000, -3400)
    mix_coat_weathering.inputs[0].default_value = 0.15  # Factor faible
    mix_coat_weathering.inputs[3].default_value = 0.04  # Ajout subtil
    links.new(mix_weathering.outputs[1], mix_coat_weathering.inputs[0])
    links.new(mix_coat_edge.outputs[1], mix_coat_weathering.inputs[2])
    
    links.new(mix_coat_weathering.outputs[1], bsdf.inputs['Coat Weight'])
    
    # === NOUVEAU: TRANSLUCENCY MAPPING (Subsurface variable) - CONNEXION FINALE ===
    
    # Modulation supplémentaire par edge (bords moins translucides)
    mix_subsurface_edge = nodes.new('ShaderNodeMix')
    mix_subsurface_edge.data_type = 'FLOAT'
    mix_subsurface_edge.blend_type = 'MIX'
    mix_subsurface_edge.location = (-2000, 1000)
    mix_subsurface_edge.inputs[3].default_value = 0.003  # Moins translucide sur bords
    links.new(ramp_edge.outputs['Color'], mix_subsurface_edge.inputs[0])
    links.new(map_range_subsurface.outputs['Result'], mix_subsurface_edge.inputs[2])
    
    links.new(mix_subsurface_edge.outputs[1], bsdf.inputs['Subsurface Weight'])
    
    # === SORTIE ===
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat



# Alias pour compatibilité avec l'ancien nom de fonction
create_brick_red_ultimate = create_ultimate_red_brick_material_v4_final