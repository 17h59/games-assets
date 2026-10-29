# Arborescence

[← Sommaire](README.md)

Racine : `/home/garen/games`

```
.venv/                         Python (Pillow, numpy, scipy, + dépendances du scraper)
tools/
  sk                           lanceur de l'outil : tools/sk <commande>   (voir sk-commandes.md)
  spritekit/                   le code de sk (paquet Python)
    config.py                  chemins, paramètres par défaut (SOURCE DE VÉRITÉ des paramètres), statuts
    cli.py                     ligne de commande, journalisation des commandes
    imageops.py                fond, composantes, texte, encarts, déchets
    grid.py                    grilles régulières, xycut
    extract.py                 chaîne d'extraction complète des sprites (zones, corrections, entités, écriture)
    templates.py               noms des frames et animations par gabarit
    qa.py                      anomalies, rapport texte, planches PNG
    tiles.py                   cartes / tilesets : zones, grille, référence, bibliothèque de tuiles
    objects.py                 objets des cartes (maisons, meubles)
    dupes.py                   doublons et miroirs entre feuilles / jeux
    auto.py                    validation automatique, réglages hérités
    journal.py                 journal append-only
  delegate.py                  répartiteur des agents agy (voir delegation.md)
  AGENT_GUIDE.md               consigne lue par chaque agent (voir guide-agents.md)
  spriters_scraper.py          scraper de l'UTILISATEUR (ne pas lancer, voir sources.md)
  README_SCRAPER.md
rpg/                           le futur projet Godot
  _raw/<Jeu>/<Section>/<Titre>_<id>.png    feuilles brutes (sources.md)
  assets/<jeu>/<catégorie>/<feuille>/      sorties de sk (sorties.md)
  assets/<jeu>/tiles/                      bibliothèque de tuiles (cartes-tuiles.md)
  assets/<jeu>/maps/<feuille>_<id>/        cartes converties en matrices de tuiles
  assets/<jeu>/objects/                    objets des cartes (objets-cartes.md)
  pipeline/
    sheets/<jeu>/<id>.json     une fiche par feuille (fiches.md)
    qa/<id>/                   planches de contrôle + last_run.json (qa.md)
    qa/objects_<jeu>/          planches des objets
    objects/<jeu>.json         corrections sur les objets
    logs/                      journaux des lots d'agents + sorties du répartiteur
    journal.jsonl              journal de tout (journal.md)
    dupes.json                 groupes de doublons (doublons.md)
    ALERT.txt                  alertes du répartiteur (quota...)
    STOP                       (si présent) le répartiteur ne lance plus de lot
docs/                          cette documentation
```

Noms de jeux (`<jeu>`) : `emerald`, `ruby_sapphire`, `minish_cap`, `pmd_red` (correspondance dans `config.GAMES`).
