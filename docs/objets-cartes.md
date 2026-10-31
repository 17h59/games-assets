# Objets des cartes

[← Sommaire](README.md) · code : `tools/spritekit/objects.py` · commandes : `sk objects JEU`, `sk run obj_<jeu>_NN`

Maisons, arbres, meubles, panneaux, rochers… reconstitués à partir des cartes converties en tuiles
([Cartes et tuiles](cartes-tuiles.md)), pour être posés sur n'importe quel autre décor.

## Chaîne (v3, 2026-10-29)
1. **Cartes seulement** : feuilles `tileset` (tuiles rangées à plat) et ignorées exclues.
2. **Terrain** (`classify_terrain`) : tuile fréquente (≥ 8) qui se répète dans les deux directions ou a ≥ 10
   voisins différents. **Murs = séparateurs** (jamais dans un objet, jamais pris comme sol) : bandes horizontales
   fréquentes, tuiles collées au **vide** (-1, hors de la pièce) dans ≥ 50 % de leurs occurrences, et les rangées
   en dessous (`void_walls`).
3. **Objet** = composante de tuiles non-terrain voisines ; terrain enfermé (toit plat, cour) inclus.
4. **Sol retiré tuile par tuile** : parmi les sols voisins, celui qui explique le plus de pixels ; seules les
   plages ≥ 6 px reliées au bord de l'objet sont retirées (pas de confettis dans une texture).
5. **Ombre** : pixels = sol assombri du même facteur sur R, G, B (0,3–0,92), d'un seul tenant avec le vide →
   noir semi-transparent (alpha = 1 − facteur). L'objet se pose sur n'importe quel sol.
6. **Découpage automatique** (`_auto_split`) : deux tuiles ne restent ensemble que si leurs pixels (sol retiré,
   ombre comprise) se touchent → une table et le canapé d'à côté = 2 objets ; morceaux identiques fusionnés.
7. **Morceaux de terrain** écartés (`terrain_pieces` dans objects.json) : 1-2 tuiles opaques, transition entre
   deux sols (`_edge_piece`), ou presque vides (< 6 % de pixels).
8. **Signature = contenu des tuiles** (hash de pixels de la bibliothèque), pas leurs numéros : reconstruire la
   bibliothèque ne casse pas les corrections.

Sorties : `rpg/assets/<jeu>/objects/<nom>.png` + `objects.json` (dispositions, sols, occurrences ; entrées
`dropped` = jetées). Bilan v3 : Émeraude 1 197 objets + 34 structures (31 pages), Rubis/Saphir 2 302 + 77
(60 pages), Minish Cap 524 + 45 (15 pages).

## Vérification par pages
Fiches `obj_<jeu>_NN` (type `objects`, 40 objets, étape `objets`) : répartition **stable** (un objet garde sa
page et son numéro ; les morceaux d'un découpage s'ajoutent en fin de page). Corrections rangées par signature
dans la fiche de la page : `sk objdrop ID n…` (`--undo`), `sk objsplit ID n x,y,l,h…` (rectangles en tuiles ;
`undo`), `sk objname ID n nom`. Planches `qa/ID/objets_K.png` : 10 objets par image, objet sur damier + même
endroit dans la carte d'origine. `sk objects` reconstruit tout un jeu (développeur) ; `sk run` d'une page le fait
aussi, sous verrou (`config.lock`) car plusieurs agents travaillent en parallèle.

**Limites** : sol mal retiré quand le sol voisin varie (eau animée, marbre) ; porte de maison parfois absente
(tuile différente selon l'occurrence) ; les agents Haiku découpent rarement (`objsplit`) d'eux-mêmes.

**objsplit d'un objet issu de la découpe automatique** (2026-10-30) : sans réglage, l'objet DISPARAÎT de sa page
sans aucun morceau (la page est renumérotée). Activer `tools/sk set ID split_pieces=true` sur la page (opt-in : les
pages déjà validées ne changent pas). Pages ruby_sapphire `ok` concernées (objet découpé absent du catalogue) :
19, 44, 46, 48, 60, 61, 65 → à revoir avec `split_pieces=true` (décision développeur).
