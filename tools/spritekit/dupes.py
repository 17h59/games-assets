"""Idée 2 : doublons entre feuilles et entre jeux (Rubis/Saphir et Émeraude partagent beaucoup).

Chaque PNG produit (entité ou item) est identifié par ses pixels exacts. Pour chaque groupe identique,
un original est choisi (priorité : statut vérifié, puis jeu, puis id de feuille) et les autres reçoivent
`duplicate_of` dans leur manifest. Les images retournées (miroir) comptent aussi : `mirror_of`.
Index complet : rpg/pipeline/dupes.json.
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image

from . import config

GAME_PRIORITY = ["emerald", "ruby_sapphire", "minish_cap", "pmd_red"]
STATUS_PRIORITY = {"ok": 0, "auto_ok": 1, "needs_review": 2, "extracted": 2, "needs_fix": 3}


def _key(arr):
    return hashlib.blake2b(arr.tobytes() + bytes(str(arr.shape), "ascii"), digest_size=10).hexdigest()


def _crop(arr):
    """Rogne le vide autour (deux copies d'un même sprite peuvent avoir des marges différentes)."""
    m = arr[..., 3] > 0
    if not m.any():
        return arr
    ys, xs = np.nonzero(m)
    return np.ascontiguousarray(arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def build():
    status = {c["id"]: c["status"] for c in config.all_sheets()}
    entries = []  # (rang, chemin relatif, manifest, kind, index)
    for root, _, files in os.walk(config.ASSETS):
        if "manifest.json" not in files:
            continue
        mpath = os.path.join(root, "manifest.json")
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
        rank = (STATUS_PRIORITY.get(status.get(man["sheet"]), 4),
                GAME_PRIORITY.index(man["game"]) if man["game"] in GAME_PRIORITY else 9, man["sheet"])
        for kind in ("entities", "items"):
            for i, e in enumerate(man.get(kind, [])):
                if "file" in e:
                    entries.append((rank, os.path.relpath(os.path.join(root, e["file"]), config.ASSETS), mpath, kind, i))
    entries.sort()
    first, first_flip, groups = {}, {}, {}
    updates = {}
    for rank, rel, mpath, kind, i in entries:
        arr = _crop(np.array(Image.open(os.path.join(config.ASSETS, rel)).convert("RGBA")))
        k = _key(arr)
        fk = _key(np.ascontiguousarray(arr[:, ::-1]))
        tag = None
        if k in first and first[k] != rel:
            tag = ("duplicate_of", first[k])
        elif fk in first and fk != k:
            tag = ("mirror_of", first[fk])
        first.setdefault(k, rel)
        groups.setdefault(k, []).append(rel)
        updates.setdefault(mpath, []).append((kind, i, tag))
    n_dup = n_mir = 0
    for mpath, ups in updates.items():
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
        for kind, i, tag in ups:
            e = man[kind][i]
            e.pop("global_duplicate_of", None); e.pop("global_mirror_of", None)
            if tag:
                e["global_" + tag[0]] = tag[1]
                n_dup += tag[0] == "duplicate_of"
                n_mir += tag[0] == "mirror_of"
        config.write_json_atomic(mpath, man, indent=1)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    with open(os.path.join(config.PIPELINE, "dupes.json"), "w", encoding="utf-8") as f:
        json.dump({"groups": list(dup_groups.values())}, f, indent=1)
    return {"images": len(entries), "doublons": n_dup, "miroirs": n_mir, "groupes": len(dup_groups)}
