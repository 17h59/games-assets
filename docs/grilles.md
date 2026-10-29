# Grilles, xycut et taches

[← Sommaire](README.md) · code : `tools/spritekit/grid.py` · paramètres : [Grille](parametres.md)

Découper par cases règle d'un coup les sprites collés (séparés par la frontière), les morceaux détachés
(ombre, arme : rattachés) et l'alignement des frames. `layout=auto` choisit, **bloc par bloc** :

1. **Blocs** : groupes de sprites séparés par plus de `block_gap` px de vide (une feuille peut avoir
   plusieurs grilles de pas différents).
2. **Grille régulière** (`fit_block`) : profil d'occupation des colonnes / lignes ; pas = autocorrélation
   (on préfère un vrai sous-multiple, k ≥ 2, du meilleur pas) ; phase = frontières qui traversent le moins de
   pixels ; confiance = 1 − densité sur les frontières / densité moyenne. Acceptée si confiance ≥
   `grid_min_conf` et ≥ `grid_min_sprites` sprites. Mode « grille » : cases fixes, indices rangée/colonne.
3. Sinon **xycut** (`fit_xycut`) — feuilles régulières mais assemblées à la main (le pas dérive de 1-2 px,
   sous-grilles décalées) : découpage XY récursif sur les lignes/colonnes entièrement vides, puis sprites
   trop larges/hauts (≥ 1,6x la taille médiane) coupés au point le moins dense, et fragments (< 45 % de la
   taille médiane, à ≤ `frag_gap` px) rattachés au voisin. Accepté si les tailles sont régulières.
4. Sinon **taches** : un sprite = une composante.

Le rapport indique la `disposition` de chaque bloc ([QA](qa.md)).

**Grille imposée** (`grid_pitch=LxH`, éventuellement `grid_origin=x,y`) : pas plus deviné ; appliquée même à
un bloc entièrement soudé (sprites collés au pixel près). Pas d'anomalie `grid_cuts` dans ce cas (les
frontières coupent forcément des pixels) : vérifier à l'œil. S'utilise surtout dans une [zone](zones.md).

Pourquoi xycut et pas une grille souple par gouttières : calculer les rangées sur toute la largeur d'un bloc
mélangeait des sous-grilles décalées (un enfant de 13 px fusionné avec une fille en dessous, feuille PNJ
d'Émeraude) ; le XY-cut récursif sépare naturellement les sous-grilles.
