# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Banc de non-régression visuel
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""BANC DE NON-RÉGRESSION VISUEL — House Generator

Usage (depuis la racine du repo, avec bpy installé):
    python3 tests/visual/bench.py              # compare aux références
    python3 tests/visual/bench.py --update     # (re)crée les références
    python3 tests/visual/bench.py --only hip   # sous-ensemble par nom
    python3 tests/visual/bench.py --fast       # noyau de 8 configs

Principe (bonnes pratiques golden-image pour add-on Blender):
- ~25 configurations couvrant CHAQUE chemin de code qui produit des
  pixels (5 toits, 2 moteurs briques, 3 modes matériaux, ailes L/T/U +
  croupe/mansarde, garage briques/enduit, lucarnes/velux, escaliers,
  intérieurs, environnement, presets).
- Rendus DÉTERMINISTES: Cycles CPU, seed fixe, 24 samples + denoise
  OIDN, 480×300 — toute la randomisation procédurale du code est déjà
  seedée (tuiles 42, aile 4242, lucarnes 777, herbe 7/51, arbres 23).
- Comparaison à SEUILS CALIBRÉS (double-run): MAE sur RGB et % de
  pixels dont un canal bouge de plus de 10/255. Un léger bruit Cycles
  passe; un matériau débranché ou un mur avalé ne passe PAS.
- RAPPORT HTML: référence | actuel | diff amplifiée, échecs en tête.
- Chaque config vérifie aussi des INVARIANTS: opérateur FINISHED et
  présence des objets clés (ex: Roof_Tiles, Wing_Walls) — le bug du
  Boolean qui avalait la façade du garage aurait été attrapé ici.

