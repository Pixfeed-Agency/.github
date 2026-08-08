# Changelog — House Generator

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
