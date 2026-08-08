# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Mode PROGRAMME (chantier qualité n°6)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""MODE PROGRAMME — "3 chambres, SdB, garage" → House résout.

L'utilisateur décrit un PROGRAMME FONCTIONNEL (combien de chambres, de
salles de bain, WC séparé ou non, garage) et le solveur le traduit en
paramètres du générateur: emprise, distribution, fenêtres, options.

Le solveur est du Python PUR (aucun import bpy) — testable sans Blender.

Périmètre v1: le PLAIN-PIED (pavillon/longère — la typologie de la photo
de référence). La bande arrière (derrière le refend transversal) est
découpée en CELLULES pleine profondeur: chambres, salle(s) de bain, WC.
Les largeurs résolues sont transmises à interiors.interior_layout via
la propriété `programme_cells`.

Surfaces normatives de l'habitat français (repères usuels):
- chambre: ~11 m² (mini légal conseillé 9 m²)
- séjour + cuisine ouverte: 30 m² + 4 m² par chambre
- salle de bain: ~5 m²  /  WC séparé: ~1.4 m²
Comme les cellules sont PLEINE PROFONDEUR (pas de couloir en v1), les
surfaces réelles générées dépassent le programme théorique — le rapport
donne les DEUX chiffres, sans maquiller.
"""

import math

# Surfaces cibles (m²)
S_CHAMBRE = 11.0
S_SDB = 5.0
S_WC = 1.4
S_SEJOUR_BASE = 30.0
S_SEJOUR_PAR_CHAMBRE = 4.0

# Bornes constructives
DEPTH_MIN, DEPTH_MAX = 6.8, 8.4    # profondeur: portée de toit saine
WIDTH_MIN, WIDTH_MAX = 8.0, 18.0   # façade
W_CHAMBRE_MIN, W_CHAMBRE_MAX = 2.8, 4.2
W_SDB_MIN, W_SDB_MAX = 1.8, 2.6
W_WC = 1.05
WALL_T = 0.3                       # épaisseur nominale (murs SIMPLE)
REFEND_RATIO = 0.55                # y_refend = 0.55 × profondeur

GARAGE_DIMS = {'SINGLE': (3.6, 5.6), 'DOUBLE': (6.0, 5.6)}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def solve(bedrooms, bathrooms=1, wc_separate=True, garage='NONE',
          surface=0.0):
    """Résout le programme.

    Returns dict:
      props   — valeurs à poser sur les propriétés House
      cells   — largeurs des cellules de la bande arrière (m), de
                gauche à droite: chambres…, SdB…, WC
      rooms   — [(nom, surface réelle m²)] pour le rapport
      report  — lignes de rapport lisibles
      summary — une ligne pour la barre d'info
    """
    bedrooms = int(_clamp(int(bedrooms), 1, 4))
    bathrooms = int(_clamp(int(bathrooms), 1, 2))
    if garage not in ('NONE', 'SINGLE', 'DOUBLE'):
        garage = 'NONE'

    s_theorique = (S_SEJOUR_BASE + S_SEJOUR_PAR_CHAMBRE * bedrooms
                   + S_CHAMBRE * bedrooms + S_SDB * bathrooms
                   + (S_WC if wc_separate else 0.0)) * 1.10

    # Scan de la profondeur: pour chaque L la bande arrière impose la
    # largeur (cellules pleine profondeur); on retient le L qui
    # approche le mieux la surface cible (ou la minimise si auto).
    t = WALL_T
    best = None
    target = surface if surface and surface > 0 else None
    L = DEPTH_MIN
    while L <= DEPTH_MAX + 1e-9:
        y_ref = REFEND_RATIO * L
        band = L - y_ref - t             # profondeur des cellules
        front = y_ref - t                # profondeur du séjour
        w_ch = _clamp(S_CHAMBRE / band, W_CHAMBRE_MIN, W_CHAMBRE_MAX)
        w_sdb = _clamp(S_SDB / band, W_SDB_MIN, W_SDB_MAX)
        cells = [w_ch] * bedrooms + [w_sdb] * bathrooms
        if wc_separate:
            cells.append(W_WC)
        inner = sum(cells)
        width = inner + 2 * t
        if width < WIDTH_MIN:
            # Petit programme: on élargit les pièces jusqu'à la façade
            # minimale (une petite maison a des pièces plus généreuses,
            # pas une façade de cabane)
            factor = (WIDTH_MIN - 2 * t) / inner
            cells = [c * factor for c in cells]
            inner = sum(cells)
            width = WIDTH_MIN
        if width > WIDTH_MAX:
            L += 0.05
            continue
        total = width * L
        score = abs(total - target) if target else total
        if best is None or score < best['score'] - 1e-9:
            best = dict(score=score, L=L, width=width, cells=cells,
                        band=band, front=front, inner=inner, total=total)
        L += 0.05
    if best is None:
        raise ValueError(
            f"Programme insoluble en plain-pied: {bedrooms} chambre(s) "
            f"ne tiennent pas dans une façade de {WIDTH_MAX}m")

    width = round(best['width'], 2)
    depth = round(best['L'], 2)
    cells = [round(c, 3) for c in best['cells']]

    rooms = [("Séjour + cuisine", best['inner'] * best['front'])]
    labels = ([f"Chambre {i + 1}" for i in range(bedrooms)]
              + ([f"Salle de bain {i + 1}" for i in range(bathrooms)]
                 if bathrooms > 1 else ["Salle de bain"])
              + (["WC"] if wc_separate else []))
    rooms += [(lbl, c * best['band']) for lbl, c in zip(labels, cells)]

    props = dict(
        house_width=width,
        house_length=depth,
        num_floors=1,
        num_bedrooms=bedrooms,
        include_interiors=True,
        roof_type='GABLE',
        roof_pitch=40.0,
        roof_covering='TILES',
        include_gutters=True,
        include_chimney=True,
        include_shutters=True,
        window_type='CASEMENT',
        door_type='SINGLE',
        use_materials=True,
        # une fenêtre par grande cellule arrière; façade avant = séjour
        num_windows_back=bedrooms + bathrooms,
        num_windows_front=max(2, bedrooms),
        num_windows_side=1,
    )
    if garage != 'NONE':
        gw, gd = GARAGE_DIMS[garage]
        props.update(include_garage=True, garage_position='RIGHT',
                     garage_width=gw, garage_depth=gd)
    else:
        props.update(include_garage=False)

    report = [
        f"Emprise résolue: {width:.1f} × {depth:.1f} m "
        f"({best['total']:.0f} m² au sol, programme théorique "
        f"{s_theorique:.0f} m²)",
        f"Refend à {REFEND_RATIO * depth:.2f} m — séjour devant, "
        f"{len(cells)} cellule(s) derrière",
    ]
    report += [f"  {lbl}: {s:.1f} m²" for lbl, s in rooms]
    if garage != 'NONE':
        report.append(f"  Garage {garage.lower()}: "
                      f"{GARAGE_DIMS[garage][0]:.1f} × "
                      f"{GARAGE_DIMS[garage][1]:.1f} m (aile droite)")

    summary = (f"Programme: {bedrooms} ch + {bathrooms} SdB"
               + (" + WC" if wc_separate else "")
               + (f" + garage {garage.lower()}" if garage != 'NONE' else "")
               + f" → {width:.1f}×{depth:.1f} m ({best['total']:.0f} m²)")

    return dict(props=props, cells=cells, rooms=rooms,
                report=report, summary=summary)
