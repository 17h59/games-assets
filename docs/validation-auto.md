# Validation automatique et réglages hérités

[← Sommaire](README.md) · code : `tools/spritekit/auto.py` · voir aussi [Statuts](statuts.md)

## `tools/sk autovalidate [--sample 0.1] [--dry]`
Pour chaque feuille `todo` (sprites/characters, non assignée) : réglages hérités si la fiche n'en a pas,
extraction, anomalies.
- **0 anomalie** → `auto_ok`, **marquée non vérifiée** ; une part `--sample` (10 %) part en
  `needs_review` avec la note « échantillon de contrôle » pour mesurer la fiabilité de la méthode.
- **Anomalies** → reste `todo` pour les agents.

## Marquage « non vérifié » (exigence de l'utilisateur)
- statut `auto_ok` + note dans la [fiche](fiches.md) ;
- `"validation": "auto"` dans le manifest ([Sorties](sorties.md)) ;
- fichier `NON_VERIFIE.txt` dans le dossier des assets (explique comment vérifier).
Retrouver : `tools/sk list --status auto_ok`, `find rpg/assets -name NON_VERIFIE.txt`.
`sk status ID ok` → `"verified"` et suppression du fichier (`auto.set_validation`).

## Réglages hérités — `tools/sk suggest ID [--apply]`
Feuilles sœurs = même jeu, même section, même type, statut `ok`. Pour chaque paramètre transmissible
(`INHERITABLE`, pas les couleurs exactes), la valeur majoritaire si ≥ 60 % et ≥ 2 sœurs. `--apply` les met
dans la fiche (ses propres réglages restent prioritaires) ; `autovalidate` les applique d'office aux fiches
sans réglage.
