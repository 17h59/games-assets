"""Journal append-only de tout ce qui arrive aux fiches : rpg/pipeline/journal.jsonl.

Une ligne JSON par événement : {"t": horodatage, "agent": qui, "event": quoi, "sheet": id, ...}.
`agent` vient de la variable d'environnement SK_AGENT (posée par delegate.py pour chaque lot),
sinon "manuel". Écritures protégées par un verrou de fichier (plusieurs agents en parallèle).
"""
import fcntl
import json
import os
import time

from . import config

PATH = os.path.join(config.PIPELINE, "journal.jsonl")


def log(event, sheet=None, **data):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "agent": os.environ.get("SK_AGENT", "manuel"), "event": event}
    if sheet is not None:
        rec["sheet"] = str(sheet)
    rec.update(data)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with open(PATH, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        fcntl.flock(f, fcntl.LOCK_UN)


def read(sheet=None, last=None):
    if not os.path.exists(PATH):
        return []
    out = []
    with open(PATH, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if sheet is None or rec.get("sheet") == str(sheet):
                out.append(rec)
    return out[-last:] if last else out


def fmt(rec):
    extra = {k: v for k, v in rec.items() if k not in ("t", "agent", "event", "sheet")}
    return f"{rec['t']}  {rec['agent']:<24} {rec['event']:<12} {rec.get('sheet', ''):>7}  " + \
        (json.dumps(extra, ensure_ascii=False) if extra else "")
