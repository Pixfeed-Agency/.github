# Changelog — House Generator

## v1.3.0 — Refonte structurelle: menuiseries articulées, briques coupées, charpente

**Validé au rendu Cycles headless à chaque bloc.**

### 🧱 Briques coupées (fini les créneaux!)
- Nouveau système de DÉCOUPE des cellules (`_clip_cell`/`_emit_cell`):
  chaque brique traversée par un bord d'ouverture ou un bout de mur est
  émise comme brique COUPÉE (instance à l'échelle) — tableaux de portes/
  fenêtres nets, coins de murs droits. Les deux moteurs (instances,
  Geometry Nodes) portent l'échelle par brique (attribut brick_scale).

### 🚪🪟 Menuiseries RÉELLEMENT ouvrables (propriété 'ouverture' 0→1)
- Porte d'entrée: panneau mouluré V2 (montants/traverses/panneaux en
  retrait), pivot sur gonds + driver — simple ET double battant (miroir)
- Fenêtre à battant (CASEMENT): OUVRANT SÉPARÉ du dormant, VITRE
  intégrée au battant (elle pivote avec lui), charnière + driver 85°
- Volets: chaque battant est un objet articulé, propriété 'fermeture'
  (0 = ouverts contre le mur, 1 = fermés sur la fenêtre)
- Porte de garage sectionnelle: coulisse vers le haut (driver)

### 🏠 Toiture: la construction visible
- CHEVRONS apparents sous les débords d'égout
- PLANCHES DE RIVE (fascia) le long des égouts
- TUILES DE RIVE le long des pignons (+ faîtières existantes)
- Tuile maître V2: profil canal galbé lissé (~200 tris partagés),
  micro-variations de pose par tuile

### 🎨 Matériaux V2 (module look.py) — la maison, pas le décor
- BRIQUES: variation PAR BRIQUE (Object Info Random), marbrures de
  cuisson, grain, bump — remplace 685 lignes de nodes qui rendaient
  noir-uniforme
- Tuiles terre cuite (teinte par tuile), mortier sable granuleux, bois
  veiné (portes/volets/terrasse), zinc brossé (gouttières), crépi
  (garage), béton (fondations), verre teinté, PVC satiné, pelouse

### Restant (prochaine itération, assumé)
- Multi-volumes (plans en L), pièces intérieures, tuiles HIP/GAMBREL,
  articulation des autres types de fenêtres, matrice de rendus de
  conformité par option


## v1.2.0 — Le grand bond: 9 fonctionnalités + validation Blender headless réelle

**Première version TESTÉE dans un vrai Blender 4.2** (bpy headless):
13/13 configurations génèrent sans erreur, rendus Cycles validés à l'image.

### Nouvelles fonctionnalités (features.py)
- **Éclairage automatique**: soleil chaud + lumière de débouchage + ciel
- **Tuiles de couverture** (GABLE/monopente): tuiles mécaniques instanciées
  via Geometry Nodes (~1300-2000 tuiles, 1 objet), effet d'écailles par
  rangée, FAÎTIÈRES sur le faîtage, couleur réglable
- **Gouttières + descentes** le long des égouts (descentes contre le mur),
  adaptées à chaque type de toit
- **Cheminée** en brique avec couronnement, traversant le toit près du
  faîtage
- **Garage attenant** (largeur/profondeur/côté réglables): 3 murs, toit
  monopente débordant, PORTE SECTIONNELLE à panneaux
- **Terrasse arrière** en lames de bois sur structure
- **Balcon** au 1er étage avec rambarde à poteaux (posé à la hauteur
  réelle des murs briques)
- **Volets battants** de part et d'autre de chaque fenêtre (option)
- **Portes**: POIGNÉE (platine + béquille) sur chaque panneau; porte
  FRANÇAISE réellement vitrée (vitre + matériau verre dans chaque battant)

### Corrections issues des rendus réels
- **Matériau briques**: 4 assombrisseurs globaux neutralisés — le dégradé
  vertical noir→blanc lisait le Z-objet d'une brique de 7cm (tout sortait
  quasi noir), l'AO multipliait par 0.5, l'humidité par 0.65
