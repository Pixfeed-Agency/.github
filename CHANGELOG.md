# Changelog — House Generator

## v1.27.0 — TABLEAU DE PIÈCES + corrections géométrie (5/5 du brief)

Le dernier chantier du brief (le plan par les surfaces) et les défauts
de proportions relevés sur les rendus.

- **Tableau de pièces** (`use_rooms_table`): chaque ligne = une pièce
  du brief (nom, type chambre/bureau/SdB/WC, surface cible m²). La
  bande arrière se DIMENSIONNE pour loger la somme (le refend recule/
  avance), les cloisons découpent des largeurs proportionnelles, les
  rôles pilotent l'aménagement (sanitaires dans la pièce déclarée SdB)
  et chaque pièce reçoit sa fenêtre (S4). Bilan des surfaces réelles
  affiché à la génération. Prime sur le mode programme
- **Conflit de cotes VISIBLE**: quand le faîtage cible impose une autre
  pente que le slider, le panneau Toit l'affiche ("Faîtage 7,80 m →
  pente 52,5°, le slider 45° est ignoré") au lieu de choisir en
  silence — et signale un faîtage inatteignable (>60°)
- **Le pignon est un MUR**: objet séparé au nu de la façade, épaisseur
  du mur, finition des façades (pierre, enduit…) — le triangle greige
  "matériau toit" au milieu d'une façade en pierre criait généré.
  (Référence walls_stucco rebasée: pignon désormais enduit)
