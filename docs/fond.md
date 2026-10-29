# Retrait du fond

[← Sommaire](README.md) · code : `imageops.remove_background`, `border_colors`, `_peel` · paramètres : [Fond](parametres.md)

1. **Déjà transparente** si plus de 1 % des pixels ont alpha = 0 (et `bg=auto`) : on ne touche pas aux
   couleurs (mais l'épluchage s'applique).
2. **Couleurs de fond** (`bg=auto`) : couleurs du bord de l'image. Jusqu'à 3 couleurs si ensemble elles
   couvrent ≥ 90 % du bord et chacune ≥ 10 % (damiers, rayures — cas « Interior Areas » d'Émeraude,
   damier rose/vert). Sinon une seule : un bord de carte texturé ne donne qu'une couleur.
3. Les couleurs sont retirées **ensemble** (un damier n'est connexe qu'en réunissant ses 2 couleurs) :
   partout (`bg_mode=global`) ou seulement la partie reliée au bord (`edge`), à `bg_tol` près.
4. **Épluchage** (`peel` couches) : fonds emboîtés (cadres, cases colorées, colonnes de couleurs). Toute
   grande zone unie (≥ `peel_min_area` px, boîte ≥ 12x12, remplissage ≥ 30 %) qui touche le vide devient du
   fond ; on retire **la zone**, pas la couleur partout (protège les sprites de même couleur) ; on recommence.
5. `black_bg` ajoute le noir aux couleurs de fond.

Cas difficiles : une couleur qui sert de fond à un endroit et de couleur de sprite ailleurs (Vaati, Move
Effects R/S) → **fond par zone** ([Zones](zones.md)).

Historique : l'épluchage remplace une détection « couleurs de grands rectangles » trop fragile ; le plancher
d'aire `0.002 x surface` a été retiré car il écrasait `peel_min_area` (trouvé par un agent, voir [Historique](historique.md)).
