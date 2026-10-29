# Contrôle qualité

[← Sommaire](README.md) · code : `tools/spritekit/qa.py`

Après `tools/sk run ID` : un **rapport texte** (lu en premier, peu coûteux) et des **planches PNG** dans
`rpg/pipeline/qa/ID/` (regardées seulement si besoin : économie de tokens pour les agents).

## Rapport texte
Fond retiré, compte par `kind`, entités, zones, déchets auto, miroirs/doublons, `disposition` des blocs,
grilles imposées, corrections non appliquées, puis les **anomalies** :

| Anomalie | Sens |
|---|---|
| `big` / `small` | item ≥ 2,2x ou ≤ 0,4x la taille médiane (fusion ? débris ?) |
| `bg_suspect` | une couleur couvre > 35 % des pixels gardés (fond non retiré ?) |
| `row_count` | segment / colonne / bloc qui ne se décompose pas en tailles de `frames` |
| `frame_counts` | entités de tailles hors `frames`/`frames_alt` |
| `mixed_entity` | frame d'un autre personnage ([Entités](entites.md)) |
| `grid_cuts` | grille détectée (non imposée) qui coupe des sprites |
| `empty` | aucun sprite |

Statut posé par `run` : `needs_review` s'il y a des anomalies, sinon `extracted`.

## Planches
- `overview_*.png` : feuille (fond retiré, damier = transparent), une boîte par item avec son numéro.
  Vert sprite, rouge texte, magenta encart, jaune déchet, orange jeté à la main, gris débris, bleu épais
  entité (`eN` dessous), cyan zone (`Z0`).
- `results_*.png` : ce qui est réellement produit (entités puis items) ; `=m` miroir, `=d` doublon.
- `zoom_*.png` : `sk zoom`. Cartes : `regions_*.png`, `region_N_*.png`, `gridcheck_zN.png`.
Pages de 1400 px max ; échelle choisie sur la hauteur médiane des éléments.
