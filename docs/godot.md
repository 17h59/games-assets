# Godot

[← Sommaire](README.md) · voir aussi [Terrains PMD](terrains-pmd.md), [Objets des cartes](objets-cartes.md)

Godot 4.7.2 (`/usr/bin/godot`). Projet : `rpg/project.godot` (créé le 2026-10-29).

## Réglages
Écran GBA 240x160, fenêtre 960x640, `stretch/mode=viewport`, mise à l'échelle entière, filtrage `nearest`.
`rpg/_raw/` et `rpg/pipeline/` ont un `.gdignore` (Godot ne les importe pas).

## Chaîne de génération (2 étapes, refaire après chaque changement d'assets)
1. `tools/sk godot` → `rpg/godot/catalog.json` (code : `tools/spritekit/godot.py`) : tout est résolu côté
   Python (chemins `res://`, cases, animations, voisins des terrains) ; chaque entrée garde sa `validation`
   (verified / auto / pending).
2. `godot --headless --path rpg --import` (1re fois ou nouveaux PNG : ~5 min pour 13 000 PNG), puis
   `godot --headless --path rpg --script res://godot/tools/build_resources.gd` (< 1 s) :
   - `res://godot/sprite_frames/<jeu>/<feuille>/<entité>.tres` : `SpriteFrames` (1 884) ; gabarit Pokémon →
     animations `idle_down/up/left`, `walk_down/up/left` (la droite = gauche + `flip_h`) ; sinon `default` ;
   - `res://godot/tilesets/pmd/<donjon>.tres` : `TileSet` 24 px, 1 jeu de terrains (walls 0, ground 1,
     water 2, mode coins + côtés) ; variantes « alt » = mêmes terrains, probabilité 0,15 ; les reflets
     (`water_sparkle`) ne sont pas des terrains (calque à part) ;
   - `res://godot/tilesets/<jeu>.tres` : TileSet de la bibliothèque de tuiles du jeu (une source par page
     d'atlas, identifiant de source = n° de page) ;
   - `res://godot/tilesets/terrains_<jeu>.tres` (Émeraude, Rubis/Saphir) : **bords de terrains Pokémon**
     vérifiés (pages `tp_<jeu>_NN` toutes `ok`) : 1 jeu de terrains (coins + côtés, Émeraude 41 terrains /
     268 tuiles, Rubis-Saphir 44 / 719) ; tuiles pures = terrain sur les 8 voisins avec probabilité ∝ fréquence
     dans les cartes ; transitions gardées = voisins mixtes. Démo : `res://godot/demo/bords_<jeu>.tscn`
     (12 paires les plus complètes, carré de B peint dans A par `set_cells_terrain_connect`). Minish Cap :
     aucune transition détectée → pas de TileSet ;
   - `res://godot/maps/<jeu>/<carte>_r<zone>.tscn` : **723 cartes d'origine reconstruites en TileMapLayer**
     (grilles des `region_N.json`) — copier des morceaux de carte dans l'éditeur, ou les utiliser telles quelles ;
   - `res://godot/demo/demo.tscn` (Bourg-en-Vol + Brendan) et `demo_donjon.tscn` (donjon PMD peint par
     terrains) : reconstruites à chaque fois.

Si `build_resources.gd` affiche « Failed loading resource » sur des PNG qui existent : leur `.import` contient
`valid=false` (importé pendant une réécriture) → `grep -l valid=false -r rpg/assets --include=*.import | xargs rm`
puis relancer `--import`.

## Collisions
TileSet des jeux : couche physique 0, carré plein sur toute tuile qui n'est PAS du sol (liste `terrain` de
`objects.json`) : bâtiments, murs, arbres, meubles. Heuristique : l'eau est traversable, les fleurs/herbes
hautes (non-sol) bloquent. Test : `godot --headless --path rpg --script res://godot/tests/collision_test.gd`
(Brendan poussé vers le nord : collision attendue).

## Galeries
`res://godot/galeries/<jeu>_<catégorie>.tscn` (et `<jeu>_objets.tscn`) : toutes les entités animées (première
animation en boucle) ou objets d'une catégorie, en grille avec leur nom : pour parcourir les assets dans
l'éditeur (ouvrir la scène, zoomer). Les entrées gardent leur validation dans `catalog.json`.

## Démos
⚠ Toutes les scènes et ressources sous `res://godot/` (démos comprises) sont **réécrites à chaque génération** :
pour modifier une démo, la dupliquer ailleurs (ex. `res://scenes/`). Le 2026-10-29, des déplacements faits
par erreur dans l'éditeur (carte et sprite de Brendan décalés) donnaient « caméra à gauche, perso invisible ».
`demo.tscn` (`run/main_scene`) : Bourg-en-Vol reconstruit à partir des tuiles + Brendan (flèches).
`demo_donjon.tscn` : donjon « Tiny Woods » peint par `set_cells_terrain_connect` (murs, piliers, mare : bords automatiques), Brendan
(`godot/demo/player.gd`, flèches, 4 directions) et quelques objets d'Émeraude vérifiés. Capture sans fenêtre :
`godot --path rpg --write-movie /tmp/f.png --quit-after 30` (image 240x160 par frame).

## Reste à faire
- Objets : choisir les objets de la démo parmi les vérifiés et nommés ; scène par objet (Sprite2D +
  collision) si besoin.
- Bords Pokémon : exportés (voir plus haut) mais **incomplets** — la plupart des paires n'ont que quelques
  combinaisons de bords, Godot complète avec la tuile la plus proche (raccords approximatifs) ; quelques
  tuiles « pures » contiennent du décor. Bien rendu : sable/herbe, sable/prairie. Pistes : tuiles pures
  vérifiées elles aussi ; compléter les bords manquants par symétrie (miroirs) quand le jeu les utilise.
- Galerie de contrôle (toutes les animations sur une ligne de base) : test d'acceptation des SpriteFrames.
