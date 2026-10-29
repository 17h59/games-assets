# Documentation du projet (point d'entrée)

Mémoire de travail de Claude pour ce projet. **Après une remise à zéro du contexte, commencer ici.**
Chaque page traite d'un seul sujet ; suivre les liens.

## Reprendre le travail en 5 minutes

1. Lire [Le projet](projet.md) (but, contraintes, préférences de l'utilisateur).
2. `tools/sk summary` et `tools/sk coverage` : où en sont les feuilles et les étapes (voir [Statuts](statuts.md), [Étapes](etapes.md)).
3. `tools/sk journal --last 40` : ce qui s'est passé récemment (voir [Journal](journal.md)).
4. `cat rpg/pipeline/ALERT.txt` et `rpg/pipeline/logs/*.out` : la délégation tourne-t-elle, est-elle bloquée
   (voir [Délégation](delegation.md)) ?
5. [Limites connues et travail restant](limites-et-reste-a-faire.md) : quoi faire ensuite.
6. [Historique des décisions](historique.md) : pourquoi les choses sont comme elles sont.

## Plan

**Cadre**
- [Le projet](projet.md) — but, contraintes, préférences de l'utilisateur
- [Arborescence](arborescence.md) — où est quoi sur le disque
- [Sources brutes et scraper](sources.md) — d'où viennent les feuilles, règle sur le scraper
- [Historique des décisions](historique.md)

**Données**
- [Fiches de feuilles](fiches.md) — le JSON par feuille, unique interface de réglage
- [Statuts](statuts.md) — cycle de vie d'une feuille, dont `auto_ok`
- [Étapes obligatoires et couverture](etapes.md) — confirmations, `ok` bloqué, marqueurs A_VERIFIER
- [Sorties et manifests](sorties.md) — ce que produit l'extraction

**Outil `sk`**
- [Référence des commandes](sk-commandes.md)
- [Référence des paramètres](parametres.md)
- [Chaîne d'extraction des sprites](extraction-sprites.md) — fond, composantes, filtres, corrections
- [Retrait du fond](fond.md)
- [Texte, encarts et déchets](dechets.md)
- [Grilles, xycut et taches](grilles.md)
- [Zones](zones.md) — réglages par partie de feuille
- [Corrections manuelles](corrections.md) — drop, keep, merge, split, carve, cut, add, name
- [Regroupement en entités](entites.md) — chunks, rows, columns, blocks, palette, anim, gabarits
- [Récapitulatif `sk report`](recap.md) — avancement %, qui, temps, consommation, reste
- [Ensembles par légende](ensembles.md) — sous-dossiers par attaque / section, nommage
- [Contrôle qualité](qa.md) — rapport texte, anomalies, planches
- [Miroirs et doublons](doublons.md)
- [Validation automatique](validation-auto.md)

**Cartes et décors**
- [Cartes et tilesets : grilles et bibliothèque de tuiles](cartes-tuiles.md)
- [Objets des cartes](objets-cartes.md) — maisons, arbres, meubles (pages de vérification, ombres, découpage auto)
- [Terrains Donjon Mystère](terrains-pmd.md) — tables d'autotiles PMD, décors PMD reclassés en « scenes »

**Agents**
- [Délégation aux agents (Haiku → Gemini)](delegation.md) — escalade, sauvegarde git, garde-fous
- [Journal](journal.md)
- [Guide des agents](guide-agents.md)

**Suite**
- [Godot](godot.md) — projet, catalogue, SpriteFrames, TileSets à terrains, démo
- [Limites connues et travail restant](limites-et-reste-a-faire.md)
