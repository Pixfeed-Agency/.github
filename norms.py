# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Normes et dimensions du bâtiment (chantier S8)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""NORMES ET DIMENSIONS DU BÂTIMENT — la source unique.

Chaque constante est une dimension du MONDE RÉEL, nommée et sourcée
(DTU, normes NF/EN, ou usage constaté sur le bâti français). Les
builders importent d'ici au lieu de semer des nombres magiques.

Chantier S8: les valeurs sont EXACTEMENT celles qui étaient éparpillées
dans le code (prouvé au pixel près par le banc visuel) — seule la
NOMINATION change. Toute évolution future d'une valeur se fait ICI,
avec sa justification, et se propage partout.

Unités: mètres, sauf mention contraire.
"""

# ============================================================
# GROS ŒUVRE
# ============================================================

MUR_EP_BASE = 0.25          # mur porteur enduit (parpaing 20 + enduits)
DALLE_EP = 0.20             # dalle béton courante (plancher 16+4 chape)
FONDATION_EP = 0.30         # semelle/soubassement hors sol
TOIT_DALLE_TERRASSE_EP = 0.30   # complexe toiture-terrasse (FLAT)
TOIT_DALLE_RAMPANT_EP = 0.15    # volige + chevronnage simplifié (pans)

# ============================================================
# ESCALIER — NF P01-012 / loi de Blondel (2h + g = 0.60-0.64 m)
# ============================================================

ESCALIER_GIRON = 0.25           # giron confortable en habitation
ESCALIER_GIRON_QT = 0.24        # giron réduit du quart-tournant
ESCALIER_HAUTEUR_MAX = 0.185    # hauteur de marche visée (17-18.5cm)
ESCALIER_N_MIN = 12             # nb de marches mini (étage courant 2.7m)
ESCALIER_PALIER = 1.0           # profondeur du palier d'angle

# ============================================================
# CLOISONS ET CIRCULATIONS INTÉRIEURES
# ============================================================

CLOISON_EP = 0.08               # cloison placo 72/48 finie
PASSAGE_PORTE_L = 0.93          # passage libre standard français
PASSAGE_PORTE_H = 2.04          # hauteur de passage standard
PLAFOND_EP = 0.06               # plaque + ossature simplifiée
PASSAGE_AILE_H = 2.05           # passage maison → aile

# ============================================================
# MENUISERIES — standards EN / usage français
# ============================================================

FENETRE_DORMANT_PROF = 0.07     # profondeur du dormant (70mm)
FENETRE_VITRAGE_EP = 0.02       # double vitrage simplifié (4/12/4)
FENETRE_VERRE_RETRAIT = 0.005   # retrait du verre dans l'ouvrant
FENETRE_APPUI_INT = 0.04        # appui intégré au dormant (40mm)
PORTE_ENTREE_H = 2.10           # porte d'entrée standard
PORTE_DORMANT_PROF = 0.10       # dormant de porte
PORTE_EP = 0.04                 # épaisseur d'un vantail
PORTE_CADRE_L = 0.06            # largeur du cadre
PORTE_POIGNEE_H = 1.05          # axe de poignée (norme PMR ~0.9-1.3)
LINTEAU_H = 2.15                # linteau standard: les HAUTS de fenêtres
                                # s'alignent dessus (comme la porte) —
                                # une façade réelle aligne ses linteaux

# Appui de fenêtre BÉTON débordant (niveau PHOTO — DTU 20.1: débord
# 3-5cm avec pente de rejet et oreilles)
APPUI_DEBORD = 0.05             # nez devant le nu extérieur
APPUI_PENTE = 0.014             # pente de rejet d'eau sur la largeur
APPUI_NEZ_EP = 0.05             # épaisseur du nez
APPUI_OREILLES = 0.04           # dépassement latéral de chaque côté
APPUI_ANCRAGE = 0.02            # ancrage sous le dormant

# ============================================================
# COUVERTURE — tuiles (DTU 40.21/40.22: recouvrement selon pente)
# ============================================================

TUILE_LARGEUR = 0.30            # largeur utile (le long du faîtage)
TUILE_LONGUEUR = 0.36           # longueur (le long de la pente)
TUILE_EP = 0.022                # épaisseur apparente
TUILE_RECOUVREMENT = 0.09       # recouvrement → pureau 27cm
TUILE_NEZ_H = 0.014             # relèvement du nez → INCLINAISON DE
                                # POSE physique: atan2(NEZ, pureau)
DOUBLIS_DECALAGE = 0.45         # rang de doublis: fraction de pureau
DOUBLIS_SURELEVATION = 0.004    # surélévation du doublis (cale)
FAITIERE_RAYON = 0.11           # faîtière demi-ronde ∅22
FAITIERE_RAYON_AILE = 0.11      # idem sur les ailes
TUILE_RIVE_RAYON = 0.07         # rive ronde de pignon
VELUX_L = 0.78                  # fenêtre de toit standard 78×118
VELUX_H = 1.18

# ============================================================
# CHARPENTE APPARENTE ET RIVES
# ============================================================

FASCIA_H = 0.18                 # bandeau d'égout (planche de rive)
FASCIA_EP = 0.022
RIVE_PLANCHE_H = 0.28           # planche de rive de pignon
RIVE_PLANCHE_EP = 0.025

# ============================================================
# ZINGUERIE — évacuation des eaux pluviales
# ============================================================

GOUTTIERE_RAYON = 0.07          # gouttière demi-ronde ~∅ 25/33
DESCENTE_RAYON = 0.04           # descente EP ∅ 80
ZINC_NOUE_LARGEUR = 0.24        # bande de noue façonnée


# ============================================================
# ✅ S6 — GRAINES DÉRIVÉES: chaque élément aléatoire (tuiles,
# lucarnes, herbe, aile) dérive sa graine de random_seed + son nom.
# Hash FNV-1a (stable entre sessions, contrairement à hash() Python)
# → une maison reste parfaitement reproductible, mais deux maisons de
# graines différentes ne sont plus JUMELLES (mêmes patines, mêmes
# jitters — le tell des rendus côte à côte).
# ============================================================

def derive_seed(props, label):
    """Graine déterministe pour l'élément `label` de cette maison."""
    try:
        base = int(getattr(props, 'random_seed', 0) or 0)
    except (TypeError, ValueError):
        base = 0
    h = 2166136261
    for c in label:
        h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return (base * 1000003 + h) & 0x7FFFFFFF
