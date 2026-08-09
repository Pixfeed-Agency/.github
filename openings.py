# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Spec d'ouverture unifiée (chantier S4)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""SPEC D'OUVERTURE UNIFIÉE — une seule vérité pour tous les trous.

Avant S4, QUATRE implémentations parallèles calculaient les ouvertures:
les trous des murs briques, les cutters Boolean des murs simples, les
menuiseries visibles et les volets — à garder synchrones à la main
(l'historique: fenêtres décalées d'une demi-hauteur, jeux entre trou et
menuiserie, seuils d'exclusion balcon DIVERGENTS entre trous et
fenêtres).

Désormais `compute(op, props)` produit LA liste, et chacun la consomme:
- murs briques   → trous par rangées (format historique conservé)
- murs simples   → cutters Boolean (dérivés du même dict)
- menuiseries    → objets fenêtres/portes aux mêmes centres
- volets         → specs aux mêmes positions

Chaque ouverture: {x, y, z (coin bas), width, height, depth, wall,
type ('door'|'window'|'passage'), along (centre le long du mur),
floor}.

✅ S4 "pilotée par les pièces": en mode PROGRAMME, les fenêtres
arrière sont placées AU CENTRE DE CHAQUE CELLULE (chambres, SdB, WC)
au lieu de l'espacement uniforme — la façade découle du plan.
"""


def _back_positions(op, props, width, num_windows_back):
    """Positions x des fenêtres ARRIÈRE.

    Uniforme (historique), ou UNE PAR PIÈCE quand le programme pilote
    la distribution (même échelle que interior_layout: les largeurs de
    cellules sont normalisées sur la largeur intérieure)."""
    from . import rooms
    rt = rooms.spec(props)
    if rt or getattr(props, 'programme_active', False):
        if rt:
            # ✅ v1.27: une fenêtre AU CENTRE DE CHAQUE PIÈCE du tableau
            cells = [r['surface'] for r in rt]
        else:
            try:
                cells = [float(v) for v in
                         getattr(props, 'programme_cells', '').split(',')
                         if v.strip()]
            except ValueError:
                cells = []
        if len(cells) >= 2:
            t = op._get_wall_depth(props)
            inner = width - 2 * t
            scale = inner / sum(cells)
            xs, acc = [], t
            for cw in cells:
                xs.append(acc + cw * scale / 2)   # centre de la cellule
                acc += cw * scale
            return xs
    spacing = width / (num_windows_back + 1)
    return [spacing * (i + 1) for i in range(num_windows_back)]


def table_spec(op, props):
    """✅ TABLEAU D'OUVERTURES: la liste construite depuis les lignes
    utilisateur — types, tailles, allèges et positions LIBRES par
    façade (le manque n°1 des briefs réels). Prime sur l'auto."""
    W, L = props.house_width, props.house_length
    wall_depth = op._get_wall_depth(props)
    if getattr(op, 'real_wall_height', None):
        fha = op.real_wall_height / props.num_floors
    else:
        fha = props.floor_height
    out = []
    for it in props.openings_table:
        is_door = it.item_type == 'DOOR'
        wall = it.wall.lower()
        w_, h_ = it.width, it.height
        along = max(w_ / 2 + 0.1,
                    min(it.pos, (W if wall in ('front', 'back') else L)
                        - w_ / 2 - 0.1))
        if is_door and it.floor == 0:
            z = op._plinth_visible(props)
        else:
            z = it.floor * fha + (0.0 if is_door else it.sill)
        d = {'width': w_, 'height': h_, 'depth': wall_depth,
             'wall': wall, 'type': 'door' if is_door else 'window',
             'along': along, 'floor': it.floor, 'z': z}
        if wall in ('front', 'back'):
            d['x'] = along - w_ / 2
            d['y'] = 0 if wall == 'front' else L
        else:
            d['y'] = along - w_ / 2
            d['x'] = 0 if wall == 'left' else W
        if is_door:
            d['door_item'] = True
        else:
            d['window_type'] = it.item_type
        out.append(d)
    return out


