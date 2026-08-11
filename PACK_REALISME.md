# Pack réalisme — textures scannées et ciel HDRI

House génère des matériaux **100 % procéduraux** par défaut: l'extension
reste légère (~2 Mo), autonome, et rien à télécharger. Mais le procédural
a un plafond de réalisme: les moteurs d'archviz qui « font vrai »
(Enscape, Lumion, les rendus Revit) posent des **photos de vraies
surfaces**.

Le pack réalisme branche ce standard, **en option**, sans alourdir
l'extension: les textures vivent dans un dossier chez vous.

## 1. Où trouver les textures (gratuit, licence CC0)

| Source | Ce qu'on y prend |
|---|---|
| [polyhaven.com/textures](https://polyhaven.com/textures) | pierre, plâtre, tuiles, herbe — photoscannés, 8K minimum |
| [ambientcg.com](https://ambientcg.com) | même chose, séries numérotées (`PaintedPlaster017`…) |
| [polyhaven.com/hdris](https://polyhaven.com/hdris) | ciels HDRI (catégorie « pure sky ») |

Licence CC0 = domaine public, usage commercial libre, sans attribution.

**Sélections qui marchent bien pour une longère française:**
- pierre: `old_stone_wall`, `stone_wall`, `rustic_stone_wall`
- enduit: `plastered_wall_02`, `painted_plaster_wall`, `PaintedPlaster017`
- tuiles: `clay_roof_tiles_02`, `roof_07`
- sol: n'importe quelle pelouse/`grass` scannée
- ciel: `kloofendal_48d_partly_cloudy_puresky` (soleil franc + nuages)

## 2. Structure du dossier

```
MonPackRealisme/
├── pierre/     ← façades quand la finition des murs est PIERRE
├── enduit/     ← façades crépi (CREPI_FIN, CREPI_GROS, AUTO)
├── sol/        ← pelouse / terrain
├── tuiles/     ← pans de toit en couverture « Lisse »
└── un_ciel.hdr ← à la RACINE (ou .exr)
```

Dans chaque sous-dossier, versez le contenu du zip téléchargé. Les
conventions de nommage Poly Haven et ambientCG sont reconnues telles
quelles (`*_Color`/`*_diff`, `*_Roughness`/`*_rough`, `*_NormalGL`/
`*_nor_gl`, `*_AmbientOcclusion`, `*_Displacement`) — **ne renommez
rien**. Un niveau de sous-dossier est toléré (`pierre/old_stone_wall_8k/…`).

Seule la map **couleur est obligatoire**; les autres enrichissent le
résultat si elles sont là.

## 3. Activation

Panneau **House → « Pack réalisme (textures CC0) »** → choisissez le
dossier. La ligne « Trouvé: … » liste ce qui a été reconnu. Générez.

Un slot vide, incomplet ou absent retombe **silencieusement** sur le
matériau procédural: rien ne casse jamais, et le dossier vide rend
House strictement identique à avant.

## 4. Quelle résolution choisir

Mesures faites sur ce projet (pic mémoire du processus Blender, rendu
d'une longère de 21 m avec terrain):

| Configuration | Pic RAM |
|---|---|
| Tout procédural (sans pack) | ~0,9 Go |
| 1 matériau 8K (4 maps) | ~1,9 Go |
| 2 matériaux 8K (8 maps) | ~2,6 Go |

Extrapolation: le **16K coûte 4× le 8K** (~5 Go par matériau). En
pratique 2 slots seulement sont actifs en même temps (une finition de
mur + le sol).

**Recommandation**: le **8K** est le bon compromis — à distance de
façade, l'œil ne distingue pas le 16K, et vous gardez de la marge
mémoire. Réservez le 16K aux très gros plans, sur une machine ≥ 32 Go.

Préférez les variantes **JPG** aux PNG/EXR: même qualité visuelle,
fichiers 5 à 10× plus légers.

## 5. Ce qui reste procédural (et pourquoi)

- **Encadrements et chaînages en pierre de taille**: ce sont de vrais
  volumes bâtis, pas des surfaces plates — ils gardent leur matériau
  calcaire procédural, cohérent avec la façade texturée.
- **Tuiles 3D** (couverture « Tuiles »): chaque tuile est un objet
  instancié. Plaquer la photo d'un pan de toit entier sur chaque tuile
  n'aurait aucun sens. Le slot `tuiles/` sert quand la couverture est
  en mode « Lisse » (dalle simple).
- **Menuiseries, volets, gouttières, charpente**: pilotés par vos
  couleurs (RAL), donc procéduraux par construction.

## 6. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| « Aucun set reconnu » | sous-dossiers mal nommés | exactement `pierre`, `enduit`, `sol`, `tuiles` (minuscules) |
| Un slot n'apparaît pas dans « Trouvé » | pas de map couleur | vérifiez qu'un fichier contient `Color`, `diff` ou `albedo` |
| La pierre ne change pas | finition des murs ≠ PIERRE | panneau « Assets & finitions » → Murs → Pierre |
| Rendu très sombre / magenta | HDRI corrompu | House le détecte et prévient en console; retéléchargez le `.hdr` |
| Blender rame ou sature | 16K sur plusieurs slots | repassez en 8K |
