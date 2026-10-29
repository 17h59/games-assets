# Récapitulatif (`sk report`)

[← Sommaire](README.md) · code : `tools/spritekit/report.py` · voir aussi [Délégation](delegation.md), [Étapes](etapes.md)

Demandé par l'utilisateur le 2026-10-28 : ce qui a été fait, par qui, ce qui reste, en %, avec le temps et la
consommation passés et estimés. `tools/sk report` l'affiche et l'écrit dans `rpg/pipeline/RECAP.txt`.

## Sources
- **Avancement** : statuts des fiches et confirmations d'étapes valides (`checks.missing`) ; niveaux d'escalade en file.
- **Qui** : champ `by` de chaque confirmation (`cc:...haiku` → Haiku, `agy:` → Gemini, `outil`, `manuel`,
  `historique:` → rétroactif). Le travail Gemini antérieur aux confirmations (27/10 avant 20h) n'apparaît
  que dans les journaux de lots.
- **Temps** : journaux `rpg/pipeline/logs/*.log` (en-tête `# lot TAG : [ids]` / `# modèle M`) ; durée =
  date de dernière écriture du journal − heure du nom de lot.
- **Coût** : agents Claude Code = `costUSD` de leur sortie stream-json (équivalent API) ; agy ne publie rien
  (« n.c. »). Tokens par modèle : transcripts Claude Code du projet (`~/.claude/projects/-home-garen-games`),
  session principale Opus comprise.

## Estimations du reste
Moyennes mesurées par feuille (Haiku, Gemini) × feuilles restantes. Hypothèses (`GUESS`) : cartes = Haiku × 1,5
(jamais déléguées : à recaler après un premier lot), 20 % des feuilles escaladées. Durée murale = 4 Haiku + 2
Gemini en parallèle, sans les attentes de quota. Ordres de grandeur seulement.