def compute(op, props):
    """LA liste des ouvertures des murs porteurs de la maison
    principale. Géométrie STRICTEMENT identique au producteur briques
    historique (prouvé au banc), enrichie de `along` et `floor`.
    ✅ Si le TABLEAU D'OUVERTURES est actif, il REMPLACE portes et
    fenêtres automatiques (les passages d'ailes restent gérés)."""
    width = props.house_width
    length = props.house_length

    if getattr(props, 'use_openings_table', False) \
            and len(getattr(props, 'openings_table', [])):
        openings = table_spec(op, props)
        for wing in getattr(op, '_wings', []):
            from . import volumes
            openings = [o for o in openings
                        if o['type'] != 'window'
                        or not volumes.opening_in_span(o, wing)]
            p = volumes.passage_opening(wing, props,
                                        op._get_wall_depth(props),
                                        op._plinth_visible(props))
            p.setdefault('floor', 0)
            p.setdefault('along', p['x'] + p['width'] / 2
                         if p.get('wall') in ('front', 'back')
                         else p['y'] + p['width'] / 2)
            openings.append(p)
        return openings

    openings = []

    wall_depth = op._get_wall_depth(props)
    style_config = op._apply_architectural_style(props)
    layout = op._get_window_layout(props, style_config)
    window_height_ratio = layout['height_ratio']
    num_windows_front = layout['num_front']
    num_windows_side = layout['num_side']

    if getattr(op, 'real_wall_height', None):
        floor_height_actual = op.real_wall_height / props.num_floors
    else:
        floor_height_actual = props.floor_height

    # PORTE — démarre au seuil (soubassement visible), posée dessus
    door_width = props.front_door_width
    door_height = None
    from .norms import PORTE_ENTREE_H
    door_height = PORTE_ENTREE_H
    door_center = op._door_center_x(props)
    openings.append({
        'x': door_center - door_width / 2, 'y': 0,
        'z': op._plinth_visible(props),
        'width': door_width, 'height': door_height, 'depth': wall_depth,
        'wall': 'front', 'type': 'door',
        'along': door_center, 'floor': 0,
    })

    # FENÊTRES
    for floor in range(props.num_floors):
        floor_z = floor * floor_height_actual
        window_height, window_z, _ = op._window_vertical(
            floor_z, floor_height_actual, window_height_ratio)
        window_width = layout['width']

        def _win(wall, along):
            if wall in ('front', 'back'):
                x, y = along - window_width / 2, (0 if wall == 'front'
                                                  else length)
            else:
                x, y = (0 if wall == 'left' else width), \
                    along - window_width / 2
            return {'x': x, 'y': y, 'z': window_z,
                    'width': window_width, 'height': window_height,
                    'depth': wall_depth, 'wall': wall, 'type': 'window',
                    'along': along, 'floor': floor}

        spacing_front = width / (num_windows_front + 1)
        for i in range(num_windows_front):
            x_pos = spacing_front * (i + 1)
            if floor == 0 and abs(x_pos - door_center) < door_width * 1.5:
                continue
            openings.append(_win('front', x_pos))

        for x_pos in _back_positions(op, props, width, layout['num_back']):
            openings.append(_win('back', x_pos))

        spacing_side = length / (num_windows_side + 1)
        for i in range(num_windows_side):
            openings.append(_win('left', spacing_side * (i + 1)))
        for i in range(num_windows_side):
            openings.append(_win('right', spacing_side * (i + 1)))

    # PORTE-FENÊTRE derrière le balcon (étage 1, façade avant) — le
    # seuil d'exclusion est LE MÊME pour le trou et la menuiserie (les
    # deux formules divergeaient avant S4)
    if getattr(props, 'include_balcony', False) and props.num_floors > 1:
        pf_w = min(1.5, max(1.1, getattr(props, 'balcony_width', 2.6) - 0.6))
        pf_z = floor_height_actual + 0.02
        openings = [o for o in openings
                    if not (o['type'] == 'window' and o['wall'] == 'front'
                            and o['z'] > floor_height_actual * 0.9
                            and abs(o['along'] - width / 2)
                            < pf_w / 2 + o['width'] / 2 + 0.3)]
        openings.append({'x': width / 2 - pf_w / 2, 'y': 0, 'z': pf_z,
                         'width': pf_w, 'height': 2.05,
                         'depth': wall_depth, 'wall': 'front',
                         'type': 'door', 'along': width / 2, 'floor': 1})

    # MULTI-VOLUMES: fenêtres masquées par les ailes supprimées +
    # ouverture de PASSAGE dans chaque mur mitoyen
    for wing in getattr(op, '_wings', []):
        from . import volumes
        before = len(openings)
        openings = [o for o in openings
                    if o['type'] != 'window'
                    or not volumes.opening_in_span(o, wing)]
        removed = before - len(openings)
        if removed:
            print(f"[House] Aile {wing['side']}: {removed} fenêtre(s) "
                  f"masquée(s) supprimée(s)")
        p = volumes.passage_opening(wing, props, wall_depth,
                                    op._plinth_visible(props))
        p.setdefault('type', 'passage')
        p.setdefault('floor', 0)
        p.setdefault('along', p['x'] + p['width'] / 2
                     if p.get('wall') in ('front', 'back')
                     else p['y'] + p['width'] / 2)
        openings.append(p)

    return openings


def windows_of(openings, wall=None, floor=None):
    """Filtre pratique pour les consommateurs."""
    out = [o for o in openings if o['type'] == 'window']
    if wall is not None:
        out = [o for o in out if o['wall'] == wall]
    if floor is not None:
        out = [o for o in out if o['floor'] == floor]
    return out
