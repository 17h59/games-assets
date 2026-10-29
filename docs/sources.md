# Sources brutes et scraper

[← Sommaire](README.md) · voir aussi [Fiches](fiches.md), [Arborescence](arborescence.md)

## Origine
The Spriters Resource, pages des 4 jeux (Game Boy Advance) :
- `thelegendofzeldatheminishcap`, `pokemonrubysapphire`, `pokemonemerald`, `pokemonmysterydungeonredrescueteam`.

Le site est derrière un **challenge Cloudflare** (`curl` reçoit 403 « Just a moment... »).

## Règle importante
`tools/spriters_scraper.py` a été écrit par l'**utilisateur**. Il résout le challenge Cloudflare
automatiquement (nodriver + xvfb). **Claude ne le lance pas** (contournement de vérification anti-bot, refusé
aussi par le classifieur de permissions). Claude donne la commande ; l'utilisateur l'exécute (par ex. avec `! `) :

```
cd /home/garen/games && for g in game_boy_advance/thelegendofzeldatheminishcap game_boy_advance/pokemonrubysapphire \
  game_boy_advance/pokemonemerald game_boy_advance/pokemonmysterydungeonredrescueteam; do
  .venv/bin/python tools/spriters_scraper.py "https://www.spriters-resource.com/$g/" -o rpg/_raw -c 2; sleep 5; done
```

## Résultat
`rpg/_raw/<Titre du jeu>/<Section>/<Titre>_<id>.png` + `metadata.json` par jeu ; 673 feuilles (55 Mo).
Les dossiers portent les titres du site (« Pokémon Emerald », « The Legend of Zelda_ The Minish Cap »...),
traduits en noms courts par `config.GAMES`.

`tools/sk init` crée une fiche par feuille et la classe (catégorie + type) d'après sa section et son titre :
règles `RULES` / `EXCLUDE_TITLE` dans `cli.py`. Les sections Pokémon et les écrans sans intérêt sont `skip`.
