# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Modèle de niveaux (chantier S3)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""MODÈLE DE NIVEAUX — les altitudes de référence, en UN seul endroit.

z = 0 est le TERRAIN FINI. Toutes les altitudes du bâtiment dérivent
des règles de ce module — plus de vérités parallèles recalculées dans
chaque builder (l'historique des bugs verticaux vient de là: fenêtre
décalée d'une demi-hauteur, escalier qui rate l'étage de 8cm, tuiles
noyées dans la dalle).

Deux usages:
- fonctions pures (`plinth_visible`, `window_vertical`) — les formules
  canoniques, appelables sans état;
- l'objet `Levels` construit par le pipeline après les murs (la hauteur
  réelle dépend du calepinage des briques) et exposé aux étapes comme
  `op.levels`.

Chantier S3: les formules sont EXACTEMENT celles qui vivaient dans
operators_auto (pixel-prouvé par le banc) — seule la RÉSIDENCE change.
"""

from . import norms

# Allège par défaut: fraction de l'étage sous la fenêtre (historique)
ALLEGE_RATIO_MAX = 0.4


def plinth_visible(props):
    """Hauteur VISIBLE du soubassement au-dessus du terrain.

    Source UNIQUE partagée entre fondations, seuil et porte d'entrée
    (la porte doit POSER sur le socle, pas être enterrée derrière).
    """
    if props.foundation_height <= 0:
        return 0.0
    return min(0.2, props.foundation_height * 0.4)


def window_vertical(floor_z, floor_height, height_ratio):
    """Géométrie verticale UNIQUE d'une fenêtre:
    (hauteur, z bas = allège, z centre).

    Partagée par les ouvertures (briques = bas du trou, murs simples =
    centre) et par les menuiseries visibles — le jeu d'une demi-hauteur
    entre le trou et la fenêtre venait de conventions divergentes.
    La fenêtre est clampée pour ne pas dépasser le plafond de l'étage.
    """
    window_height = floor_height * height_ratio
    sill_ratio = min(ALLEGE_RATIO_MAX, max(0.05, 1.0 - height_ratio - 0.05))
    z_bottom = floor_z + floor_height * sill_ratio
    return window_height, z_bottom, z_bottom + window_height / 2


class Levels:
    """Altitudes de référence d'UN bâtiment (maison principale).

    Construit par l'étape `walls` du pipeline (la hauteur d'arase
    réelle dépend du mode de construction) et restauré en régénération
    incrémentale comme le reste de l'état inter-étapes.
    """

    def __init__(self, props, real_wall_height=None):
        self.plinth = plinth_visible(props)          # seuil / socle
        self.slab_t = norms.DALLE_EP                 # épaisseur de dalle
        self.floor_h = props.floor_height            # étage nominal
        self.n_floors = props.num_floors
        # Arase réelle des murs (calepinage briques) ou nominale
        self.wall_top = real_wall_height if real_wall_height is not None \
            else props.num_floors * props.floor_height
        # Étage RÉEL: l'arase se répartit sur les étages
        self.floor_h_real = self.wall_top / max(1, self.n_floors)

    def floor_z(self, floor=0):
        """z du sol BRUT de l'étage `floor` (0 = rez-de-chaussée)."""
        return floor * self.floor_h_real

    def slab_top(self, floor=0):
        """z du DESSUS de la dalle de l'étage (sol avant finition)."""
        return self.floor_z(floor) + self.slab_t if floor == 0 \
            else self.floor_z(floor)

    def window(self, floor, height_ratio):
        """(hauteur, z bas, z centre) de la fenêtre de l'étage."""
        return window_vertical(self.floor_z(floor), self.floor_h_real,
                               height_ratio)

    def eave_z(self):
        """z de l'égout (arase des murs — la charpente part d'ici)."""
        return self.wall_top

    def ridge_z(self, pitch_deg, half_span):
        """z du faîtage pour une pente et une demi-portée données."""
        import math
        return self.wall_top + half_span * math.tan(math.radians(pitch_deg))
