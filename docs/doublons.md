# Miroirs et doublons

[← Sommaire](README.md) · code : `extract._mirrors` (dans une feuille), `tools/spritekit/dupes.py` (global)

## Dans une feuille (à chaque `sk run`)
Pour les items isolés et pour les frames d'une entité : `duplicate_of` (identique au pixel près à un
précédent) ou `mirror_of` (identique une fois retourné horizontalement). Sert à Godot (`flip_h`) et au
nommage des directions. Ne pas jeter les miroirs.

## Entre feuilles et jeux (`tools/sk dupes`)
Toutes les images produites (entités et items de tous les manifests), rognées, comparées au pixel près.
Pour chaque groupe identique, un **original** est choisi (statut vérifié d'abord, puis jeu dans l'ordre
`emerald, ruby_sapphire, minish_cap, pmd_red`, puis id), les autres reçoivent `global_duplicate_of` (ou
`global_mirror_of`) dans leur manifest. Rien n'est supprimé. Index : `rpg/pipeline/dupes.json`.

Premier passage (2026-10-27) : 12 142 images, 2 801 doublons, 493 miroirs, 172 groupes inter-jeux.
À relancer après chaque série d'extractions.
