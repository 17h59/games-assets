# Limites connues et travail restant

[← Sommaire](README.md) · à mettre à jour à chaque session

## État au 2026-10-29, 08 h 55 (nuit autonome, l'utilisateur a tout autorisé)
- **Audit** : Haiku seul peu fiable : sur 49 feuilles revues par Gemini, 7 accords, 24 découpages corrigés,
  12 regroupements, 5 renommages (`sk audit --report`). 29 restantes + 10 pages (objets, bords, tables PMD)
  en audit ; quota Gemini épuisé jusqu'à 13 h 09 (les répartiteurs attendent).
- Cartes : toutes `ok`. **Objets** : 110/110 pages `ok`. **PMD** : 60/60 tables `ok`, décors `ok`.
- **Bords Pokémon** : 29/29 pages `ok` → TileSets `terrains_emerald/ruby_sapphire.tres` (raccords partiels).
- **Godot** : 2 044 SpriteFrames, 65 TileSets, 723 cartes, démos Bourg-en-Vol, donjon, bords.
- Répartiteurs `batch29_argon_<type>.out` (`--pool argon`) : audit des 39 éléments restants par Argon medium.
- Godot régénéré à 06 h 50 : 0 erreur.

## À faire
1. Relire les `needs_fix` / escalades → corriger les outils → relancer ([Statuts](statuts.md)).
2. Après la vérification des objets / terrains / décors : `tools/sk godot` puis import + `build_resources.gd`
   ([Godot](godot.md)).
3. Revue hostile non encore appliquée : I5 (verrou global sur les fiches : mises à jour « charger → long
   travail → sauver »), M2 (empreinte sans type/titre/source), M3 (écriture atomique du dossier de sortie),
   M4 (doublons écrits en fichiers séparés), M6 (`release_stale` par sous-chaîne), C7 complet (anomalies à
   acquitter avant `ok`), I8 complet (gabarits directionnels des persos Pokémon sans gabarit : `sk anims`
   existe, aucun agent ne l'a encore appliqué), I10 (tuiles vues une seule fois, miroirs).
4. Bords de terrains Pokémon : exportés mais incomplets (voir [Godot](godot.md)) ; Minish Cap : aucune
   transition détectée.
5. Collisions Godot : heuristique (tout non-sol bloque, eau traversable) ; à affiner.
6. `sk dupes` après les extractions ([Doublons](doublons.md)).

## Limites connues
- (2026-10-30) Pages d'objets ruby_sapphire 19, 44, 46, 48, 60, 61, 65 validées `ok` alors qu'un objet découpé y a
  disparu sans morceaux : activer `split_pieces=true` puis revoir (renumérote la page, invalide la confirmation).
- (2026-10-30) Fiches ok avec sprites en double dus au `split` historique : 28882, 5342, 31116 → `split_own=true` à
  tester puis revoir ; 5343/6407/6546 dépendent au contraire du comportement historique (ne pas l'activer).
- (2026-10-30) Répartiteurs lancés avant le correctif `assigned_by` : encore sujets à la course « agent disparu ».
- Objets : sol mal retiré quand le sol voisin varie (eau, marbre) ; porte de maison parfois absente ; Haiku
  découpe rarement (`objsplit`) → découpage automatique par connexité.
- Minish Cap : plusieurs « cartes » sont des décors peints (tuiles uniques) — fidèles mais non réutilisables.
- Texte de ripper multicolore parfois manqué → zone `skip`.
- Le quota agy est le goulot d'étranglement → escalade : Gemini seulement quand Haiku échoue.
