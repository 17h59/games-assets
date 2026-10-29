# Journal

[← Sommaire](README.md) · code : `tools/spritekit/journal.py` · fichier : `rpg/pipeline/journal.jsonl`

Exigence de l'utilisateur : savoir ce qui est fini ou pas par les agents. Journal **append-only**, une ligne
JSON par événement, écritures verrouillées (`fcntl.flock`) car plusieurs agents écrivent en parallèle.

```json
{"t": "2026-10-27 20:03:51", "agent": "agy:20261027_200017_b0", "event": "drop", "sheet": "8329", "refs": ["12"]}
```
`agent` = variable `SK_AGENT` (posée par [delegate.py](delegation.md)), sinon `manuel`.

Événements :
- commandes `sk` qui modifient (`set drop keep split merge cut add carve name clear status zone region
  objdrop objname autovalidate suggest init`) avec leurs arguments ;
- `run` : résultat (sprites, entités, anomalies) ;
- répartiteur : `attribué` (lot, modèle, reprise), `terminé` (statut, durée), `interrompu` (raison :
  quota / timeout / fin sans statut / agent disparu, tentatives), `abandon` (→ needs_fix) ;
- `relancé` : feuille remise en file par le développeur après correction d'outil, avec la piste.

Lire : `tools/sk journal [ID] [--last N]`. Utile aussi aux agents en reprise (« qu'a fait le précédent ? »).
