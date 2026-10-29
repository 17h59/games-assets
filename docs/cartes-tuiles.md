# Cartes et tilesets : grilles et bibliothèque de tuiles

[← Sommaire](README.md) · code : `tools/spritekit/tiles.py` · voir aussi [Objets des cartes](objets-cartes.md)

Fiches de type `map` (cartes complètes : Locations, Maps, Backgrounds, Gyms, Friend Areas...) et `tileset`
(Exterior/Interior Tileset, Dungeon Tiles...). Tuiles de 16 px (PMD : 24, à régler `tile=24`).

## Zones de carte (`find_regions`)
Fond retiré (`TILE_PARAMS` : bord seulement, tolérance 0, épluchage des cartouches ≥ 1024 px), puis zones
opaques assez grandes. Une zone **unie** (1 tuile unique) est ignorée (fond, cadre).

## Grille de chaque zone
1. **Unicité** (`detect_offset`) : le décalage (ox, oy) qui minimise le ratio de tuiles uniques. Tous les
   décalages comparés **sur le même nombre de tuiles** (sinon perdre une rangée de bord améliore le ratio).
   Confiance = écart à la médiane. Égalité → plus grande couverture.
2. **Référence** (`reference`, mise en cache `assets/<jeu>/tiles/reference.json`) : tuiles vues ≥ 2 fois
   dans les zones sûres (confiance ≥ 0,5, ≥ 60 tuiles), puis **bootstrap** : chaque zone douteuse qui se
   recale nettement y ajoute ses tuiles, on recommence (5 tours max). Émeraude : 1 169 → 3 516 tuiles.
3. **Recalage** (`offset_by_reference`) des zones peu sûres : on ne compte que les correspondances
   **propres à un seul décalage** (les motifs périodiques — parquet 8 px, herbe — matchent à plusieurs
   décalages et ne prouvent rien). Accepté si seul décalage avec correspondances, ou ≥ 3x le second + 2.
4. Corrections : `sk gridcheck ID zN` (4 candidats côte à côte) puis `sk region ID zN offset=ox,oy|skip`.

## Bibliothèque (`sk tiles JEU`)
Reconstruit la référence, puis : toutes les tuiles uniques (cartes : **seulement les tuiles entièrement
opaques** — le texte et les débris partiels disparaissent) → `assets/<jeu>/tiles/atlas_N.png` (64x64
tuiles par page), `library.json` (tuile → page/col/rangée, occurrences, feuilles), `adjacency.json`
(voisinages `a>b` et `avb`), et chaque zone en matrice d'indices `assets/<jeu>/maps/<feuille>_<id>/region_N.json`
(reconstructible en TileMap Godot) **+ `region_N.png`, aperçu reconstruit à partir des tuiles** (et sa
`coverage` = part des pixels reproduits). Confirmations automatiques des [étapes](etapes.md) `reconstruction`
(≥ 97 %) et `grille` (toutes zones ≥ 0,5). Le dossier `maps/` est vidé à chaque reconstruction.

**À savoir** : `maps/` ne contient pas de sprites mais des **cartes en tuiles** (JSON = « case → n° de
tuile de l'atlas ») ; les images des objets de ces cartes sont dans `objects/`.

Émeraude : 16 463 tuiles uniques depuis 29 feuilles ; 90 pièces dans « Interior Areas », 17 encore douteuses.
Trop pour un seul TileSet : prévoir des familles (extérieur, grottes, intérieurs) — voir [Godot](godot.md).


## Contrôle indépendant des grilles (revue C5, 2026-10-29)
La « reconstruction » est presque tautologique (tuiles découpées puis recollées au même endroit). Mesure
indépendante : part des tuiles d'une zone vues UNE seule fois dans toute la bibliothèque. Une grille décalée
donne ~100 %. Résultat : Émeraude médiane 0 % (5 zones > 60 %, petites pièces), Rubis/Saphir médiane 1 %
(2 zones > 60 %) → grilles saines. Minish Cap médiane 37 %, 11 zones > 80 % : ce sont des **décors peints**
(maisons Minish vues en grand, chemins du mont Crenel) — même en tuiles de 8 px et au meilleur décalage, 73 à
95 % des blocs sont uniques. Pas d'erreur de grille : ces cartes ne se réutilisent pas en tuiles ; dans Godot,
la TileMapLayer les reproduit fidèlement mais autant les traiter comme des images de fond.
