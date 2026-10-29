# Chaîne d'extraction des sprites

[← Sommaire](README.md) · code : `tools/spritekit/extract.py` (`run` → `detect` → `_detect_part`)

Pour les fiches de type `sprites` et `characters`. Déterministe : mêmes PNG brut + fiche → même résultat.

1. **Fond** retiré sur toute la feuille ([Retrait du fond](fond.md)).
2. **Parties** : chaque [zone](zones.md) (dans l'ordre, première qui contient gagne) puis le reste. Une
   zone avec des paramètres de fond refait son propre retrait de fond. Une zone `skip` est ignorée.
3. Pour chaque partie (`_detect_part`) :
   1. **composantes connexes** (8-connexité) après dilatation de `gap` (`imageops.components`) ;
      plus une version sans fusion (`lab_fine`) pour `split` ;
   2. description de chaque composante : boîte, aire, nb de couleurs, couleur dominante et sa part ;
   3. `tiny` si trop petit ; **texte**, **encarts** et **déchets** ([Déchets](dechets.md)) ;
   4. **grille / xycut** si `layout` le permet, puis re-détection du texte ([Grilles](grilles.md)) ;
   5. **carve** puis les autres [corrections manuelles](corrections.md).
4. **Ordre de lecture** : rangées de grille, sinon lignes d'après le bas des sprites (`row_tol`), gauche → droite.
5. **Entités** selon `group` ([Entités](entites.md)) + contrôle de palette (`mixed_entity`).
6. **Écriture** ([Sorties](sorties.md)) : bandes d'entités, items isolés, miroirs internes, manifest,
   `rpg/pipeline/qa/<id>/last_run.json`. Puis [rapport et planches](qa.md) par la CLI.

Chaque item garde des références internes : `labels` (liste de `(tableau, label)` : `g` composantes,
`f` sans fusion, `c` cases de grille, `k` carve), `_labs` (les 4 tableaux de sa partie), `_a` (image de sa
partie). `_pixels(a, item)` reconstitue exactement ses pixels, sans ceux des voisins.

Types d'items (`kind`) : `sprite` (gardé), `text`, `panel`, `junk`, `tiny`, `dropped` (corrections).
