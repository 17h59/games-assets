"""Chemins du projet et fiches de feuille (une fiche JSON par feuille source)."""
import json
import os
import re
import unicodedata

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.abspath(os.path.join(TOOLS, "..", "rpg"))
RAW = os.path.join(PROJECT, "_raw")
ASSETS = os.path.join(PROJECT, "assets")
PIPELINE = os.path.join(PROJECT, "pipeline")
SHEETS = os.path.join(PIPELINE, "sheets")
QA_DIR = os.path.join(PIPELINE, "qa")

GAMES = {
    "Pokémon Emerald": "emerald",
    "Pokémon Ruby _ Sapphire": "ruby_sapphire",
    "The Legend of Zelda_ The Minish Cap": "minish_cap",
    "Pokémon Mystery Dungeon_ Red Rescue Team": "pmd_red",
}

# auto_ok = validé automatiquement (aucune anomalie) mais NON vérifié par un agent ou un humain
STATUSES = ["todo", "extracted", "needs_review", "needs_fix", "auto_ok", "ok", "skip"]

# Valeurs par défaut de chaque paramètre ; une fiche ne stocke que ce qui diffère.
DEFAULT_PARAMS = {
    # tables d'autotiles Donjon Mystère (type terrainset) : noms des groupes de colonnes, dans l'ordre
    "pmd_groups": None,
    # effets plein écran (météo...) rangés un écran par encadré : chaque encadré = une frame (fond -> transparent)
    "panel_frames": False,    # ex. ["walls","wall_alt_1","wall_alt_2","ground","ground_alt","water"]
    # pages d'objets : les objsplit de la page s'appliquent aussi aux objets issus de la découpe automatique
    # ou d'un autre objsplit (sinon ils disparaissaient sans morceaux) ; opt-in, voir objects._late_splits
    "split_pieces": False,
    # fond
    "bg": "auto",          # "auto" | "none" | "#RRGGBB" | liste de couleurs
    "bg_tol": 12,          # tolérance par canal
    "bg_mode": "global",   # "global" (couleur retirée partout) | "edge" (seulement reliée au bord)
    "black_bg": False,     # effets sur fond noir : noir -> transparent
    "peel": 4,             # couches de fonds emboîtés à éplucher (cadres, cases colorées) ; 0 = off
    "peel_min_area": 256,  # aire mini (px) d'une zone unie pour être considérée comme fond
    # détection des sprites
    "gap": 1,              # écart (px) en dessous duquel deux morceaux sont fusionnés
    "min_size": 4,         # ignore ce dont le plus grand côté est < min_size
    "min_area": 6,         # ignore ce qui a moins de pixels opaques
    "drop_text": True,     # retire automatiquement les légendes / crédits détectés
    "text_max_h": 16,      # hauteur max d'un caractère de légende
    "drop_junk": True,     # retire captures d'écran 240x160, traits, quadrillages
    # grille (feuilles de sprites régulières)
    "layout": "auto",      # "auto" (grille si fiable, sinon taches) | "grid" (grille dès qu'elle existe) | "blobs"
    "block_gap": 8,        # vide (px) qui sépare deux blocs de grilles différentes
    "grid_min_pitch": 8,   # pas de grille minimal / maximal (px)
    "grid_max_pitch": 96,
    "grid_min_conf": 0.8,  # confiance mini (1 - densité de pixels coupés par les frontières) en mode auto
    "grid_min_sprites": 4, # en dessous, un bloc reste en mode taches
    "grid_pitch": "auto",  # pas imposé "LxH" (ex. 16x32) : la grille n'est plus devinée
    "grid_origin": "auto", # origine imposée "x,y" (coin d'une case, coordonnées de la feuille)
    "frag_gap": 3,         # xycut : un fragment à <= frag_gap px d'un sprite y est rattaché
    "split_own": False,    # sk split : ne recréer QUE les morceaux de l'item visé (sinon tout ce qui est dans
                           # sa boîte : un split sur un grand cadre dupliquait chaque sprite entouré, 8183)
    # regroupement
    "group": "none",       # "none" | "rows" | "chunks" (lignes coupées tous les `frames`) | "columns" (idem en
                           # colonnes) | "blocks" (blocs 2D, voir entity_shape) | "palette" | "anim" (animations en ligne)
    "frames": 9,           # frames par entité pour group=chunks
    "frames_alt": [3],     # tailles de segment acceptées telles quelles (ex. PNJ à 3 poses)
    "entity_shape": "3x3", # group=blocks : taille d'une entité en cases "colonnes x rangées"
    "frame_order": "row",  # group=blocks : ordre des frames dans le bloc, "row" (ligne par ligne) ou "col"
    "col_tol": 0.5,        # columns/blocks : deux sprites sont dans la même colonne si leurs centres
                           # sont à moins de col_tol x largeur médiane
    "row_tol": 6,          # tolérance (px) sur le bas des sprites pour les mettre sur la même ligne
    "row_split_gap": 10,   # trou horizontal (px) qui coupe une ligne en deux segments
    "cell": "auto",        # taille de case normalisée "WxH" ou "auto" (max du groupe)
    "anchor": "bottom",    # ancrage dans la case : "bottom" (pieds) | "center"
    "template": "none",    # noms des frames : voir templates.py
    "sets": "none",        # "captions" : chaque légende de la feuille ouvre un ensemble (sous-dossier) ;
                           # les sprites rejoignent la légende au-dessus d'eux (nommer : sk setname)
    "anim_split_sim": 0.2, # group=anim : on coupe une ligne là où deux frames voisines ont des palettes
                           # plus différentes que ça (Jaccard) = autre effet / autre perso
    "palette_sim": 0.6,    # group=palette : ressemblance mini des palettes (0..1)
    "palette_dist": 48,    # group=palette : distance max (px) entre deux frames d'un même perso
    # grille (tilesets / cartes)
    "tile": 16,
    "grid_offset": "auto", # "auto" ou "x,y"
}


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "x"


