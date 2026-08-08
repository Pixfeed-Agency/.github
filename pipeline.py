# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Pipeline de construction déclaratif (chantier qualité n°3)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""PIPELINE DE CONSTRUCTION — l'ordre et les dépendances, EXPLICITES.

Avant ce module, `execute()` était un monolithe de ~150 lignes dont
l'ordre implicite a causé trois familles de bugs réels:
- `_apply_materials` écrasait des matériaux posés par des étapes
  antérieures (l'ordre matériaux/charpente n'était garanti nulle part);
- l'initialisation des ailes devait précéder murs ET ouvertures, ce
  qui n'était écrit nulle part;
- `real_wall_height` périmé entre deux exécutions (état implicite).

Ici chaque étape déclare:
- `requires`: les attributs d'état qu'elle CONSOMME (sur l'opérateur),
- `provides`: ceux qu'elle GARANTIT après exécution,
- `cond(props)`: sa condition d'activation,
- `tags`: son domaine (walls/roof/interior/env…) — base de la future
  régénération incrémentale (invalider un tag → rejouer ses étapes).

Deux validations:
1. STATIQUE (à l'import): toute dépendance doit être fournie par une
   étape antérieure ou faire partie des GRAINES (`SEEDS`). Un mauvais
   ordre casse l'import — plus de bug d'ordre silencieux.
2. À L'EXÉCUTION: presence des `requires` avant l'étape, des
   `provides` après — une étape qui ne tient pas son contrat est
   nommée dans l'erreur.

`HOUSE_PIPELINE_PROFILE=1` imprime le chrono par étape.
"""

import os
import time

# Attributs présents AVANT la première étape (posés par le driver)
SEEDS = ("props", "collection", "context")


class Step:
    __slots__ = ("name", "run", "requires", "provides", "cond", "tags")

    def __init__(self, name, run, requires=(), provides=(), cond=None,
                 tags=()):
        self.name = name
        self.run = run            # fonction (op, context, props, collection)
        self.requires = tuple(requires)
        self.provides = tuple(provides)
        self.cond = cond          # fonction (props) -> bool, ou None
        self.tags = tuple(tags)


class PipelineError(RuntimeError):
    pass


def _validate_static(steps):
    """L'ordre est un CONTRAT: chaque requires doit être couvert par les
    provides d'une étape antérieure (ou par les graines)."""
    available = set(SEEDS)
    for s in steps:
        missing = [r for r in s.requires if r not in available]
        if missing:
            raise PipelineError(
                f"Pipeline invalide: l'étape '{s.name}' requiert "
                f"{missing} mais aucune étape antérieure ne le fournit. "
                f"Ordre actuel: {[x.name for x in steps]}")
        available.update(s.provides)
    return True


def run_pipeline(steps, op, context, props, collection):
    """Exécute les étapes dans l'ordre, contrats vérifiés, chrono."""
    profile = os.environ.get("HOUSE_PIPELINE_PROFILE") == "1"
    timings = []
    for s in steps:
        if s.cond is not None and not s.cond(props):
            continue
        for r in s.requires:
            if r in SEEDS:
                continue
            if not hasattr(op, r):
                raise PipelineError(
                    f"Étape '{s.name}': dépendance '{r}' absente à "
                    f"l'exécution (contrat rompu en amont)")
        t0 = time.perf_counter()
        s.run(op, context, props, collection)
        dt = time.perf_counter() - t0
        timings.append((s.name, dt))
        for pv in s.provides:
            if not hasattr(op, pv):
                raise PipelineError(
                    f"Étape '{s.name}' n'a pas fourni '{pv}' "
                    f"comme son contrat le déclare")
        if profile:
            print(f"[Pipeline] {s.name:20s} {dt*1000:8.1f} ms")
    if profile:
        total = sum(t for _n, t in timings)
        print(f"[Pipeline] {'TOTAL':20s} {total*1000:8.1f} ms "
              f"({len(timings)} étapes)")
    return timings


# ============================================================
# LES ÉTAPES DE CONSTRUCTION D'UNE MAISON
# (les corps restent dans operators_auto — ici: ordre + contrats)
# ============================================================

def _st_seed(op, context, props, collection):
    import random
    if props.random_seed > 0:
        random.seed(props.random_seed)
    # remise à zéro de l'état par exécution (le panneau Redo réutilise
    # l'instance d'opérateur!)
    op.real_wall_height = None
    op._interior_layout = None
    op.style_config = op._apply_architectural_style(props)


def _st_wings(op, context, props, collection):
    from . import volumes
    op._wings = []
    op._garage_as_wing = False
    if not (getattr(props, 'include_wing', False)
            or getattr(props, 'include_garage', False)):
        return
    layout = op._get_window_layout(props, op.style_config)
    for frame in op._get_wing_frames(props):
        if frame.get('garage'):
            ops_l, fl, opening = volumes.garage_openings_local(
                frame, props, op._get_wall_depth(props))
            frame['openings'], frame['specs'] = ops_l, []
            frame['garage_opening'] = opening
            frame['garage_front_local'] = fl
        else:
            wvs = [op._window_vertical(i * frame['fh'], frame['fh'],
                                       layout['height_ratio'])
                   for i in range(frame['floors'])]
            frame['openings'], frame['specs'] = volumes.wing_openings_local(
                frame, props, layout, wvs, op._get_wall_depth(props))
        op._wings.append(frame)
        print(f"[House] Aile {frame['w']:.1f}×{frame['d']:.1f}m "
              f"×{frame['floors']} étage(s) côté {frame['side']} "
              f"({'noues 45°' if frame['valley'] else 'appentis-pignon'})")


def _st_foundation(op, context, props, collection):
    op._generate_foundation(context, props, collection)


def _st_walls(op, context, props, collection):
    op.walls = op._generate_walls(context, props, collection)


def _st_floors(op, context, props, collection):
    op._generate_floors(context, props, collection)


def _st_interiors(op, context, props, collection):
    op._generate_interiors(context, props, collection, op.style_config)


def _st_roof(op, context, props, collection):
    op._generate_roof(context, props, collection)


def _st_openings(op, context, props, collection):
    op._generate_wall_openings(context, props, collection, op.walls,
                               op.style_config)


def _st_windows(op, context, props, collection):
    op._generate_windows_complete(context, props, collection,
                                  op.style_config)


def _st_door(op, context, props, collection):
    op._generate_door_visual(context, props, collection)


def _st_tiles(op, context, props, collection):
    op._generate_roof_tiles(context, props, collection)


def _st_roof_details(op, context, props, collection):
    op._generate_roof_details(context, props, collection)


def _st_wings_build(op, context, props, collection):
    for wing in op._wings:
        print(f"[House] Aile côté {wing['side']}...")
        op._generate_wing(context, props, collection, wing)


def _st_gutters(op, context, props, collection):
    op._generate_gutters(context, props, collection)


def _st_chimney(op, context, props, collection):
    op._generate_chimney(context, props, collection)


def _st_garage_legacy(op, context, props, collection):
    if not op._garage_as_wing:
        print("[House] Garage (volume simple hérité)...")
        op._generate_garage(context, props, collection)


def _st_terrace(op, context, props, collection):
    op._generate_terrace(context, props, collection)


def _st_balcony(op, context, props, collection):
    op._generate_balcony(context, props, collection)


def _st_materials(op, context, props, collection):
    # DOIT rester après charpente/tuiles/aile: ne repeint QUE les
    # objets sans matériau (contrat consolidé en v1.4)
    op._apply_materials(context, props, collection, op.style_config)


def _st_lighting(op, context, props, collection):
    op._add_scene_lighting(context, props)


def _st_environment(op, context, props, collection):
    from . import features
    garage_front = None
    for wg in op._wings:
        if wg.get('garage') and wg.get('garage_opening') is not None:
            fp = wg['footprint']
            garage_front = (fp[0] + 0.4, fp[2] - 0.4)
    features.build_environment(props, collection,
                               garage_front=garage_front,
                               door_x=op._door_center_x(props))


HOUSE_STEPS = [
    Step("seed_style", _st_seed,
         provides=("real_wall_height", "_interior_layout", "style_config"),
         tags=("all",)),
    Step("wings_init", _st_wings,
         requires=("style_config",),
         provides=("_wings", "_garage_as_wing"),
         tags=("wings",)),
    Step("foundation", _st_foundation,
         requires=("_wings",),
         cond=lambda p: p.foundation_height > 0,
         tags=("structure",)),
    Step("walls", _st_walls,
         requires=("_wings", "style_config"),
         provides=("walls", "real_wall_height"),
         tags=("walls",)),
    Step("floors", _st_floors,
         requires=("real_wall_height", "_wings"),
         tags=("structure",)),
    Step("interiors", _st_interiors,
         requires=("real_wall_height", "_wings", "style_config"),
         cond=lambda p: getattr(p, 'include_interiors', True),
         tags=("interior",)),
    Step("roof", _st_roof,
         requires=("real_wall_height",),
         tags=("roof",)),
    Step("wall_openings", _st_openings,
         requires=("walls", "style_config", "_wings"),
         cond=lambda p: p.wall_construction_type != 'BRICK_3D',
         tags=("walls",)),
    Step("windows", _st_windows,
         requires=("real_wall_height", "style_config", "_wings"),
         tags=("joinery",)),
    Step("door", _st_door,
         requires=("_wings",),
         tags=("joinery",)),
    Step("roof_tiles", _st_tiles,
         requires=("real_wall_height",),
         cond=lambda p: p.roof_covering == 'TILES',
         tags=("roof",)),
    Step("roof_details", _st_roof_details,
         requires=("real_wall_height", "_wings"),
         tags=("roof",)),
    Step("wings_build", _st_wings_build,
         requires=("_wings", "real_wall_height"),
         tags=("wings",)),
    Step("gutters", _st_gutters,
         requires=("real_wall_height", "_wings"),
         cond=lambda p: p.include_gutters,
         tags=("roof",)),
    Step("chimney", _st_chimney,
         requires=("real_wall_height",),
         cond=lambda p: p.include_chimney,
         tags=("roof",)),
    Step("garage_legacy", _st_garage_legacy,
         requires=("_garage_as_wing",),
         cond=lambda p: p.include_garage,
         tags=("wings",)),
    Step("terrace", _st_terrace,
         cond=lambda p: p.include_terrace,
         tags=("structure",)),
    Step("balcony", _st_balcony,
         requires=("real_wall_height",),
         cond=lambda p: p.include_balcony and p.num_floors > 1,
         tags=("joinery",)),
    Step("materials", _st_materials,
         requires=("style_config",),
         cond=lambda p: p.use_materials,
         tags=("materials",)),
    Step("lighting", _st_lighting,
         cond=lambda p: p.auto_lighting,
         tags=("env",)),
    Step("environment", _st_environment,
         requires=("_wings",),
         cond=lambda p: getattr(p, 'include_environment', False),
         tags=("env",)),
]

# ✅ Validation STATIQUE à l'import: un mauvais ordre casse le chargement
_validate_static(HOUSE_STEPS)
