# Terrains Donjon Mystère (tables d'autotiles)

[← Sommaire](README.md) · code : `tools/spritekit/pmd.py` · type de fiche : `terrainset`

Les 60 feuilles « tilesets » de PMD sont des **tableaux formatés** (« Ripped and formatted by SilverDeoxys563 ») :
cases de 24 px, lignes de 1 px cyan `#80FFFF` ou rose `#FF80FF` au pas de 25, en-tête de colonnes, puis
**Legend** + groupes de 3 colonnes (Walls, Wall Alt. 1/2, Ground, Ground Alt., Water, Water Sparkle…).
Chaque case de légende = motif 3x3 (carré plein = voisin du même terrain) : c'est exactement les *peering
bits* d'un terrain Godot. 45 tuiles par terrain (jeu complet).

- `sk run ID` : atlas par groupe `rpg/assets/pmd_red/terrains/<titre>/<groupe>.png` (la grille du tableau sans
  séparateurs) + `terrains.json` (col, rangée, masque des 8 voisins) + planche `qa/ID/terrains_0.png`
  (en-tête d'origine + groupes extraits + motifs décodés).
- Noms des groupes devinés d'après leur nombre ; les agents les corrigent d'après l'en-tête :
  `sk set ID pmd_groups='["walls",...]'` (paramètre `pmd_groups`). Étape obligatoire : `terrains`.
- Magenta `#FF00FF` = transparence du ripper : transparent dans `water_sparkle` (calque de reflets), remplacé par
  la couleur voisine ailleurs (pixels animés de l'eau).

Les 105 feuilles « maps » de PMD ne sont PAS des cartes en tuiles : décors peints (huttes, plaines, fonds de
donjon) + bandes d'animation. Reclassées le 2026-10-29 en `sprites`, catégorie `scenes`, `peel=0` (sinon le
ciel du décor est troué). Voir [Godot](godot.md) pour l'usage des terrains.
