# Statuts

[← Sommaire](README.md) · voir aussi [Fiches](fiches.md), [Validation automatique](validation-auto.md), [Délégation](delegation.md)

| Statut | Sens | Qui le pose |
|---|---|---|
| `todo` | à traiter (éventuellement `resume: true` = reprise d'un travail interrompu) | `sk init`, répartiteur |
| `extracted` | extraite, aucune anomalie, pas encore jugée | `sk run` |
| `needs_review` | extraite avec anomalies, ou échantillon de contrôle | `sk run`, `sk autovalidate` |
| `needs_fix` | l'agent n'y arrive pas : **souvent une limite d'outil** → pour le développeur | agent, ou répartiteur après 3 tentatives |
| `auto_ok` | validée automatiquement (0 anomalie), **NON vérifiée** (marquée) | `sk autovalidate` |
| `ok` | vérifiée, **toutes les [étapes](etapes.md) confirmées sur l'état actuel** (sinon refusé) | agent / humain via `sk status` |
| `skip` | hors périmètre | `sk init`, agent |

`tools/sk summary` compte par type et statut ; `tools/sk list --status needs_fix` liste.

Passer à `ok` met le manifest en `"validation": "verified"` et supprime `NON_VERIFIE.txt` ; `auto_ok` le
remet ; tout autre statut → `"pending"` (voir [Validation automatique](validation-auto.md)).

Cycle typique : `todo` → (agent : `sk run` → corrections → `sk status`) → `ok` | `needs_fix` | `skip`.
Un `needs_fix` est relu par le développeur, l'outil corrigé, puis la feuille est remise en `todo` +
`resume` avec une piste dans ses notes (voir [Historique](historique.md)).
