# Texte, encarts et déchets

[← Sommaire](README.md) · code : `imageops.mark_text`, `mark_panels`, `mark_junk`

Ce qui n'est pas du contenu de jeu est marqué (pas supprimé) et apparaît en couleur sur l'overview
([QA](qa.md)) ; un agent peut toujours le récupérer avec `keep` ([Corrections](corrections.md)).

## Texte (`kind=text`, rouge) — `drop_text`
- Candidats : hauteur ≤ `text_max_h`, largeur ≤ 2x, part de la couleur dominante ≥ 35 % (le texte anti-aliasé
  a jusqu'à 15 nuances mais une couleur majoritaire).
- Chaînes : glyphes de **même couleur dominante**, sur la même ligne de base, écart ≤ max(2, 0.45 x hauteur).
  Une chaîne de ≥ 4 est du texte si ses formes sont **variées** (≥ 50 % de formes distinctes) — une rangée
  d'objets identiques (Poké Balls) n'en est pas.
- Mot soudé : très large (≥ 5 x hauteur) et couleur dominante ≥ 55 %.
- Propagation : un morceau collé à du texte, même couleur, même ligne → texte.
- Relancé après la grille (la grille peut séparer des mots soudés en lettres).

## Encarts (`kind=panel`, magenta)
Rectangle ≥ 40x14 presque plein (≥ 93 %) dont le contour est d'une seule couleur (≥ 85 %) : cartouches de
titre, crédits.

## Déchets (`kind=junk`, jaune) — `drop_junk`
- **Capture d'écran** : rectangle plein de 240x160 (taille écran GBA) ou multiple, sauf catégorie `ui`.
- **Trait** : ≥ 32 px de long et ≤ 2 px d'épais.
- **Quadrillage / cadre vide** : boîte ≥ 48x48, remplissage ≤ 12 %, ≥ 60 % des pixels sur des lignes pleines.

Limites : texte de ripper multicolore ou très anti-aliasé parfois manqué → zone `skip` ([Zones](zones.md)).