- **Linteaux**: fallback en PLATE-BANDE (1 rangée couchée) quand le cours
  de soldats ne tient pas sous l'égout — les fenêtres hautes n'avaient
  AUCUN linteau
- Tuiles: chevauchement coplanaire entre rangées éliminé (bandes noires
  de z-fighting), clamp au faîtage

### Limites connues (documentées)
- Plans en L non supportés (le corps est rectangulaire + garage attenant)
- Briques coupées aux ouvertures et pièces intérieures: prochains chantiers
- Tuiles sur HIP/GAMBREL: à venir


## v1.1.1 — Tour du propriétaire: 40+ correctifs post-audit

Trois audits croisés sur l'état v1.1.0 (dont un sur les nouveautés
elles-mêmes) — corrections notables:

### Géométrie / architecture
- **MANSARDE réellement corrigée**: les points de cassure étaient aux
  mauvaises positions (le "brisis 68°" ne faisait que ~39°). Reconstruite
  en dalles à épaisseur verticale, cassures près des façades.
- **Plans de toit ancrés à la façade** (GABLE/HIP): le plan pivotait au
  bord du débord → pente effective plus faible que demandée + jour d'air
  entre mur et toit. Les égouts descendent maintenant de o·tan(pente).
- **Dégagements pitch-aware**: solidify épaissit perpendiculairement →
  chute verticale = t/cos(θ). Plafonds des murs et briques adaptés
  (validé: 0 collision à 20/35/50°, marge ≥2.1cm).
- **Pignons maçonnés visibles**: le toit GABLE ne ferme plus ses pignons
  quand les murs sont en briques (ses triangles pleins les masquaient).
- **Briques flottantes éliminées** (pignons/rampants): limites de colonne
  monotones → arrêt sûr.
- **Linteaux**: bande d'exclusion au-dessus des ouvertures (les soldats
  s'interpénétraient avec les briques du mur), rang centré sur
  l'ouverture, clamp au plafond effectif par mur (wall_top).
- **Acrotère en anneau manifold**, seuil de porte butant contre le socle
  (fini le z-fighting), **porte posée SUR le soubassement**, ouvertures
  alignées, fondations générées en premier, dalles d'étage à la hauteur
  réelle des briques, cutter booléen en solver EXACT et masqué.

### Moteur Geometry Nodes
- **FIX critique**: le master en hide_viewport sortait du depsgraph →
  Object Info vide → murs invisibles. Passage en hide_set (œil) via
  keep_evaluated.
- Node group neuf par génération (l'ancien remove-par-nom cassait la
  maison précédente), nettoyage des objets partiels si fallback.

### Interface & propriétés
- Le swatch "Couleur toit" éditait une propriété que le générateur ne
  lisait pas; la section matériaux "murs simples" (8 styles, 3 qualités)
  ne pilotait rien — remplacée par les vraies couleurs murs/toit/planchers.
- Exposés: type/qualité de porte, ratio hauteur fenêtres, avertissement
  UI quand la pente sera clampée, boutons du mode manuel (add_wall/door/
  window/toggle_plan étaient implémentés mais inaccessibles!).
- num_windows_back enfin câblé; estimation de briques corrigée (~28%
  de surestimation); version lue depuis bl_info (1.1.1 partout).
- 16 propriétés mortes supprimées; callbacks update ajoutés aux couleurs
  et réglages qui échappaient à la mise à jour auto; auto_lighting off
  par défaut (il levait un warning à chaque génération).
