# The Spriters Resource Scraper

Scraper haute performance et résilient pour [The Spriters Resource](https://www.spriters-resource.com/).

## Caractéristiques

- **Contournement Cloudflare Transparent** : Résolution automatique du challenge Cloudflare en tâche de fond (via `nodriver` et `xvfb-run` sous Linux), avec mise en cache locale des cookies (`cf_clearance`, etc.). Les téléchargements suivants s'exécutent instantanément sans relancer le navigateur.
- **Téléchargement ultra-rapide et concurrent** : Exploitation de `curl_cffi` avec multi-threading (`ThreadPoolExecutor`), permettant de télécharger plusieurs dizaines d'assets par seconde.
- **Détection directe & Mode Approfondi** :
  - Déduit automatiquement l'URL haute résolution de l'asset directement à partir de la page du jeu (`/media/asset_icons/...` $\rightarrow$ `/media/assets/...`).
  - Si un asset échoue ou a un format spécifique (.zip, .gif), visite automatiquement la sous-page de l'asset pour récupérer le lien direct (`download`).
- **Organisation automatique** : Classement dans des dossiers par jeu et par section (`downloads/<Jeu>/<Section>/<Titre>_<ID>.<ext>`), avec sauvegarde d'un fichier `metadata.json`.
- **Filtres & Reprise** : Possibilité de filtrer par nom de section (ex: `--section "Playable Characters"` ou `--section "Gyms"`), ignorer les fichiers déjà téléchargés (avec `--force` pour forcer), ou simplement lister les assets sans télécharger (`--list`).

## Utilisation

Le script utilise l'environnement virtuel situé dans `.venv` :

```bash
# Activer le venv (ou utiliser directement .venv/bin/python)
source .venv/bin/activate
```

### 1. Télécharger tous les assets d'un jeu
```bash
python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/
```

### 2. Lister les sections et assets sans les télécharger
```bash
python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/ --list
```

### 3. Télécharger une section spécifique (regex / mot-clé)
```bash
python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/ --section "Playable Characters"
python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/ --section "Gyms"
```

### 4. Télécharger un asset individuel via son URL de sous-page
```bash
python tools/spriters_scraper.py https://www.spriters-resource.com/game_boy_advance/pokemonemerald/asset/523725/
```

### 5. Personnaliser le dossier de destination et la concurrence
```bash
python tools/spriters_scraper.py <URL> -o ./mes_sprites -c 8
```

## Options disponibles

| Option | Description |
|---|---|
| `url` | URL de la page de jeu ou de la sous-page d'un asset |
| `-o, --output` | Répertoire de destination (défaut : `./downloads`) |
| `-c, --concurrency` | Nombre de téléchargements simultanés (défaut : 4) |
| `-s, --section` | Filtrer par section (ex: `"Pokémon"`, `"Gyms"`) |
| `-f, --force` | Forcer le re-téléchargement si les fichiers existent déjà |
| `-l, --list` | Affiche la liste des assets et sections sans télécharger |
| `--deep` | Visite systématiquement chaque sous-page d'asset |