- **Doublage plâtre des pignons dans les combles** (le dos brun de la
  maçonnerie n'apparaît plus dans les rendus intérieurs)
- **Preset LONGÈRE modernisé**: pierre vue + encadrements de taille +
  tuiles plates + combles aménagés + débord court 0,30 m (les vraies
  longères ne débordent pas de 0,50)
- 81 invariants, banc fast 10/10

## v1.26.0 — VOLUMÉTRIE: faîtage cible + combles aménagés (4/5 du brief)

Les deux cotes de coupe d'un vrai brief (faîtage ET pente) et le
niveau habitable sous rampants des longères.

- **Faîtage cible** (`ridge_height_target`, GABLE/HIP/SKELETON): la
  hauteur de faîtage visée DÉRIVE la pente — comme dans un vrai outil
  d'architecture, l'une des deux cotes pilote l'autre. La cote prime
  sur la plage stylistique (jusqu'à 60°, tuiles plates de longère);
  0 = la pente du slider commande (comportement historique)
- **Combles aménagés** (`attic_habitable`, plain-pied GABLE): plancher
  à l'arase (18cm, troué par la trémie), jambettes de 1,00 m, rampants
  plâtrés, plafond plat à 2,40 m — les hauteurs du brief type ("2,40 m
  sous entrait, mur de 1,00 m sous sablière"). Garde-fou si la
  pente/portée ne permet pas d'aménager
- **L'escalier y monte VRAIMENT**: volée unique recalculée sur la
  hauteur d'arase + plancher (marches ~18cm), trémie + garde-corps à
  l'arrivée. Corrige l'escalier fantôme (0 volée en plain-pied)
- **Fermes apparentes** (`attic_trusses`): entraits bois visibles sous
  le plafond tous les ~2,40 m, abouts encastrés dans les rampants
- **Éclairage des combles**: suspensions 2700K automatiques (pas de
  fenêtre de toit = rendu intérieur noir sinon)
- Règle de construction respectée: TOUT le second œuvre des combles
  reste SOUS le plan des versants avec 22cm de réserve (chevrons +
  isolant) — la v0 du chantier faisait percer rampants et abouts
  d'entraits à travers les tuiles, invariant pytest dédié désormais
- 79 invariants, banc fast 10/10 (défauts pixel-identiques)

## v1.25.0 — PIERRE procédurale + RAL menuiseries (3/5 du brief)

LE matériau manquant révélé par le brief longère — 100% procédural,
zéro texture embarquée (comme demandé).

- **Pierre vue** (`wall_finish = PIERRE`): appareillage par Voronoï —
  chaque cellule est une pierre calcaire de teinte variée (assises
  plus longues que hautes), joints beurrés teinte sable, joints en
  creux + grain de taille au bump. Couleur de base au choix
- **Moellons de soubassement** automatiques: quand la façade est en
  pierre, la fondation passe en moellons PLUS PETITS et PLUS SOMBRES
  (le brief: "moellons plus foncés sur 60 cm")
- **Encadrements en PIERRE DE TAILLE** (géométrie réelle, option):
  jambages 16cm + linteau monolithe 24cm + appui saillant autour de
  CHAQUE ouverture — dérivés de la spec S4, donc compatibles tableau
  d'ouvertures et mode auto; + **CHAÎNAGES D'ANGLE à harpes
  alternées** aux 4 angles (assises de 34cm)
- **Menuiseries RAL** (`joinery_color`): la teinte des dormants et
  ouvrants est enfin pilotable (le RAL 7016 du brief) — blanc
  historique par défaut (références intactes)
- Validé sur la façade du brief: pierre vue + encadrements sur les
  baies ET les fenêtres du tableau + chaînages + moellons — rendu
  conforme; 77 invariants, banc fast 10/10

## v1.24.0 — TABLEAU D'OUVERTURES hétérogènes (2/5 du brief)

Le manque n°1 des briefs réels: House imposait UN type et UNE taille
de fenêtre pour toute la maison. Le tableau les libère.

- **Une ligne = une ouverture**: façade, type (battante / baie
  coulissante / châssis fixe / PORTE), largeur × hauteur, ALLÈGE,
  position en mètres le long du mur (les travées d'un brief se posent
  directement), étage — UIList avec +/− dans le panneau principal
- **Le tableau REMPLACE l'auto** quand il est actif; il alimente la
  spec S4 unique → trous briques, Booleans, menuiseries, voilages et
  volets suivent sans code supplémentaire (l'architecture S4 paie)
- **Portes multiples**: la porte de service du brief existe enfin —
  chaque ligne PORTE devient une vraie porte sur SA façade, perron
  sur la première porte avant uniquement
- **Volets intelligents en mode tableau**: sur les battantes
  seulement (une baie coulissante n'a pas de volets battants)
- Validé sur la façade du brief longère: porte 1.00×2.15 + 3 baies
  2.40×2.15 toute hauteur + 3 fenêtres 1.20×1.40 allège 0.90 SUR LA
  MÊME FAÇADE + porte de service nord — rendu conforme
- 76 invariants (test façade mixte: dimensions, allèges, volets
  comptés); banc fast 10/10 (l'auto est inchangé)

## v1.23.0 — TERRAIN & IMPLANTATION (chantier terrain, 1/5 du brief)

La maison seule, sur une parcelle générée, ou sur TON terrain.

- **3 modes** (panneau "Terrain & implantation"): Auto simple
  (historique, inchangé au pixel), **Parcelle** paramétrique,
  **Mon terrain** (slot `terrain_asset` — votre mesh remplace le sol,
  House garde soleil et implantation). L'hybride = parcelle + slots
- **Parcelle**: dimensions réelles (ex. 40×60), **NORD** (boussole),
  **pente %** (la maison pose sur une plateforme de terrassement avec
  talus de raccord 4m), côté d'ACCÈS (l'allée gravier va du bord de
  parcelle jusqu'au perron/garage), haie en LIMITE de parcelle, herbe
  sur toute la parcelle (hors emprise et allée)
- **Implantation**: position X/Y et ORIENTATION de la maison sur la
  parcelle (la maison reste à l'origine moteur — c'est la parcelle
  qui se place autour: zéro risque sur le bâti)
- **SOLEIL PAR HEURE** (6-21h): course est→ouest selon le nord,
  élévation réaliste, chaud et rasant matin/soir — "lumière de fin
  d'après-midi" d'un brief = `sun_hour 17.5`; ciel Nishita aligné
- Corrections trouvées au rendu: allée calculée en espace parcelle
  (elle partait à côté quand la maison était décalée/tournée), z du
  terrain UNIFIÉ pente+plateforme+talus (l'allée plongeait sous le
  plateau), herbe bornée à la parcelle (prédicat inside + z pente)

## v1.22.0 — NIVEAU RENDU CLIENT: finitions ext. + intérieur habité

L'objectif "rendu d'artiste/architecte intérieur-extérieur" — les cinq
phases actées, slots d'assets prioritaires partout.

EXTÉRIEUR (les 4 tells d'audit corrigés):
- **SOFFITES**: sous-face d'égout FERMÉE (lambris) sur GABLE, SHED,
  ailes et toit squelette — fini la bande noire de chevrons à nu
- **PERRON + SEUIL**: dalle de seuil sous la porte + marche si socle
  haut — la porte ne donne plus sur l'herbe
- **VITRES VIVANTES**: reflet de ciel par Fresnel (mix glossy) — les
  rectangles noirs en plein jour étaient un tell majeur
- **GONDS de volets** (pattes sur la ligne de charnière) et RIVES
  FINES en finition ardoise (plus de demi-ronds terre cuite)

INTÉRIEUR (de "coquille" à "habité"):
- **SECOND ŒUVRE**: plinthes 100mm sur tout le périmètre et les deux
  faces des cloisons (passages déduits) + CHAMBRANLES de fenêtres —
  interiors.build_trim, alimenté par la spec d'ouvertures S4
- **ÉCLAIRAGE INTÉRIEUR** (option): suspension 2700K par pièce, deux
  au séjour (câble + abat-jour + point chaud)
- **CUISINE paramétrique** (mode programme): linéaire caissons + plan
  de travail + crédence + meubles hauts + évier + plaque
- **SDB + WC équipés**: meuble-vasque, miroir, douche (receveur +
  paroi verre + colonne), cuvette + réservoir + lave-mains — posés
  dans LEURS cellules du programme
- **MOBILIER**: lit par chambre (sommier/matelas/tête), table et
  canapé au séjour
- **SLOTS partout** (kitchen/bathroom/bed/table/sofa_asset): vos
  propres meubles remplacent le procédural, posés à l'échelle au sol
  sans déformation — le procédural n'est que le repli
- **Caméra intérieure** en un clic (20mm, œil 1.5m, exposition
  intérieure) — house.camera_interior
- Références du banc rebasées (soffites/perron/verre changent chaque
  façade)

## v1.21.0 — Audit des mesures automatiques + ÉLECTRICITÉ

Ré-analyse complète sur les modèles livrés (rendus d'audit rapprochés
+ mesures numériques) — quatre vrais bugs corrigés, une fonctionnalité.

- **Fenêtres trop hautes (CORRIGÉ)**: les linteaux flottaient à ratio
  du plafond (2.30, AU-DESSUS de la porte à 2.20). Le haut de chaque
  fenêtre s'aligne désormais sur le LINTEAU standard (`norms.LINTEAU_H`
  = 2.15, comme une vraie façade) → allège 0.91 sur le pavillon type.
  Toutes les références du banc rebasées
- **Porte de garage 19cm trop basse (CORRIGÉ)**: les panneaux étaient
  construits en local PUIS re-translatés de z0 (double translation) —
  porte enterrée dans le seuil et FENTE NOIRE de 21cm sous le linteau.
  La porte remplit son ouverture (0.21 → 2.24 pour 0.20 → 2.25)
- **Gouttière volante (CORRIGÉ)**: les descentes EP de l'aile/garage
  pendaient EN L'AIR à o_rake devant le pignon — plaquées contre
  l'angle du mur
- **Voilage devant la façade (CORRIGÉ)**: il pendait 3cm DEVANT le nu
  extérieur (mesuré y=[-0.03,+0.01]) — désormais côté pièce, 5cm
  derrière le nu intérieur (y=+0.33)
- **✅ ÉLECTRICITÉ (NF C 15-100)**: nouvelle option "Électricité" —
  prises de courant (axe 0.25m du sol fini) réparties dans CHAQUE
  pièce, interrupteur à 1.10m près de chaque porte, séjour à n+2
  prises (minimum normatif 5); **nombre par pièce réglable** (1-8);
  régénération incrémentale (tag interior)
- 2 nouveaux tests (mesures de façade verrouillées + électricité
  comptée et mesurée) → 75 invariants

## v1.20.0 — Tuiles COUPÉES aux arêtiers et noues (S5, partie 2)

Fin du crénelage: sur le toit squelette, les tuiles de bord sont de
VRAIES tuiles coupées, plus des tuiles omises.

- Décision par les 4 COINS de l'emprise de chaque tuile: tout dedans →
  instance GN (léger); partiel → copie réelle du master BISECTÉE par
  les plans verticaux des arcs du pan (côté égout conservé), fusionnée
  dans `Roof_Tiles_Cut`
- `skeleton.ridge_segments` réécrit: appariement par LIGNE SUPPORT +
  chevauchement d'intervalles (la fragmentation en pièces cassait
  l'appariement segment-à-segment → arêtiers sans couvre-joint et
  bords sans plan de coupe); un arc FUSIONNÉ par paire de pans
- Trois corrections trouvées par la boucle rendu→diagnostic: ordre
  index_update/mapping bmesh, pièces dégénérées acceptées comme
  "dedans", et PLAN INFINI d'une noue prolongée qui tranchait des
  tuiles à l'autre bout du pan (coupe désormais bornée à la portée
  du segment d'arc)
- Croupe legacy (HIP) inchangée au pixel près; référence
  roof_skeleton_L rebasée; 73 invariants verts

## v1.19.0 — Masters de tuiles PAR COUVERTURE (S5, partie 1)

- La géométrie du master suit enfin la couverture: **ARDOISE = élément
  PLAT rectangulaire** (8mm, pose à pureau), **BÉTON = profil bas**
  (galbe 12mm), terre cuite = tuile canal galbée (inchangée au pixel
  près — 0.00 au banc). Le galbe canal pour tout le monde était le
  défaut n°1 du rendu ardoise: matière juste, géométrie fausse
- Référence `finitions_ardoise` rebasée (le toit change réellement)
- Reste (S5 partie 2): tuiles COUPÉES aux arêtiers/noues (rangées de
  bord bisectées en objets réels) et rives plates pour l'ardoise

## v1.18.0 — Toit par SQUELETTE DROIT + plan 2D unifié (S2 + S1 noyau)

Le toit n'est plus codé cas par cas: il est DÉDUIT du plan.

- **`skeleton.py`** — squelette droit rectiligne EXACT (pur Python):
  surface = min des distances L∞ aux segments, pans = régions du plan
  de support (attribution PLANAIRE — l'attribution au segment le plus
  proche créait des cônes bombés aux coins rentrants, vu au rendu);
  décomposition en pièces convexes (grille + médianes entre murs
  parallèles + diagonales x±y). Prouvé sur carré/rect/L/T/U:
  couverture au µm², planéité par sommet, surface exacte, faîtage du
  rectangle — 11 tests purs
- **`plan2d.py`** — union maison+ailes+garage → UN contour CCW propre
  (frontières orientées, chaînage, colinéaires fondus; non-connexe
  refusé) — 8 tests purs; chaîne plan2d→skeleton prouvée
- **`roof_skeleton.py` + roof_type 'SKELETON' ("Auto (squelette)")**:
  croupe construite depuis les pans sur N'IMPORTE QUELLE emprise —
  dalles prismatiques par pièce, FAÎTIÈRES sur les arcs horizontaux,
  ARÊTIERS (coins convexes), NOUES zinc (coins rentrants), fascias et
  gouttières sur TOUS les égouts, tuiles par pan (grille bornée à
  l'étendue du pan — l'éventail des coins dépassait l'égout)
- **Ailes NATIVES**: sous SKELETON l'aile n'a ni toit propre ni pignon
  maçonné (il transperçait la croupe — vu au rendu de contrôle et
  corrigé); le L/T/U est le même algorithme que le rectangle
- Invariant décisif: grille zénithale sur l'emprise UNIFIÉE en L →
  100% toit (73 invariants); banc: +1 config roof_skeleton_L (29)
- Périmètre v1: plain-pied même arase (ailes plus basses → moteur
  historique), cheminée/velux sur squelette à venir

## v1.17.0 — Spec d'ouverture UNIFIÉE, pilotée par les pièces (S4)

Quatre implémentations parallèles des ouvertures (trous briques,
cutters Boolean, menuiseries, volets) → UNE SEULE (`openings.py`).

- **`openings.compute()`**: LA liste des ouvertures (coin bas, dims,
  mur, type, centre, étage), géométrie strictement identique au
  producteur historique (murs briques 5/5, murs simples 2/2 au pixel
  près avant la partie pièces)
- Les Booleans des murs simples et les menuiseries/volets CONSOMMENT
  la même liste — les boucles dupliquées (et leurs skips porte/aile/
  balcon recopiés) sont mortes
- **Deux incohérences latentes corrigées par l'unification**: le seuil
  d'exclusion des fenêtres derrière le balcon divergeait entre trous
  et menuiseries; la porte-fenêtre du balcon n'était jamais DÉCOUPÉE
  dans les murs simples (mur plein derrière la menuiserie)
- **✅ "Pilotée par les pièces"**: en mode PROGRAMME, chaque cellule
  arrière (chambres, SdB, WC) reçoit SA fenêtre au centre de la
  cellule — la façade découle du plan (fini la chambre sans fenêtre
  de l'espacement uniforme); invariant dédié (fenêtre dans sa cellule
  ±5cm), référence programme_3ch rebasée
- 54 invariants au total

## v1.16.0 — Fondations du moteur: normes, niveaux, graines, maillage
## (chantiers structurels S8 + S3 + S6 + S7)

Première tranche de la refonte "outil d'architecture" (S1-S8): les
quatre chantiers de FONDATION, sous les deux filets.

- **S8 — `norms.py`**: les dimensions du bâtiment sont des constantes
  NOMMÉES et SOURCÉES (Blondel pour l'escalier, DTU 20.1 appuis,
  DTU 40.2x couverture, passages 0.93×2.04…) — plus de nombres magiques
  éparpillés; prouvé au pixel près (28/28 MAE=0.00 avant rebase)
- **S3 — `levels.py`**: MODÈLE DE NIVEAUX unique (soubassement, dalles,
  allèges, arase, égout, faîtage). L'objet `Levels` est construit par
  l'étape walls (arase réelle briques) et exposé au pipeline; formules
  canoniques `plinth_visible`/`window_vertical` migrées, opérateur en
  simple délégation
- **S6 — graines DÉRIVÉES** (`norms.derive_seed`, FNV-1a stable):
  tuiles, lucarnes, ailes, herbe dérivent leur graine de random_seed +
  leur nom. Reproductible à l'identique (prouvé au bit près sur les
  rotations de tuiles) mais deux maisons de graines différentes ne
  sont PLUS JUMELLES (avant: mêmes seeds 42/4242/777 pour tout le
  monde). Références du banc rebasées (micro-jitters, MAE ≤ 1.0)
- **S7 — maillage PROPRE**:
  - dormants de fenêtres = ANNEAUX prismatiques manifold (16 sommets)
    au lieu de 4 boîtes fusionnées → plus AUCUNE arête en T (>2 faces)
  - dalles trouées (trémie) = anneaux manifold également
  - **UVs systématiques** (projection boîte, 1 UV = 1 m) sur tous les
    créateurs de mesh — prêt pour les textures image PBR
  - PHOTO: normales PONDÉRÉES après le Bevel (keep_sharp)
- **Tests**: +5 (graines: stabilité/reproductibilité/non-jumelles;
  maillage: manifold + UVs) → **53 invariants**
- Prochaines tranches: S4 (spec d'ouverture unifiée), S1 (plan 2D
  extrudé), S2 (squelette droit), S5 (tuiles coupées)

## v1.15.1 — Conformité des accessoires de couverture

- Les FAÎTIÈRES, tuiles de rive et arêtiers suivent désormais la
  finition de couverture (`_tile_accessory_material`) — des faîtières
  terre cuite restaient sur un toit ARDOISE/BÉTON (vu sur le rendu de
  contrôle); référence `finitions_ardoise` régénérée

## v1.15.0 — Slots d'assets + finitions procédurales (chantier n°7)

Des SLOTS optionnels — jamais obligatoires: le procédural reste le
socle, l'asset est un habillage AU CHOIX. Slot vide ou défaillant →
House construit sa version procédurale comme toujours.

- **4 slots d'assets** (panneau "Assets & finitions"):
  - `window_asset`: l'objet remplace chaque fenêtre, mis à l'échelle
    exacte de l'ouverture (bbox), orienté par mur
  - `door_asset`: idem pour les portes (ancre = coin bas)
  - `shutter_asset`: chaque battant devient une copie normalisée
    (charnière à l'origine) — l'articulation `fermeture` et le
    micro-désordre PHOTO sont CONSERVÉS
  - `tile_asset`: le mesh devient la tuile maître, normalisé au
    calepin (TILE_W × TILE_L) et instancié sur toute la couverture
    (maison, ailes, toitons) — ses matériaux sont conservés
- **Garde-fous**: un objet généré par House est refusé (il serait
  détruit à la régénération — poll UI + re-vérification au build);
  asset plat/vide → repli procédural loggé, jamais de crash
- **Finitions procédurales au choix** (en plus de la couleur unie et
  des textures PBR existantes):
  - murs: AUTO/taloché fin, CRÉPI PROJETÉ gros grain, PEINTURE LISSE
  - couverture: AUTO/terre cuite, ARDOISE (satinée, feuilletage),
    BÉTON (gris mat) — `look.wall_material` / `tile_material(finish)`
- **Tests** (`test_assets.py`, 5): slots remplis → assets à l'échelle
  (bbox vérifiée), slots vides → procédural, objet House refusé,
  matières réellement changées (nœuds inspectés), repli sur asset plat
- Banc visuel: +1 config `finitions_ardoise` (28 au total)

## v1.14.0 — Mode PROGRAMME (chantier n°6)

"3 chambres, salle de bain, WC, garage" → House résout. L'utilisateur
décrit le BESOIN, le solveur calcule l'emprise, la distribution et les
options, puis génère.

- **`programme.py`** — solveur en Python PUR (testable sans Blender):
  surfaces normatives françaises (chambre ~11 m², séjour+cuisine
  30 + 4×chambres m², SdB 5 m², WC 1.4 m²), scan de la profondeur
  (6.8-8.4 m, portée de toit saine) → façade et cellules de la bande
  arrière; petits programmes élargis jusqu'à la façade minimale
- **Distribution RÉELLE**: les largeurs résolues (chambres, SdB, WC)
  sont transmises à `interior_layout` via `programme_cells` — les
  cloisons et les portes suivent le programme, plus le découpage
  uniforme; désactivable (`programme_active`)
- **Panneau "Programme (plain-pied)"**: chambres (1-4), SdB (1-2),
  WC séparé, garage simple/double, surface cible optionnelle, bouton
  "Résoudre le programme"; rapport m² par pièce en console + résumé
- Le programme pose aussi les options d'un pavillon cohérent:
  GABLE 40° TUILES, volets, gouttières, cheminée, fenêtres par pièce
  (1 par cellule arrière, séjour en façade) — fini le piège de la
  couverture 'Lisse' par défaut dans ce mode
- **Preuves** (`test_programme.py`, 21 tests): bornes constructives et
  minima légaux pour tout programme (paramétré ×16), déterminisme,
  surface cible, et raycast transversal dans la maison GÉNÉRÉE — les
  cloisons existent au droit des cellules résolues
- Banc visuel: +1 config `programme_3ch` (27 au total)
- Périmètre v1: plain-pied (la typologie pavillon/longère); étage,
  couloir et pièces d'eau équipées = chantiers suivants

## v1.13.0 — Proxy viewport + régénération incrémentale (chantier n°5)

Les tags posés par le pipeline (v1.11) portent leurs fruits: la "Mise à
jour auto" ne reconstruit plus TOUTE la maison à chaque réglage.

- **Régénération INCRÉMENTALE**: chaque objet est estampillé par
  l'étape qui l'a créé (`house_step`); le callback de mise à jour
  diffe les props contre le dernier build → domaines invalidés
  (`PROP_TAGS`) → seules les étapes de ces domaines sont rejouées
  (leurs objets supprimés/recréés, l'état inter-étapes est restauré
  depuis `pipeline.LAST_STATE` au lieu d'être recalculé)
- **Sûr par défaut**: toute propriété absente de la carte invalide
  `all` (reconstruction complète); la carte ne liste que les
  raccourcis prouvés — volets/fenêtres/porte (joinery), accessoires
  de toiture (roof), environnement (env), terrasse, intérieurs
- **Preuve d'équivalence** (`tests/invariants/test_incremental.py`,
  5 tests): build(A) puis regen incrémentale vers B == build(B)
  direct — mêmes objets, mêmes sommets, mêmes modificateurs; la
  cheminée ajoutée apparaît, les tuiles retirées disparaissent
- Mesures: maison briques GN + environnement — complet 0.31s,
  volets 0.05s, toit 0.03s, intérieurs 0.02s (6-15×)
- **Proxy viewport** (case à côté de "Mise à jour auto"): suspend les
  instanciations GN lourdes (tuiles, ~50k touffes d'herbe) dans la
  vue 3D seulement — le rendu F12 reste complet, la silhouette reste
  lisible (dalles et sol visibles); ré-appliqué après chaque regen
- `materials`/`photo_finish` sont toujours rejouées en incrémental
  (peu coûteuses; la géométrie recréée doit être repeinte)

## v1.12.0 — Niveau de détail Brouillon / Normal / Photo (chantier n°4)

Nouvelle propriété `detail_level` (panneau principal, "Détail") — trois
contrats explicites au lieu d'un unique niveau implicite. NORMAL reste
**au pixel près** le comportement historique (26 configs du banc dont
24 anciennes à MAE=0.00, 17/17 invariants).

- **BROUILLON** (itérer sur les volumes, régénération rapide): sans
  charpente, sans voilages, volets en plaque simple (1 planche au lieu
  de 4 lames + barres), sans végétation d'environnement (ni arbres ni
  herbe GN — sol/allées/ciel conservés)
- **PHOTO** (le rendu final): tous les "tells" photo identifiés sur la
  longère de référence, productisés:
  - **appuis de fenêtre BÉTON débordants** (`Window_Sill_Photo`): nez à
    5cm du nu du mur, pente de rejet d'eau — l'ombre horizontale sous
    chaque fenêtre qui manquait (l'appui du dormant restait noyé dans
    l'épaisseur du mur)
  - **doublis d'égout**: rang de tuiles supplémentaire en pied de
    versant (pose réelle) avec micro-jitter déterministe
  - **volets ENTROUVERTS** à angles variés (hash déterministe par
    battant, `fermeture` 0.015–0.065) — plus de façade aux volets
    parfaitement plaqués
  - **chanfreins d'arêtes** (modificateur Bevel 7mm/2 segments, limite
    d'angle 50°) sur fascias, rives, souche, couronnement, fondations,
    gouttières, lucarnes, balcon — les arêtes parfaitement vives sont
    le tell CG n°1
- **Pipeline**: nouvelle étape `photo_finish` (cond PHOTO, tag
  materials) validée statiquement; fenêtres: portes de détail lues
  depuis la scène (`_detail_level`)
- **Banc visuel**: +2 configs `detail_draft` / `detail_photo` (26 au
  total), références générées

## v1.11.0 — Pipeline de construction déclaratif (chantier qualité n°3)

La chirurgie structurelle, opérée SOUS les deux filets (banc visuel +
invariants) et prouvée sans effet de bord: 24/24 configs au pixel près
(MAE=0.00) et 17/17 invariants après refonte.

- **`pipeline.py`**: la construction est une liste d'ÉTAPES déclaratives
  (21) — chacune déclare ses dépendances (`requires`), ses garanties
  (`provides`), sa condition et son domaine (`tags`)
- **Validation STATIQUE à l'import**: un ordre d'étapes invalide casse
  le chargement du module en nommant l'étape fautive — la famille de
  bugs "ordre implicite" (matériaux écrasés, ailes initialisées trop
  tard, real_wall_height périmé) devient impossible silencieusement
- **Contrats vérifiés à l'exécution**: requires présents avant, provides
  présents après, erreur nominative sinon; test négatif validé
- **`execute()` réduit au driver** (30 lignes au lieu de ~150 de
  séquence implicite); chrono par étape via HOUSE_PIPELINE_PROFILE=1
- Les `tags` par étape posent la base de la RÉGÉNÉRATION INCRÉMENTALE
  (chantier n°5): invalider un domaine → rejouer ses seules étapes

## v1.10.1 — Invariants géométriques pytest (chantier qualité n°2)

- **`tests/invariants/test_geometry.py`** (17 tests, ~4s): façades
  SOLIDES hors ouvertures par raycasts (maison + garage — le bug du
  Boolean serait attrapé), TOIT ÉTANCHE vu du ciel (grille de rayons
  zénithaux: seul du "toit" peut être touché), fenêtres ANCRÉES à un
  plan de mur, tuiles posées SUR leur dalle (< 2% hors plan), escalier
  qui ATTEINT l'étage (±8cm), TRÉMIE réellement percée (rayon
  traversant), volets sans CHEVAUCHEMENT, rien sous les fondations —
  chaque invariant vient d'un bug réel de l'historique
- **Première prise dès le premier run**: les battants ouverts de deux
  fenêtres proches se chevauchaient sur les murs latéraux → chaque
  battant est désormais clampé à la moitié de l'espace libre vers sa
  voisine (`_leaf_room`), références du banc visuel rebasées

## v1.10.0 — BANC DE NON-RÉGRESSION VISUEL (chantier qualité n°1)

Le filet de sécurité qui manquait: les pires bugs de l'historique
(matériau par-tuile débranché, Boolean avalant la façade du garage,
doublons masquant les V2) rendaient `FINISHED` avec une image fausse.

- **`tests/visual/bench.py`**: 24 configurations golden-image couvrant
  chaque chemin de code visible (5 toits, 2 moteurs briques, 3 modes
  matériaux, murs enduit+Boolean, ailes L/U/croupe/mansarde, garage
  briques ET enduit, velux/lucarnes, étages+balcon, 2 vues intérieures,
  environnement complet, preset régional)
- **Invariants par config**: opérateur FINISHED + objets clés présents
  (le bug du garage aurait été attrapé) — a d'ailleurs immédiatement
  attrapé une erreur d'invariant dans sa propre config garage_bricks
- **Déterminisme prouvé**: double-run 24/24 PASS à MAE=0.00 (Cycles
  CPU seed fixe = pixels identiques) — seuils MAE≤2.0 / ≤1.5% px
- **Test négatif validé**: matériau volontairement cassé → FAIL net
  (MAE 10.4, 16% de pixels)
- **Rapport HTML** (référence | actuel | diff ×8), CLI `--update`,
  `--only`, `--fast`, exit code CI; références committées (~1.5 Mo);
  bonnes pratiques documentées dans `tests/visual/README.md`

## v1.9.1 — La MAISON photoréaliste (réponse au comparatif photo réelle)

**Diagnostiqué sur photo de pavillon réel fournie par l'utilisateur.**

### Les tells "fake" corrigés sur la maison elle-même
- **ENDUIT TALOCHÉ réel** (`look.stucco_material`) pour les murs
  simples: grain fin serré, nuages de teinte à l'échelle du mur,
  pied de mur sali — l'aplat lisse faisait maquette. Appliqué maison
  + ailes + garage
- **Le matériau PAR TUILE était débranché** depuis la v1.3 (le master
  utilisait un aplat orange!) → rebranché + PATINE de versant grande
  échelle (position monde) — fini le toit orange uniforme
- **Briques**: contraste par-brique divisé par 2 + patine murale
  grande échelle (zones d'humidité 3-8m) — fini le damier de pixels
- **VOILAGES blancs ondulés** derrière chaque vitre (voile diffus/
  translucide) — le verre-miroir-noir devient une fenêtre habitée
- **Volets à LAMES** (4 planches + 2 barres) avec COULEUR AU CHOIX
  (`shutter_color`) — la plaque pastel faisait jouet
- **Porte d'entrée en bois veiné** (chêne) au lieu de l'aplat beige
- **Gouttières fines** (Ø 25/33 réel) en alu laqué sable
- **Ombres douces** (disque solaire Nishita 1.6°) + palette briques
  resserrée

### Environnement (secondaire, mais rendu propre)
- Caméra à HAUTEUR D'ŒIL (1.65m) + 40mm + profondeur de champ
- Pelouse en VRAIES touffes d'herbe instanciées (52k, GN, hors allées)
- Arbres multi-lobes en arrière-plan, haie bosselée avec portail

## v1.9.0 — Distribution paramétrable, quincaillerie, parcelle

### 🛏️ DISTRIBUTION INTÉRIEURE PARAMÉTRABLE
- Nouveau réglage **Chambres (1-4)**: N-1 refends longitudinaux derrière
  le refend principal, chacun avec sa PORTE battante posée; nombre
  auto-réduit si la façade est courte (chambre mini 2.6m), cloisons
  décalées hors des fenêtres

### 🔧 QUINCAILLERIE des fenêtres battantes
- Poignée + béquille et tringle de CRÉMONE sur l'ouvrant (côté opposé
  aux gonds) — elles pivotent avec le battant

### 🌳 PARCELLE
- HAIE périphérique avec portail aligné sur l'allée d'entrée
  (option Environnement)

## v1.8.0 — Lucarnes jacobines, presets régionaux, export glTF

### 🏠 LUCARNES JACOBINES (style de fenêtre de toit au choix)
- Nouveau style `Lucarne jacobine` (toits GABLE): façade verticale
  maçonnée avec FENÊTRE battante, jouées triangulaires, toiton à
  2 pans **coupé exactement au plan du toit principal** (bisect),
  tuiles du toiton ajustées et faîtière arrêtée au point de
  pénétration analytique; tuiles principales exclues au calepinage
  (zone resserrée: le toiton recouvre sa propre pénétration)

### 🗺️ PRESETS RÉGIONAUX (silhouettes complètes en un clic)
- **Longère** (volume long et bas, GABLE 45°, 3 lucarnes, briques brunes)
- **Chalet** (2 niveaux, débords 1m, balcon + porte-fenêtre)
- **Bastide** (croupe provençale 22°, enduit clair, terrasse, volets)
- **Meulière** (étage + mansarde, briques rouges)
- Sélecteur + bouton dans le panneau principal; chaque preset règle
  dimensions, toit, matériaux et options puis regénère

### Divers
- Portes intérieures déjà posées à CHAQUE étage (portes palières via
  les refends) — complété par le garde-corps de trémie v1.7

## v1.7.0 — Les 8 problèmes connus réglés + ② Environnement de rendu

**Le grand nettoyage du ROADMAP, un par un, validé au rendu.**

### Problèmes réglés (les 8 de l'état des lieux)
- **P1 — Ailes sur croupe et mansarde**: noues exactes sur le pan
  trapézoïdal d'une croupe (emprise contrôlée entre les arêtiers),
  appentis sous les pignons d'une mansarde (profil W respecté, pente
  auto-réduite)
- **P2 — Velux sur croupe et mansarde**: calepinage clampé entre les
  arêtiers (trapèze) / posé sur le terrasson, tuiles exclues
- **P3 — Garage-aile**: le garage est désormais un VRAI volume maçonné
  (briques coupées, linteau, toiture raccordée, gouttières) avec sa
  porte sectionnelle articulée — fini le cube enduit
- **P4 — Gouttières/chevrons/fascias DÉCOUPÉS autour des ailes**
  (plus de tronçons cachés dans les combles)
- **P5 — Plafonds CATHÉDRALE**: le dernier étage suit la sous-face du
  toit en monopente et en mansarde (profil piecewise)
- **P6 — Escalier**: GARDE-CORPS DE TRÉMIE à l'arrivée; VOLÉE EN L
  (quart tournant à palier) quand la volée droite ne rentre pas
- **P7 — Coulissante et guillotine ARTICULÉES**: vantail mobile séparé
  avec vitre intégrée, driver 'ouverture' (translation)
- **P8 — PORTE-FENÊTRE française** posée automatiquement derrière le
  balcon (ouverture maçonnée + battants articulés)

### ② ENVIRONNEMENT DE RENDU (nouvelle option)
- Terrain gazonné, allées béton vers l'entrée ET le garage, arbres,
  **ciel physique Nishita** + AgX avec **exposition photo** (-4.6 stops
  — le bug historique du monde noir venait d'un lien Background→Output
  manquant), **caméra cadrée automatiquement** sur l'emprise bâtie

### Divers
- Export **glTF (.glb)** de la maison (bouton dédié)

## v1.6.0 — Les 5 toits finis SÉRIEUSEMENT + état des lieux (ROADMAP.md)

**Matrice des 5 types rendue et vérifiée.**

### Finitions réelles par type (nouveau `_carpentry_other_roofs`)
- **Monopente**: chevrons apparents sous l'égout bas, fascia d'égout,
  BANDEAU de tête, planches de rive le long des rampants; **gouttière
  UNIQUEMENT à l'égout bas** (l'eau ne remonte pas!) ; velux supportés
- **Croupe (HIP)**: fascia PÉRIPHÉRIQUE sur les 4 égouts + chevrons
  sur les 4 côtés (à l'écart des arêtiers)
- **Mansarde**: fascias d'égout + planches de rive des pignons en
  2 segments (brisis puis terrasson) suivant le profil en W
- **Toit plat**: COUVERTINE zinc sur l'acrotère (géométrie exacte du
  muret) + MEMBRANE bitume sur la dalle

### Cheminée EXACTE par type de toit
- Avant: maths GABLE appliquées partout. Désormais: position clampée
  sur la partie trapézoïdale du HIP (elle pouvait tomber sur le pan
  triangulaire!), hauteur de toit et angle de SOLIN exacts par type
  (profil piecewise mansarde, pente monopente, au-dessus de l'acrotère
  en toit plat)

### Divers
- Velux étendus à la monopente (calepinage partagé, tuiles exclues)
- **ROADMAP.md**: état des lieux honnête — problèmes connus classés
  par gravité + améliorations possibles court/moyen/long terme

## v1.5.0 — Toits complets, plans T/U, escalier, doublage, velux, bibliothèque d'assets

**Chaque bloc validé au rendu Cycles headless.**

### ① Toits HIP et MANSARDE enfin complets
- **HIP**: tuiles sur les 4 pans avec coupes d'ARÊTIERS exactes (45° en
  plan, pentes égales), arêtiers + faîtière demi-ronds, gouttières
  périphériques (déjà en place) — plus de dalle nue
- **MANSARDE (gambrel)**: tuiles sur les 4 surfaces (2 brisis 68° +
  2 terrassons), FAÎTIÈRE + MEMBRONS aux cassures, et surtout **pignons
  MAÇONNÉS suivant le profil en W** (briques coupées le long des deux
  rampants) — fini la maison ouverte aux pignons; pignons fermés aussi
  en mode murs simples
- Bug corrigé au passage: le `else` de la couverture GABLE attrapait
  HIP/GAMBREL et superposait un champ de tuiles fantôme

### ③ Ailes à ÉTAGES + SECONDE AILE (plans en T et U)
- `wing_floors` / `wing2_floors`: aile de 1 à 3 étages (clampée aux
  étages de la maison — noues seulement à égouts alignés, sinon
  appentis, règle affichée)
- **Seconde aile** avec ses propres côté/dimensions/position →
  plans en T et en U; contrôle de NON-CHEVAUCHEMENT des emprises
- Fenêtres de l'aile PAR ÉTAGE, plafonds/sols de l'aile par étage

### ④ ESCALIER automatique + PORTES INTÉRIEURES
- Dès 2 étages: volée droite (giron 25cm, hauteur ≈ 17-18cm) le long du
  refend, **TRÉMIE découpée dans les dalles ET les plafonds**, position
  du passage de porte déplacée automatiquement hors de la volée
- **Styles intelligents**: BOIS (marches à nez + contremarches + limons
  + garde-corps bois) en Traditionnel/Méditerranéen; **BÉTON + garde-corps
  métal fin** en Moderne/Contemporain/Asiatique
- **Portes intérieures** posées dans les passages des cloisons à chaque
  étage (battants articulés)

### ⑤ DOUBLAGE INTÉRIEUR PEINT
- Panneaux plâtre (3.5cm) côté intérieur des murs extérieurs ET des
  ailes, **réservations exactes** aux fenêtres/portes/passages (liste
  d'ouvertures partagée avec la maçonnerie), couleur au choix
  (`Peinture murs`) — fini la brique apparente involontaire; les
  tableaux de fenêtres restent en brique (retour naturel)

### ⑥ FENÊTRES DE TOIT (velux)
- Option `Fenêtres de toit` (1-4) sur le pan visible des toits GABLE:
  cadre + vitrage + solin zinc périphérique, **tuiles exclues de
  l'emprise** par calepinage partagé (aucun chevauchement)

### ⑦ BIBLIOTHÈQUE D'ASSETS
- Bouton **« Exporter la bibliothèque d'assets (.blend) »**: marque les
  menuiseries puis écrit un .blend de bibliothèque (dépendances
  incluses) prêt à brancher dans Préférences > Asset Libraries

## v1.4.1 — Peinture/PBR validés, cheminée V2, Asset Browser

### 🎨 Finitions de façade au choix (validé au rendu)
- Mode **COLOR** (brique peinte de la couleur choisie) et mode **PBR**
  (déposez un dossier de textures dans `materials/textures/<nom>/` —
  basecolor/normal/roughness détectés automatiquement, le preset
  apparaît dans la liste) vérifiés par rendus Cycles
- Set d'exemple `brique_peinte` fourni (brique peinte blanche)

### 🏭 Cheminée V2 (elle n'était pas au niveau)
- Fût en VRAIES briques (Brick Texture procédural à l'échelle réelle
  22×6.5cm, joints creusés), **solin zinc** incliné au passage du toit,
  **couronnement béton** débordant avec goutte d'eau, **2 boisseaux**
  terre cuite — toujours activable/désactivable (option Cheminée)

### 📚 Asset Browser
- Nouveau bouton **« Menuiseries → Asset Browser »**: marque portes,
  fenêtres, volets, porte de garage et tuile maître comme assets
  Blender (tags, auteur, aperçus) — réutilisables par glisser-déposer
  après enregistrement du .blend dans une bibliothèque d'assets

## v1.4.0 — Multi-volumes (plans en L), intérieurs, conformité

**Validé au rendu Cycles headless.**

### 🏘️ MULTI-VOLUMES: aile en L (nouveau module `volumes.py`)
- Nouvelle option **Aile** (côté AVANT/ARRIÈRE/GAUCHE/DROITE, largeur,
  profondeur, position le long de la façade)
- Murs de l'aile calculés dans son repère local par le MÊME moteur que
  la maison (pignon maçonné, briques coupées, linteaux soldats) puis
  transformés et **fusionnés dans le même nuage Geometry Nodes** —
  un seul objet murs pour tout le plan en L
- Toit GABLE de l'aile raccordé au toit principal par des **NOUES
  EXACTES**: pentes égales → plans de coupe verticaux à 45° passant par
  les coins du mur mitoyen (`bisect_plane`), tuiles ajustées à la noue,
  **bandes de noue en zinc** couvrant la coupe
- Cas appentis-pignon: accroche sur un mur pignon ou maison à étages →
  toit terminé au nu du mur, pente réduite automatiquement si nécessaire
  (règle de construction affichée en console)
- **Passage** percé dans le mur mitoyen (linteau + briques coupées)
- Fenêtres de la façade masquées par l'aile SUPPRIMÉES, porte d'entrée
  **déplacée automatiquement** dans le plus grand segment libre
- Aile complète: fondations alignées, plancher, faîtière, planches de
  rive, tuiles de rive, gouttières + descentes, volets, mode murs
  simples également supporté
- Contrainte assumée (affichée): aile de plain-pied, pente du toit
  principal, toit principal GABLE

### 🛋️ INTÉRIEURS (nouveau module `interiors.py`, option activée par défaut)
- **Plafonds en plâtre** par étage et par volume (fini la vue directe
  sur le dessous de la dalle en regardant par les fenêtres)
- **Cloisons de distribution** avec passages de porte 0.93×2.04m:
  refend transversal (pièce de vie / chambres) + refend longitudinal,
  positions ajustées automatiquement HORS des fenêtres et alignées sur
  la circulation de l'entrée
- **Sols parquet** posés sur les dalles, matériaux plâtre/parquet V2

### ⑤ Conformité des options (matrice de rendus Cycles, 15 configurations)
- Chaque valeur d'option rendue et vérifiée: 5 types de toits, 6 types
  de fenêtres, 4 types de portes, murs simples/briques, appareillages,
  2 étages + balcon — toutes génèrent ce qu'elles promettent
- **Bug majeur découvert**: `features.py` contenait des sections
  DUPLIQUÉES (tuiles + volets) — la seconde copie (ancienne, volets
  fixes V1, rotations de tuiles fausses) MASQUAIT silencieusement les
  versions V2. Doublons supprimés: volets articulés et tuiles V2
  réellement actifs
- **Tuiles monopente/faîtage court**: inclinaison de pose PHYSIQUE
  (le nez repose sur la rangée du dessous, δ=atan(épaisseur/pas)) au
  lieu du décalage cumulatif qui faisait flotter les tuiles jusqu'à
  16cm au sommet des longues pentes
- **Rampants monopente**: briques coupées le long de la pente (même
  principe que les pignons — fini l'escalier à trous sous la dalle)
- Limites documentées (messages console): tuiles et gouttières sur
  GABLE/monopente, charpente visible sur GABLE

### 🧱 Défauts de rendu corrigés (les 3 signalés + trouvés en route)
- **Mortier enfin lisible**: la brique déborde de 4mm du lit de mortier
  (avant: affleurement → joints invisibles en façade)
- **Palettes recalibrées pour AgX**: BRICK_RED/BRICK_ORANGE et tuiles
  en valeurs linéaires basses et saturées (avant: rose pastel délavé)
- **Chevrons recalculés** (maths exactes): face supérieure collée au
  dessous de la dalle, rotation par pan, entrée dans le mur — finis les
  chevrons flottants
- **Briques de RIVE des pignons coupées en biais** le long du rampant
  (fini l'escalier) + **planches de rive de pignon** (bargeboards) qui
  ferment le jeu dalle/maçonnerie comme en vrai
- **Tuiles des pans montant en ±X réorientées** (SHED, faîtage court,
  pans de l'aile): la longueur de tuile monte la pente, le galbe en
  travers — avant, les tuiles étaient couchées en travers et noyées
  dans la dalle
- **Z-fighting éliminé**: coins des cadres de fenêtres (traverses à
  coupe droite entre jambages), angles du garage (murs sans
  recouvrement), volets de fenêtres proches (espacement aux quarts sur
  le pignon de l'aile)

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