def sheet_path(game: str, sid: str) -> str:
    return os.path.join(SHEETS, game, f"{sid}.json")


def find_sheet(sid: str) -> str:
    """Retrouve la fiche d'un id (sans connaître le jeu)."""
    for game in os.listdir(SHEETS):
        p = sheet_path(game, sid)
        if os.path.exists(p):
            return p
    raise SystemExit(f"fiche introuvable : {sid} (lance `sk list` pour voir les ids)")


def _read_json(path, tries=20):
    """Lecture tolérante : plusieurs agents écrivent en parallèle ; on réessaie si le fichier est en
    cours de remplacement (les écritures sont atomiques, mais on reste prudent)."""
    import time
    for k in range(tries):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            if k == tries - 1:
                raise
            time.sleep(0.05)


def write_json_atomic(path, data, **kw):
    """Écriture atomique : fichier temporaire dans le même dossier, puis os.replace (jamais de fichier
    vide ou à moitié écrit visible par un autre processus)."""
    import tempfile
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, **kw)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


class lock:
    """Verrou exclusif entre processus (agents en parallèle) : `with config.lock("objects_emerald"): ...`"""
    def __init__(self, name):
        self.path = os.path.join(PIPELINE, "locks", f"{name}.lock")

    def __enter__(self):
        import fcntl
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def load(sid: str) -> dict:
    return _read_json(find_sheet(sid))


def save(cfg: dict):
    write_json_atomic(sheet_path(cfg["game"], cfg["id"]), cfg, indent=1)


def params(cfg: dict) -> dict:
    return {**DEFAULT_PARAMS, **cfg.get("params", {})}


def all_sheets():
    for game in sorted(os.listdir(SHEETS)) if os.path.isdir(SHEETS) else []:
        for f in sorted(os.listdir(os.path.join(SHEETS, game))):
            if f.endswith(".json") and not f.startswith(".tmp_"):
                yield _read_json(os.path.join(SHEETS, game, f))


def out_dir(cfg: dict) -> str:
    return os.path.join(ASSETS, cfg["game"], cfg["category"], slug(cfg["title"]))


def empty_overrides() -> dict:
    # tout est ancré sur des points (x, y) de la feuille source, pas sur des numéros
    return {"drop": [], "keep": [], "merge": [], "split": [], "add": [], "carve": [], "cut": [], "names": [],
            "setnames": [], "setbox": [], "entities": [], "erase": [], "flood": [], "anims": []}
