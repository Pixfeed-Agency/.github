# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Tableau de pièces (chantier ⑤ du brief)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""TABLEAU DE PIÈCES — le plan par les SURFACES, comme dans un brief.

Un brief réel ne dit pas "3 cellules": il dit "chambre 1: 12 m²,
chambre 2: 11 m², SdB: 6 m², WC: 2,5 m²". Le tableau de pièces prend
ces lignes (nom, type, surface cible) et:
- dimensionne la PROFONDEUR de la bande arrière pour que la somme des
  surfaces y tienne (le refend recule ou avance),
- découpe la bande en cellules de LARGEURS proportionnelles aux
  surfaces demandées,
- transmet les RÔLES (chambre/SdB/WC) à l'aménagement (sanitaires,
  mobilier, électricité) et une fenêtre par pièce à la façade (S4).

Prime sur le mode PROGRAMME (comme le tableau d'ouvertures prime sur
les fenêtres automatiques). Le séjour/cuisine reste la bande avant.
"""

ROLES = {
    'CHAMBRE': 'chambre',
    'BUREAU': 'chambre',      # même aménagement de base
    'SDB': 'sdb',
    'WC': 'wc',
}


def spec(props):
    """[{name, role, surface}] du tableau utilisateur, ou None si le
    tableau est inactif ou trop court (< 2 pièces)."""
    if not getattr(props, 'use_rooms_table', False):
        return None
    rows = []
    for r in getattr(props, 'rooms_table', []):
        rows.append({
            'name': (r.name.strip() or r.room_type.title()),
            'role': ROLES.get(r.room_type, 'chambre'),
            'surface': max(1.0, float(r.surface)),
        })
    return rows if len(rows) >= 2 else None


def band_depth(rows, inner_width):
    """Profondeur de bande arrière qui loge la somme des surfaces."""
    total = sum(r['surface'] for r in rows)
    return total / max(0.5, inner_width)
