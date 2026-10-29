# Étapes obligatoires et couverture

[← Sommaire](README.md) · code : `tools/spritekit/checks.py` · voir aussi [Statuts](statuts.md), [Journal](journal.md)

Exigence de l'utilisateur (2026-10-27, après la découverte d'effets validés mais rangés en vrac) : chaque
chose doit être traitée **au moins une fois**, avec une **confirmation** à chaque fois.

## Étapes par type (`STAGES`)
| Type | Étape | Ce qu'on confirme |
|---|---|---|
| sprites / characters | `decoupage` | éléments entiers, seuls, fond transparent, déchets jetés |
| | `regroupement` | animations / persos en entités, sections en [ensembles](ensembles.md) (ou `na` : objets indépendants) |
| | `nommage` | ensembles / entités nommés d'après les légendes (ou `na` : aucune légende) |
| map / tileset | `grille` | bonne grille pour chaque zone |
| | `reconstruction` | la carte reconstruite à partir des tuiles reproduit l'originale |

## Confirmer
`tools/sk check ID ETAPE ok|na "note"` → `checks[étape] = {result, by, t, note, state}` dans la [fiche](fiches.md).
`by` = `SK_AGENT` (agent), `manuel`, `outil` (confirmation automatique), `historique:...` (rétroactive).

**Caducité** : `state` = empreinte de `params`, `overrides`, `zones`, `regions` au moment de la confirmation.
Si la fiche change ensuite, la confirmation est caduque. `sk status ID ok` est **refusé** tant qu'une étape
requise n'est pas confirmée sur l'état actuel (message avec la liste et la commande).

Confirmations automatiques (`sk tiles` pour tout un jeu, `sk recon ID` pour une feuille) : `reconstruction` si ≥ 97 % des pixels des zones sont reproduits ;
`grille` si toutes les zones de la feuille ont une confiance ≥ 0,5. Sinon : vérification à faire.

## Modification de l'outil
Une confirmation porte sur l'état de la **fiche** ; un changement de l'**outil** peut changer la sortie sans
toucher la fiche. Après toute modification de `tools/spritekit` : `tools/sk regress --write` (ré-extraction à
blanc de chaque feuille validée, comparaison au manifest ; sortie différente → `needs_review` + note, journal
`régression`). Une feuille `auto_ok` le reste à la ré-extraction ; une `ok` aussi si ses étapes sont valides.

## Suivre
- `tools/sk coverage [--game G] [--list]` : par type et par étape, combien de feuilles sont confirmées / à faire
  (`--list` : les ids).
- Marqueurs dans les dossiers d'assets (`auto.refresh_marker`, après `sk run` et `sk status`) :
  `A_VERIFIER.txt` (pas validée : statut + étapes manquantes), `NON_VERIFIE.txt` (`auto_ok`), rien si `ok`
  avec toutes les étapes. Le manifest porte `validation`, `status`, `missing_stages`.

## Migration du 2026-10-27
Les 92 feuilles `ok` d'avant la règle : `decoupage` confirmé rétroactivement (`historique:<agent>`), statut
→ `needs_review` pour `regroupement` et `nommage`. Réglages par défaut ajoutés quand absents :
`sets=captions` (toutes), `group=anim` (effets, monstres, persos Zelda), `anchor=center` (effets).
