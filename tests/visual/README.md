# Banc de non-régression visuel — House

## Pourquoi (analyse de l'extension)

House fait ~14 800 lignes, **81 propriétés** et ~40 builders qui
produisent des pixels. L'historique du projet montre que ses pires bugs
étaient **visuellement évidents mais programmatiquement silencieux**:

- le matériau "variation par tuile" écrit en v1.3 et **jamais branché**
  (toit orange uniforme pendant 5 versions);
- le modificateur Boolean des ouvertures qui **avalait la façade du
  garage** (solveur EXACT sur boîtes en recouvrement);
- des sections de code **dupliquées** dont la seconde copie (ancienne)
  masquait les volets articulés et les bonnes rotations de tuiles;
- des tuiles **couchées dans la dalle** sur les pans montant en ±X.

Tous rendaient `{'FINISHED'}`. Aucun test unitaire ne les aurait vus.
D'où ce banc: des **golden images** re-rendues et comparées.

## Ce que le banc couvre

~25 configurations choisies pour traverser chaque chemin de code
visible: les 5 types de toit, les 2 moteurs briques (GN + instancing),
les modes matériaux (preset procédural, couleur, PBR scanné),
l'appareillage, les murs enduit + Boolean, les ailes (L, U, sur croupe,
sur mansarde), le garage-aile (briques ET enduit — le bug du Boolean
vivait dans la variante enduit), velux et lucarnes, étages + balcon +
coulissantes, deux vues intérieures (escalier, chambres), le mode
environnement complet (herbe/haie/ciel/caméra auto) et un preset
régional (chemin `apply_preset`).

Chaque config vérifie AUSSI des **invariants**: opérateur FINISHED et
présence d'objets clés (`Wing_Walls`, `Roof_Tiles`, `Stair_Steps`…).

## Bonnes pratiques appliquées

- **Déterminisme**: Cycles CPU, `seed=0`, 24 samples + denoise OIDN,
  480×300; toute la randomisation procédurale du code est seedée.
- **Seuils calibrés par double-run**: le bruit résiduel Cycles mesure
  MAE ≈ 0.3 et ≈ 0.2 % de pixels; les seuils (MAE ≤ 2.0, ≤ 1.5 % de
  pixels avec delta canal > 10) laissent ×5 de marge au bruit tout en
  attrapant un matériau débranché ou un mur manquant.
- **Références committées** dans `baseline/` (petites PNG). `current/`
  et `report/` sont ignorés par git.
- **Rapport HTML** `report/report.html`: référence | actuel | diff
  amplifiée ×8, échecs en tête.
- **CI-compatible**: exit 0/1.

## Usage

```bash
python3 tests/visual/bench.py            # comparer aux références
python3 tests/visual/bench.py --fast     # noyau de 8 configs (~5 min)
python3 tests/visual/bench.py --only hip # filtrer par nom
python3 tests/visual/bench.py --update   # REBASER les références
```

Workflow: après un changement voulu qui modifie l'image, vérifier le
rapport à l'œil puis `--update` pour rebaser, et committer les
nouvelles références AVEC le changement de code.