Exit code: 0 = tout passe, 1 = au moins un échec (CI-compatible).
"""

import os
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BASELINE = os.path.join(HERE, "baseline")
CURRENT = os.path.join(HERE, "current")
REPORT = os.path.join(HERE, "report")

# Seuils calibrés par double-run (bruit Cycles résiduel: MAE ~0.3,
# pixels changés ~0.2% — marge ×5 pour rester silencieux sur le bruit
# et bruyant sur les vraies régressions)
THRESH_MAE = 2.0
THRESH_PCT = 1.5   # % de pixels avec delta canal > 10/255

RES_X, RES_Y = 480, 300
SAMPLES = 24


# ============================================================
# CONFIGURATIONS DE RÉFÉRENCE
# Chaque entrée: props (dict), cam (loc, target, lens),
# expect (objets requis), light/exposure optionnels, fast (noyau).
# ============================================================

def _cfg(name, props, cam, expect=(), light=None, exposure=None, fast=False):
    return dict(name=name, props=props, cam=cam, expect=list(expect),
                light=light, exposure=exposure, fast=fast)


BASE = dict(house_width=9.0, house_length=7.0, num_floors=1,
            floor_height=2.7, roof_type='GABLE', roof_pitch=32.0,
            roof_overhang=0.45, roof_covering='TILES',
            wall_construction_type='BRICK_3D', brick_use_geonodes=True,
            include_gutters=True, include_shutters=True,
            window_type='CASEMENT', door_type='SINGLE',
            use_materials=True, auto_lighting=True, random_seed=42,
            include_interiors=True)


def configs():
    C = []
    # --- Toits (les 5 types) ---
    C.append(_cfg("roof_gable", dict(BASE, include_chimney=True),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32),
                  expect=("Roof_Tiles", "Roof_Rafters", "Gutters", "Chimney"),
                  fast=True))
    C.append(_cfg("roof_gable_ridge_y", dict(BASE, house_width=7.0,
                                             house_length=9.5),
                  ((13, -10, 6.0), (3.5, 3.5, 2.0), 32),
                  expect=("Roof_Tiles", "Roof_Bargeboard")))
    C.append(_cfg("roof_shed", dict(BASE, roof_type='SHED',
                                    include_roof_windows=True,
                                    num_roof_windows=2),
                  ((15, -10, 7.5), (4, 3, 2.5), 32),
                  expect=("Roof_Tiles", "Roof_Windows_Frame"), fast=True))
    C.append(_cfg("roof_hip", dict(BASE, roof_type='HIP', roof_pitch=30.0,
                                   include_chimney=True),
                  ((13.5, -10.5, 7.5), (4.5, 3.5, 2.0), 32),
                  expect=("Roof_Tiles", "Roof_Hips", "Chimney"), fast=True))
    C.append(_cfg("roof_gambrel", dict(BASE, roof_type='GAMBREL',
                                       roof_pitch=24.0),
                  ((13, -12, 7.0), (4.5, 3.5, 2.5), 34),
                  expect=("Roof_Tiles", "Roof_Membrons"), fast=True))
    C.append(_cfg("roof_flat", dict(BASE, roof_type='FLAT',
                                    include_chimney=True),
                  ((13, -10.5, 7.0), (4.5, 3.5, 2.0), 32),
                  expect=("Roof_Coping", "Roof_Membrane", "Chimney")))
    # --- Moteurs et matériaux briques ---
    C.append(_cfg("bricks_instancing", dict(BASE, brick_use_geonodes=False),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32)))
    C.append(_cfg("bricks_color", dict(BASE, brick_material_mode='COLOR',
                                       brick_solid_color=(0.88, 0.88, 0.85, 1.0)),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32)))
    C.append(_cfg("bricks_pbr", dict(BASE, brick_material_mode='PRESET',
                                     brick_preset_type='PBR_BRIQUE_PEINTE'),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32)))
    C.append(_cfg("bricks_flemish", dict(BASE,
                                         brick_bonding_pattern='FLEMISH'),
                  ((8, -7, 2.2), (4.5, 0, 1.6), 45)))
    # --- Murs simples (enduit) + booleans ---
    C.append(_cfg("walls_stucco", dict(BASE,
                                       wall_construction_type='SIMPLE',
                                       wall_material_color=(0.55, 0.455, 0.325)),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32), fast=True))
    # --- Multi-volumes ---
    C.append(_cfg("wing_L", dict(BASE, house_width=11.0, house_length=7.5,
                                 include_wing=True, wing_side='FRONT',
                                 wing_width=5.0, wing_depth=4.5,
                                 wing_offset=0.3),
                  ((17, -13, 8.5), (5.5, 2, 1.8), 32),
                  expect=("Wing_Roof", "Wing_Valley", "Wing_Tiles"),
                  fast=True))
    C.append(_cfg("wing_U", dict(BASE, house_width=11.0, house_length=7.5,
                                 include_wing=True, wing_side='FRONT',
                                 wing_width=4.0, wing_depth=4.0,
                                 wing_offset=0.0, include_wing2=True,
                                 wing2_side='FRONT', wing2_width=4.0,
                                 wing2_depth=4.0, wing2_offset=7.0),
                  ((20, -16, 9.5), (5.5, 1.5, 1.5), 30)))
    C.append(_cfg("wing_on_hip", dict(BASE, roof_type='HIP',
                                      roof_pitch=30.0, house_width=11.0,
                                      house_length=8.0, include_wing=True,
                                      wing_side='FRONT', wing_width=4.0,
                                      wing_depth=4.0, wing_offset=3.5),
                  ((16, -13, 8.5), (5.5, 2, 1.8), 32),
                  expect=("Wing_Roof",)))
    C.append(_cfg("wing_on_gambrel", dict(BASE, roof_type='GAMBREL',
                                          roof_pitch=24.0, house_width=11.0,
                                          house_length=8.0, include_wing=True,
                                          wing_side='BACK', wing_width=4.5,
                                          wing_depth=3.5, wing_offset=3.0),
                  ((16, 19, 8.5), (5.5, 5, 2.2), 32),
                  expect=("Wing_Roof",)))
    # --- Garage-aile (briques ET enduit — le bug du Boolean vivait ici) ---
    C.append(_cfg("garage_bricks", dict(BASE, house_width=11.0,
                                        house_length=7.5,
                                        include_garage=True,
                                        garage_position='RIGHT',
                                        garage_width=5.0, garage_depth=6.0),
                  ((19, -12, 7.0), (7.5, 2, 1.8), 32),
                  # en mode briques, les murs du garage sont FUSIONNÉS
                  # dans le nuage GN — pas d'objet Wing_Walls séparé
                  expect=("Wing_Roof", "Garage_Door"), fast=True))
    C.append(_cfg("garage_stucco", dict(BASE, house_width=16.5,
                                        house_length=7.2,
                                        wall_construction_type='SIMPLE',
                                        wall_material_color=(0.55, 0.455, 0.325),
                                        roof_pitch=42.0,
                                        include_garage=True,
                                        garage_position='RIGHT',
                                        garage_width=5.0, garage_depth=6.0),
                  ((19.0, -8.0, 1.8), (19.0, 2.0, 1.8), 28),
                  expect=("Wing_Walls", "Garage_Door"), fast=True))
    # --- Fenêtres de toit ---
    C.append(_cfg("velux_gable", dict(BASE, include_roof_windows=True,
                                      roof_window_style='VELUX',
                                      num_roof_windows=2),
                  ((11.5, -10.5, 6.5), (4.5, 2, 2.4), 35),
                  expect=("Roof_Windows_Glass",)))
    C.append(_cfg("lucarnes", dict(BASE, house_width=10.0,
                                   house_length=7.5, roof_pitch=38.0,
                                   include_roof_windows=True,
                                   roof_window_style='LUCARNE',
                                   num_roof_windows=2),
                  ((13, -12.5, 6.5), (5, 2, 3.0), 34),
                  expect=("Dormer_Walls", "Dormer_Roof")))
    # --- Étages, balcon, menuiseries articulées ---
    C.append(_cfg("floors2_balcony", dict(BASE, house_width=10.0,
                                          house_length=8.0, num_floors=2,
                                          include_balcony=True,
                                          window_type='SLIDING'),
                  ((14.5, -12.5, 6.5), (4.5, 2, 2.8), 33),
                  expect=("Stair_Steps", "Stair_Rail")))
    # --- Intérieurs ---
    C.append(_cfg("interior_stairs", dict(BASE, house_width=10.0,
                                          house_length=8.0, num_floors=2,
                                          roof_covering='NONE'),
                  ((1.2, 0.8, 1.6), (8.5, 4.0, 1.8), 22),
                  expect=("Interior_Partitions", "Interior_Liners",
                          "Stair_Steps"),
                  light=((5.0, 2.2, 2.3), 500), exposure=0.0, fast=True))
    C.append(_cfg("interior_rooms", dict(BASE, house_width=12.0,
                                         house_length=8.5, num_bedrooms=3,
                                         roof_covering='NONE'),
                  ((11.0, 7.8, 1.6), (2.0, 5.5, 1.4), 22),
                  expect=("Interior_Ceilings", "Interior_Floors"),
                  light=((6.0, 6.8, 2.3), 500), exposure=0.0))
    # --- Environnement complet ---
    C.append(_cfg("environment", dict(BASE, house_width=11.0,
                                      house_length=7.5, include_wing=True,
                                      wing_side='FRONT', wing_width=5.0,
                                      wing_depth=4.5, wing_offset=0.3,
                                      include_garage=True,
                                      garage_position='RIGHT',
                                      garage_width=5.0, garage_depth=6.0,
                                      include_chimney=True,
                                      include_environment=True),
                  None,   # caméra auto de l'environnement
                  expect=("Env_Ground", "Env_Grass", "House_Camera"),
                  fast=True))
    # --- Niveaux de détail (chantier n°4) ---
    C.append(_cfg("detail_draft", dict(BASE,
                                       wall_construction_type='SIMPLE',
                                       wall_material_color=(0.55, 0.455, 0.325),
                                       detail_level='DRAFT'),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32)))
    C.append(_cfg("detail_photo", dict(BASE,
                                       wall_construction_type='SIMPLE',
                                       wall_material_color=(0.55, 0.455, 0.325),
                                       detail_level='PHOTO'),
                  ((13, -10.5, 6.5), (4, 2.5, 2.0), 32),
                  expect=("Window_Sill_Photo",)))
    # --- Preset régional (chemin apply_preset complet) ---
    C.append(_cfg("preset_bastide", dict(house_preset='BASTIDE',
                                         random_seed=42),
                  ((17, -14, 6.5), (7, 4, 2.0), 32),
                  expect=("Roof_Tiles",)))
    return C


# ============================================================
# RENDU (exécuté dans bpy)
# ============================================================

def _apply_props(p, values):
    for k, v in values.items():
        try:
            setattr(p, k, v)
        except Exception as e:
            print(f"[bench] prop {k} ignorée: {e}")


def render_all(selected, out_dir):
    import bpy
    from mathutils import Vector
    # importer le package (dossier du repo) quel que soit son nom
    sys.path.insert(0, os.path.dirname(REPO))
    import importlib
    House = importlib.import_module(os.path.basename(REPO))
    House.register()

    os.makedirs(out_dir, exist_ok=True)
    results = []
    for cfg in selected:
        name = cfg["name"]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        p = scene.house_generator
        _apply_props(p, cfg["props"])
        try:
            if cfg["props"].get("house_preset"):
                res = bpy.ops.house.apply_preset()
            else:
                res = bpy.ops.house.generate_auto()
            ok = 'FINISHED' in res
        except Exception as e:
            print(f"[bench] {name}: EXCEPTION {e}")
            ok = False
        missing = [n for n in cfg["expect"]
                   if not any(o.name.startswith(n) for o in bpy.data.objects)]
        # caméra
        if cfg["cam"] is not None:
            cam_data = bpy.data.cameras.new("BenchCam")
            cam = bpy.data.objects.new("BenchCam", cam_data)
            scene.collection.objects.link(cam)
            loc, target, lens = cfg["cam"]
            cam.location = Vector(loc)
            d = Vector(target) - cam.location
            cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
            cam_data.lens = lens
            scene.camera = cam
        if cfg["light"]:
            (lx, ly, lz), energy = cfg["light"]
            ld = bpy.data.lights.new("BenchLight", 'AREA')
            ld.energy = energy
            ld.size = 3.0
            lo = bpy.data.objects.new("BenchLight", ld)
            scene.collection.objects.link(lo)
            lo.location = Vector((lx, ly, lz))
        if cfg["exposure"] is not None:
            scene.view_settings.exposure = cfg["exposure"]
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = SAMPLES
        scene.cycles.seed = 0
        scene.cycles.use_denoising = True
        scene.render.resolution_x = RES_X
        scene.render.resolution_y = RES_Y
        scene.render.filepath = os.path.join(out_dir, name + ".png")
        try:
            bpy.ops.render.render(write_still=True)
            rendered = True
        except Exception as e:
            print(f"[bench] {name}: RENDER FAIL {e}")
            rendered = False
        results.append(dict(name=name, finished=ok, rendered=rendered,
                            missing=missing))
        print(f"[bench] {name}: gen={'OK' if ok else 'FAIL'} "
              f"render={'OK' if rendered else 'FAIL'} "
              f"missing={missing or '-'}")
    return results


# ============================================================
# COMPARAISON + RAPPORT
# ============================================================

def compare(name):
    """Retourne (status, mae, pct, note). status: PASS/FAIL/NEW/MISSING"""
    import numpy as np
    from PIL import Image
    ref_p = os.path.join(BASELINE, name + ".png")
    cur_p = os.path.join(CURRENT, name + ".png")
    if not os.path.exists(cur_p):
        return "MISSING", None, None, "rendu absent"
    if not os.path.exists(ref_p):
        return "NEW", None, None, "pas de référence (lancer --update)"
    ref = np.asarray(Image.open(ref_p).convert("RGB"), dtype=np.int16)
    cur = np.asarray(Image.open(cur_p).convert("RGB"), dtype=np.int16)
    if ref.shape != cur.shape:
        return "FAIL", None, None, f"tailles {ref.shape} vs {cur.shape}"
    diff = np.abs(ref - cur)
    mae = float(diff.mean())
    pct = float((diff.max(axis=2) > 10).mean() * 100.0)
    status = "PASS" if (mae <= THRESH_MAE and pct <= THRESH_PCT) else "FAIL"
    return status, mae, pct, ""


def diff_image(name):
    import numpy as np
    from PIL import Image
    ref = np.asarray(Image.open(os.path.join(BASELINE, name + ".png"))
                     .convert("RGB"), dtype=np.int16)
    cur = np.asarray(Image.open(os.path.join(CURRENT, name + ".png"))
                     .convert("RGB"), dtype=np.int16)
    d = np.abs(ref - cur).max(axis=2)
    amp = np.clip(d * 8, 0, 255).astype(np.uint8)
    rgb = np.zeros((*amp.shape, 3), dtype=np.uint8)
    rgb[..., 0] = amp
    rgb[..., 1] = (cur.mean(axis=2) * 0.25).astype(np.uint8)
    rgb[..., 2] = (cur.mean(axis=2) * 0.25).astype(np.uint8)
    out = os.path.join(REPORT, name + "_diff.png")
    Image.fromarray(rgb).save(out)
    return out


def write_report(rows, gen_results):
    os.makedirs(REPORT, exist_ok=True)
    gen_by_name = {g["name"]: g for g in gen_results}
    rows_sorted = sorted(rows, key=lambda r: (r[1] == "PASS", r[0]))
    html = ["<!doctype html><meta charset='utf-8'>",
            "<title>House — banc visuel</title>",
            "<style>body{font-family:sans-serif;background:#111;color:#eee}",
            "td{padding:4px;text-align:center}img{width:320px}",
            ".PASS{color:#7c6}.FAIL{color:#e66;font-weight:bold}",
            ".NEW{color:#fc6}.MISSING{color:#e66}</style>",
            "<h1>House — banc de non-régression visuel</h1>",
            "<table>"]
    html.append("<tr><th>config</th><th>statut</th><th>MAE</th><th>%px</th>"
                "<th>invariants</th><th>référence</th><th>actuel</th>"
                "<th>diff ×8</th></tr>")
    for (name, status, mae, pct, note) in rows_sorted:
        g = gen_by_name.get(name, {})
        inv = "OK"
        if not g.get("finished", True):
            inv = "GEN FAIL"
        elif g.get("missing"):
            inv = "manque: " + ", ".join(g["missing"])
        ref_rel = os.path.relpath(os.path.join(BASELINE, name + ".png"), REPORT)
        cur_rel = os.path.relpath(os.path.join(CURRENT, name + ".png"), REPORT)
        dif = ""
        if status == "FAIL" and mae is not None:
            diff_image(name)
            dif = f"<img src='{name}_diff.png'>"
        html.append(
            f"<tr><td>{name}</td><td class='{status}'>{status}</td>"
            f"<td>{mae:.2f}" if mae is not None else
            f"<tr><td>{name}</td><td class='{status}'>{status}</td><td>-")
        html.append(f"</td><td>{pct:.2f}%" if pct is not None else "</td><td>-")
        html.append(f"</td><td>{inv}</td>"
                    f"<td><img src='{ref_rel}'></td>"
                    f"<td><img src='{cur_rel}'></td>"
                    f"<td>{dif}</td></tr>")
    html.append("</table>")
    with open(os.path.join(REPORT, "report.html"), "w") as f:
        f.write("\n".join(html))


# ============================================================
# MAIN
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true",
                    help="(re)génère les images de référence")
    ap.add_argument("--only", default=None,
                    help="filtre les configs par sous-chaîne")
    ap.add_argument("--fast", action="store_true",
                    help="noyau de configs rapides uniquement")
    args = ap.parse_args()

    sel = configs()
    if args.fast:
        sel = [c for c in sel if c["fast"]]
    if args.only:
        sel = [c for c in sel if args.only in c["name"]]
    if not sel:
        print("Aucune config ne correspond.")
        return 1

    out_dir = BASELINE if args.update else CURRENT
    gen_results = render_all(sel, out_dir)

    if args.update:
        bad = [g for g in gen_results
               if not (g["finished"] and g["rendered"]) or g["missing"]]
        print(f"\n[bench] Références écrites: {len(gen_results) - len(bad)}"
              f"/{len(gen_results)} OK")
        for g in bad:
            print(f"[bench]   ⚠️ {g['name']}: finished={g['finished']} "
                  f"missing={g['missing']}")
        return 1 if bad else 0

    rows = []
    for cfg in sel:
        status, mae, pct, note = compare(cfg["name"])
        g = next(g for g in gen_results if g["name"] == cfg["name"])
        if status == "PASS" and (not g["finished"] or g["missing"]):
            status = "FAIL"
            note = "invariants"
        rows.append((cfg["name"], status, mae, pct, note))
    write_report(rows, gen_results)

    n_fail = sum(1 for r in rows if r[1] != "PASS")
    print("\n========== BANC VISUEL ==========")
    for (name, status, mae, pct, note) in rows:
        m = f"MAE={mae:.2f} px%={pct:.2f}" if mae is not None else note
        print(f"  {status:8s} {name:24s} {m}")
    print(f"=========== {len(rows) - n_fail}/{len(rows)} PASS ===========")
    print(f"Rapport: {os.path.join(REPORT, 'report.html')}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
