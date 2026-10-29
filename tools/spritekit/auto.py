"""Idée 3 : validation automatique des feuilles sans anomalie (marquées NON vérifiées).
Idée 6 : réglages hérités des feuilles sœurs déjà validées.

Marquage d'une feuille validée automatiquement :
- statut `auto_ok` dans sa fiche + note ;
- `"validation": "auto"` dans son manifest.json ;
- un fichier NON_VERIFIE.txt dans son dossier d'assets.
Quand un agent ou un humain met le statut `ok`, le manifest passe à "verified" et le fichier disparaît.
"""
import json
import os
import random
from collections import Counter

from . import config, extract, qa

MARKER = "NON_VERIFIE.txt"
# réglages qu'on peut hériter d'une feuille sœur (pas les couleurs exactes, propres à chaque feuille)
INHERITABLE = ["bg_tol", "bg_mode", "black_bg", "peel", "peel_min_area", "gap", "min_size", "min_area",
               "drop_text", "text_max_h", "drop_junk", "layout", "block_gap", "frag_gap", "group", "frames",
               "frames_alt", "row_tol", "row_split_gap", "anchor", "template", "palette_sim", "palette_dist"]


PENDING_MARKER = "A_VERIFIER.txt"


def set_validation(cfg, value):
    """value : "verified" (statut ok, toutes étapes confirmées), "auto" (validée automatiquement, non
    vérifiée), "pending" (pas encore validée). Met à jour le manifest et les fichiers marqueurs du dossier
    d'assets : NON_VERIFIE.txt (auto), A_VERIFIER.txt (pending, avec les étapes manquantes), aucun (verified)."""
    from . import checks
    out = config.out_dir(cfg)
    if not os.path.isdir(out):
        return
    mpath = os.path.join(out, "manifest.json")
    miss = checks.missing(cfg)
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
        man["validation"] = value
        man["status"] = cfg["status"]
        man["missing_stages"] = [m[0] for m in miss]
        config.write_json_atomic(mpath, man, indent=1)
    for name in (MARKER, PENDING_MARKER):
        path = os.path.join(out, name)
        if os.path.exists(path):
            os.remove(path)
    head = f"Fiche : rpg/pipeline/sheets/{cfg['game']}/{cfg['id']}.json  (statut actuel : {cfg['status']})\n"
    todo = "".join(f"  - {st} : {why}\n" for st, why in miss)
    if value == "auto":
        with open(os.path.join(out, MARKER), "w", encoding="utf-8") as f:
            f.write("Feuille validée AUTOMATIQUEMENT (aucune anomalie détectée) mais jamais vérifiée par un agent "
                    "ni un humain.\n" + head + ("Étapes non confirmées :\n" + todo if todo else ""))
    elif value == "pending":
        with open(os.path.join(out, PENDING_MARKER), "w", encoding="utf-8") as f:
            f.write("CES ASSETS NE SONT PAS ENCORE VALIDÉS : sortie brute ou en cours de vérification.\n" + head
                    + ("Étapes non confirmées :\n" + todo if todo else ""))


def refresh_marker(cfg):
    """Marqueur cohérent avec le statut et les confirmations de la fiche."""
    from . import checks
    if cfg["status"] == "ok" and not checks.missing(cfg):
        set_validation(cfg, "verified")
    elif cfg["status"] == "auto_ok":
        set_validation(cfg, "auto")
    else:
        set_validation(cfg, "pending")


def suggest(cfg, min_siblings=2, agree=0.6):
    """Réglages majoritaires des feuilles sœurs validées (même jeu, même section, même type)."""
    sibs = [c for c in config.all_sheets() if c["id"] != cfg["id"] and c["game"] == cfg["game"]
            and c["section"] == cfg["section"] and c["type"] == cfg["type"] and c["status"] == "ok"]
    if len(sibs) < min_siblings:
        return {}, len(sibs)
    out = {}
    for k in INHERITABLE:
        vals = Counter(json.dumps(c["params"][k]) for c in sibs if k in c["params"])
        if not vals:
            continue
        v, n = vals.most_common(1)[0]
        if n >= agree * len(sibs) and n >= min_siblings:
            out[k] = json.loads(v)
    return out, len(sibs)


def apply_suggestion(cfg):
    """Applique les réglages hérités à une fiche sans réglage propre. Renvoie ce qui a été appliqué."""
    if cfg.get("params"):
        return {}
    sug, n = suggest(cfg)
    if sug:
        cfg["params"] = dict(sug)
        cfg["notes"] = (cfg.get("notes", "") + f"\nréglages hérités de {n} feuille(s) sœur(s) validée(s) : "
                        + json.dumps(sug, ensure_ascii=False)).strip()
        config.save(cfg)
    return sug


def autovalidate(sample=0.1, dry=False, seed=0):
    """Feuilles `todo` sprites/characters : extraction ; aucune anomalie -> auto_ok (marquée non vérifiée).
    Une fraction `sample` des auto_ok est renvoyée en relecture (needs_review) pour contrôler la méthode.
    Les feuilles avec anomalies restent `todo` pour les agents."""
    rnd = random.Random(seed)
    res = Counter()
    for c in list(config.all_sheets()):
        if c["type"] not in ("sprites", "characters") or c["status"] != "todo" or c.get("assigned"):
            continue
        cfg = config.load(c["id"])
        inherited = apply_suggestion(cfg) if not dry else {}
        cfg = config.load(c["id"])
        r = extract.run(cfg, write=not dry)
        fl = qa.flags(r, cfg)
        n_sprites = sum(1 for it in r["items"] if it["kind"] == "sprite")
        if dry:
            res["sans anomalie" if not fl and n_sprites else "avec anomalies"] += 1
            continue
        cfg = config.load(c["id"])
        if not fl and n_sprites:
            if rnd.random() < sample:
                cfg["status"] = "needs_review"
                cfg["notes"] = (cfg.get("notes", "") + "\néchantillon de contrôle de la validation automatique").strip()
                res["échantillon -> relecture agent"] += 1
            else:
                cfg["status"] = "auto_ok"
                cfg["notes"] = (cfg.get("notes", "") + "\nvalidée automatiquement (0 anomalie), NON vérifiée").strip()
                res["auto_ok"] += 1
            config.save(cfg)
            set_validation(cfg, "auto")
        else:
            cfg["status"] = "todo"
            config.save(cfg)
            res["anomalies -> agents"] += 1
        if inherited:
            res["réglages hérités"] += 1
    return dict(res)
