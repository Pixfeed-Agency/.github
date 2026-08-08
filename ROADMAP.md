# État des lieux & feuille de route — House Generator

*Mis à jour pour v1.6.0 — inventaire honnête: ce qui marche, ce qui manque,
ce qu'on peut améliorer. Rien n'est caché.*

## ✅ Pris en charge sérieusement (validé au rendu Cycles)

### Toits — les 5 types finis
| Type | Tuiles | Faîtage/arêtes | Charpente visible | Gouttières | Cheminée | Velux |
|---|---|---|---|---|---|---|
| GABLE | ✅ 2 pans | faîtière + rives | chevrons + fascias + bargeboards | 2 égouts | ✅ exacte | ✅ |
| Monopente | ✅ 1 pan | — | chevrons + fascia + bandeau tête + rives | égout bas seul (physique!) | ✅ exacte | ✅ |
| Croupe (HIP) | ✅ 4 pans, coupes 45° | faîtière + 4 arêtiers | chevrons 4 côtés + fascia périphérique | périphériques | ✅ clampée sur trapèze | ⏳ |
| Mansarde | ✅ brisis+terrassons | faîtière + membrons | fascias + rives 2 segments | 2 égouts | ✅ sur terrasson | ⏳ |
| Plat | membrane bitume | — | couvertine zinc sur acrotère | drainage intérieur | ✅ au-dessus acrotère | n/a |

- Pignons MAÇONNÉS en briques coupées: triangle (GABLE), W (mansarde),
  rampant (monopente) — plus aucun escalier apparent
- Tuiles: pose physique (inclinaison δ réelle), variation par tuile,
  micro-jitter, orientation exacte par pan

### Structure
- Murs briques 3D: 1 seul objet Geometry Nodes, briques COUPÉES aux
  ouvertures/bords/rampants, linteaux soldats, 4 appareillages,
  hauteur réelle partagée partout (toit/fenêtres/dalles)
- Multi-volumes: 1-2 ailes (plans L/T/U), 1-3 étages par aile, noues
  exactes à 45°, appentis-pignon sinon, passage percé, porte déplacée
- Intérieurs: plafonds clampés sous chaperons, cloisons+portes,
  doublage peint avec réservations exactes, sols, escalier normé avec
  trémie réellement découpée, styles bois/béton selon l'architecture
- Menuiseries articulées (drivers 'ouverture'/'fermeture'), Asset
  Browser + export bibliothèque .blend

## ⚠️ Problèmes connus (assumés, par gravité)

*Mise à jour v1.7: les points 1-8 ci-dessous sont RÉGLÉS (voir
CHANGELOG). Restent les limites listées après la liste historique.*

1. **Ailes seulement sur toit principal GABLE.** Le raccord noue sur
   HIP demande l'intersection avec des plans de croupe (3 plans par
   angle) — faisable avec la même méthode bisect, non écrit. Sur
   mansarde, le raccord change de plan à la cassure (2 noues par pan).
2. **Velux absents de HIP/mansarde** (calepinage écrit pour un pan
   unique rectangulaire; les pans HIP sont trapézoïdaux).
3. **Le garage est un volume "simple"** (enduit + monopente béton),
   pas au niveau du reste. Il devrait devenir une AILE spécialisée
   (briques + vraie toiture + noue).
4. **Gouttière principale traversant l'aile**: le tronçon masqué passe
   dans le comble de l'aile (invisible de l'extérieur, mais présent).
   Idem chevrons du pan principal sous l'aile.
5. **Intérieur monopente/mansarde**: le plafond du dernier étage est
   plat sous le chaperon — pas de plafond rampant (cathédrale) suivant
   la sous-face, alors que c'est l'intérêt d'une mansarde.
6. **Escalier**: volée droite uniquement (pas de quart tournant pour
   les maisons étroites — il est alors simplement omis, message en
   console). Pas de porte palière à l'étage.
7. **HIP à pente très faible + débord fort**: les chevrons d'angle
   approchent les arêtiers (marge 0.55m, pas de coupe d'about).
8. **Fenêtres ARCHED/PICTURE/SLIDING/DOUBLE_HUNG non articulées**
   (fixes — seule CASEMENT s'ouvre vraiment).
9. **Balcon**: dalle+rambarde béton simple, pas de porte-fenêtre
   automatique derrière.
10. **Booleans murs simples**: solver EXACT fiable mais lent sur les
    grandes maisons multi-étages.

## 🔭 Améliorations possibles (par chantier)

### Court terme (mécanique existante à étendre)
- ✅ v1.7: velux HIP/mansarde, ailes sur HIP, garage-aile, plafonds
  cathédrale, garde-corps de trémie, split des gouttières — FAITS
- ✅ v1.8: lucarnes JACOBINES (2 pans, coupe exacte au plan du toit)
- Lucarne capucine (3 pans) — à venir
- ✅ v1.8: portes à chaque étage sur les refends (palières)

### Moyen terme (nouveaux systèmes)
- ✅ v1.7: ② environnement (terrain, allées, arbres, ciel Nishita,
  exposition photo, caméra auto) — reste: HDRI importables, herbe
  en particules, clôtures/haies
- Articulation des autres menuiseries + quincaillerie (gonds, crémones)
- Escalier quart-tournant / limon central; rampe normée
- Distribution intérieure paramétrable (nombre de chambres, cuisine,
  SdB avec équipements simples)
- Textures PBR: UV continues par mur (aujourd'hui box par brique),
  displacement optionnel
- ✅ v1.8: presets régionaux (longère, chalet, bastide, meulière)

### Long terme (structurel)
- **Import du plan 2D → maison complète** (le mode MANUAL pose des
  murs; il faudrait reconnaissance de pièces + toiture auto multi-pans
  sur contour quelconque — squelette droit / straight skeleton)
- Toiture sur EMPRISE QUELCONQUE (L/T/U natifs par squelette droit au
  lieu de volumes accolés)
- Étages en retrait, combles aménagés avec plancher sous rampants
- ✅ v1.7: export glTF (.glb); reste IFC (nécessite ifcopenshell)
- LOD: masters de briques/tuiles multi-résolution pilotés par la
  distance caméra