- ~550 lignes de code mort supprimées (ancien chemin "géométrie
  complète" et tout son sous-arbre).
- pbr_scanner: résolution du dossier textures par __file__ (le scan de
  sys.modules pouvait matcher un autre addon).

## v1.1.0 — Mise à niveau architecturale + moteur Geometry Nodes

### 🏛️ Conformité architecturale des toits

- **Pentes normées par type de toit** (`PITCH_RANGES`): le slider global est
  désormais clampé à la plage réaliste de chaque toit — monopente 5-25°
  (avant: une monopente à 35° générait un mur pignon de 10m!), 2 pans et
  4 pans 15-50°, mansarde 15-30° (terrasson). Valeur unique partagée entre
  le toit, les murs adaptés et les briques (`_effective_pitch`).
- **GABLE — faîtage selon la grande dimension**: le faîtage court maintenant
  le long du plus grand côté, comme en construction réelle (avant: toujours
  le long de Y, donnant un toit anormalement haut pour toute maison plus
  large que longue).
- **GAMBREL — vraies proportions de mansarde**: brisis raide fixe à 68° sur
  25% de la demi-largeur, terrasson doux = pente utilisateur. Les
  proportions étaient inversées (brisis doux, terrasson quasi plat), ce qui
  donnait un gable "cassé" au lieu d'un comble à la Mansart.
- **Débords différenciés rives/égouts**: les rives (pignons) font maintenant
  10-30cm quand les égouts gardent le débord complet (GABLE, SHED, GAMBREL)
  — conforme à la pratique réelle.
- **FLAT — acrotère**: le toit-terrasse a désormais son muret périphérique
  de 45cm, LE marqueur visuel d'un toit plat réel.

### 🧱 Maçonnerie

- **Pignons maçonnés sous toit GABLE**: les murs pignons en briques suivent
  le triangle du toit (validé par simulation: 0 collision avec la dalle,
  gap ≥ 2cm à toutes les pentes 20-50°). L'orientation suit automatiquement
  le faîtage.
- **Linteaux en cours de soldats**: les linteaux sont désormais un rang de
  briques VERTICALES (soldier course) au-dessus des ouvertures — comme un
  vrai linteau maçonné — au lieu de briques couchées empilées qui se
  superposaient aux briques du mur. Rotations validées numériquement pour
  les 4 murs.
- **Murs capés sous les égouts**: pour TOUS les toits en pente, les murs
  briques s'arrêtent sous la face inférieure de la dalle (avant: seul le
  SHED était géré; les briques transperçaient les toits GABLE/HIP/GAMBREL
  près des avant-toits).

### 🏠 Fondations

- **Soubassement enfin visible**: l'ancien socle affleurait exactement le
  sol (entièrement enterré = invisible!). Il dépasse maintenant de 15-20cm,
  comme un vrai soubassement.
- **Seuil de porte (perron)**: une marche devant l'entrée franchit le
  soubassement — sans elle, le bas de la porte était masqué par la bande
  de socle.

### ⚙️ Moteur Geometry Nodes (opt-in)

- **Nouveau moteur d'instanciation** (`materials/brick_geonodes.py`),
  activable par la case "Moteur Geometry Nodes" du panneau Murs:
  - **1 seul objet** au lieu de milliers d'instances (outliner propre,
    viewport fluide, mémoire quasi nulle — vraies instances GPU)
  - Nuage de points (1 vertex par brique, rotation en attribut
    `brick_rot`) + node group de 5 nodes (`Mesh to Points` →
    `Instance on Points` ← `Object Info` brique maître)
  - Fallback automatique vers le moteur classique en cas d'erreur
- **Refactor**: le calcul des positions (`compute_all_brick_positions`),
  la brique maître (`create_brick_master`) et la hauteur réelle
  (`compute_real_wall_height`) sont désormais partagés entre les deux
  moteurs — une seule source de vérité.

### Notes de mise à niveau

- Les pentes hors plage sont clampées avec un message console explicite.
- Le moteur Geometry Nodes nécessite Blender 4.x (interface node group 4.x).
- Testé par simulation numérique (collisions toit/briques, rotations des
  soldats, couverture des linteaux); un test visuel dans Blender 4.2 reste
  recommandé avant production.

## v1.0.x — Assainissement complet (sessions précédentes)

- ~60 bugs corrigés sur l'ensemble du code: compatibilité Blender 4.2+
  (shadow_method, blend_method, noise_basis…), collisions briques/toit
  monopente, fenêtres décalées d'une demi-hauteur en murs briques,
  chevauchement des briques des murs latéraux, toit HIP inversé, pente
  stockée en radians affichée ~2005°, fondations générées deux fois,
  6 presets de briques tous rouges, mode manuel entièrement réécrit,
  propriétés dupliquées supprimées, mise à jour auto implémentée,
  `blender_manifest.toml` ajouté (format Extension 4.2).
