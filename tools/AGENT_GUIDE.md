# Guide agent : vérifier et corriger le découpage des feuilles de sprites

Tu travailles sur un projet de jeu Godot qui réutilise des sprites de jeux GBA (Pokémon Émeraude,
Rubis/Saphir, Zelda Minish Cap, Pokémon Donjon Mystère). Chaque **feuille** source (un gros PNG plein de
sprites) doit être découpée en **éléments isolés** propres : un PNG par objet, ou une bande de frames par
personnage animé.

Le découpage est automatique. **Ton rôle : vérifier le résultat de chaque feuille qu'on te donne, corriger
les erreurs avec les commandes ci-dessous, puis donner un statut.** Tu ne modifies JAMAIS le code Python ni les
fichiers PNG à la main. Tout passe par la commande `tools/sk` (lancée depuis `/home/garen/games`).

## Commandes

```
tools/sk show ID                   fiche de la feuille (type, paramètres, corrections, statut)
tools/sk run ID                    découpe + rapport texte + planches PNG de contrôle
tools/sk run ID --no-images        idem sans régénérer les planches (rapide)
tools/sk run ID -v                 rapport + liste de tous les items (numéro, type, x,y, LxH)
tools/sk zoom ID x0,y0,x1,y1       planche agrandie d'une zone de la feuille (coordonnées source)
tools/sk set ID clé=valeur ...     change des paramètres (valeur `default` = revenir au défaut)
tools/sk drop ID 12 15 e3          jette des items (numéros) ou toutes les frames d'une entité (eN)
tools/sk keep ID 40 41             récupère des items jetés à tort (texte, encart, débris)
tools/sk merge ID 7 8 9            fusionne plusieurs items en un seul (objet en morceaux)
tools/sk split ID 22               re-découpe un item qui contient plusieurs sprites collés
                                   (si le split d'un grand CADRE crée des sprites en double : `set ID split_own=true`)
tools/sk add ID x,y,w,h            boîte forcée : tout ce qui est dedans devient UN item
tools/sk carve ID x,y,w,h          découpe AU PIXEL PRÈS : les pixels du rectangle deviennent UN item, retirés de
                                   l'item qui les contenait (sprites collés sans aucun pixel transparent entre eux)
tools/sk cut ID 30                 personnages : l'item 30 commence une nouvelle entité (deux persos collés)
tools/sk name ID e3 vieil_homme    nomme un item ou une entité (sinon nom automatique)
tools/sk clear ID drop             efface une catégorie de corrections (drop|keep|merge|split|add|cut|names|erase|flood|all)
tools/sk zone ID x,y,w,h clé=val   zone de la feuille avec SES réglages (ex. layout=grid grid_pitch=16x32 frames=9)
tools/sk zone ID x,y,w,h skip      zone entièrement ignorée (crédits, captures, schémas)
tools/sk zone ID list | del N      voir / supprimer les zones
tools/sk suggest ID [--apply]      réglages des feuilles sœurs déjà validées (même jeu, même section)
tools/sk journal ID                historique de la feuille (qui a fait quoi, reprises, interruptions)
tools/sk entity ID 12 13 14 15     ces items, DANS CET ORDRE, forment UNE animation (retirés des autres entités)
tools/sk slice ID 22 2 [1]         coupe l'item 22 en 2 colonnes (x 1 rangée) égales : sprites collés sans
                                   pixel transparent (plus simple que carve, pas de coordonnées à calculer)
tools/sk setbox ID S2 x,y,w,h      rattache à l'ensemble S2 tous les sprites dont le centre est dans la boîte
tools/sk captions ID               planche « légende -> ensemble / animation » (pour nommer, voir plus bas)
tools/sk setname ID S3 fire_blast  nomme un ensemble (légende) ; « none » = cette ligne n'est pas une légende
tools/sk pixel ID x,y               couleur exacte d'un pixel de la feuille SOURCE (#RRGGBB)
tools/sk pixel ID x,y,w,h           couleurs d'un rectangle, de la plus fréquente à la moins (+ fond détecté)
tools/sk erase ID x,y,w,h [#RRGGBB ...] [--tol N] [--fill clear|near|LxH]
                                   GOMME : efface les pixels du rectangle (seulement ces couleurs si données).
                                   clear (défaut) = transparents ; near = remplacés par le fond voisin ;
                                   16x16 = motif de fond répété recopié (fond à motif sous un texte)
tools/sk flood ID x,y [--tol N]    rend transparente la région d'un seul tenant de la couleur de ce point
                                   (fond de panneau resté, tracé/arc dessiné, fond qui troue un sprite)
tools/sk check ID ETAPE ok|na "n"  confirme une étape obligatoire (voir « Étapes obligatoires »)
tools/sk status ID ok "note"       statut final : ok | needs_fix | skip   (ok REFUSÉ si une étape manque)
```

Les numéros d'items/entités viennent du **dernier** `sk run`. Après chaque correction, relance `sk run ID`
pour voir le nouveau résultat (les numéros peuvent changer, les corrections déjà faites restent valables).

## Étapes obligatoires (le statut ok est refusé sans elles)

Chaque feuille de sprites / personnages a 3 étapes à confirmer, chacune avec `tools/sk check ID ETAPE ok|na "note"` :
1. `decoupage` : chaque élément est entier, seul, sur fond transparent ; légendes, crédits et déchets jetés.
2. `regroupement` : les frames d'une même animation / d'un même personnage sont regroupées en ENTITÉS, et
   les éléments d'une même attaque / d'une même section de la feuille sont dans le même ENSEMBLE (sous-dossier).
   « na » seulement si la feuille ne contient que des objets indépendants sans animation (icônes, objets).
3. `nommage` : `tools/sk captions ID` ; si la feuille a des légendes (noms d'attaques, de persos, de sections),
   nomme chaque ensemble avec `sk setname ID Sn nom` et les entités importantes avec `sk name ID eN nom`
   (snake_case anglais : fire_blast, old_man_walk). « na » seulement s'il n'y a aucune légende exploitable.

Une confirmation porte sur l'état ACTUEL de la fiche : si tu changes un réglage ou une correction après
avoir confirmé une étape, elle devient caduque et `sk status ID ok` te dira de la refaire. Donc : corrige
tout, relance `sk run`, vérifie, PUIS confirme les 3 étapes, PUIS `sk status ID ok`.
Si une feuille t'arrive avec `decoupage` déjà confirmé (feuille validée avant cette règle), concentre-toi
sur le regroupement et le nommage — mais si tu modifies quoi que ce soit, reconfirme aussi le découpage.

## Ensembles (légendes) et animations

- `sets=captions` (réglage par défaut) : chaque légende de la feuille (« Ember », « Fire Blast », « Walking »...)
  ouvre un ENSEMBLE ; chaque segment de rangée rejoint la légende placée à sa gauche ou à sa droite sur la même
  rangée, sinon celle qui commence au-dessus de lui ; les fichiers vont dans un sous-dossier par ensemble. Vérifie sur `sk captions ID` que chaque ensemble contient
  bien les sprites de sa légende. Une ligne de texte qui n'est pas une légende (crédits du ripper, titre) :
  `sk setname ID Sn none`. Sans légende sur la feuille, il n'y a simplement pas d'ensemble.
- `group=anim` (défaut pour effets, monstres, persos Zelda) : dans chaque ensemble, les frames rangées en
  ligne forment une animation ; une ligne est coupée aux trous (`row_split_gap`) et là où la palette change
  nettement (`anim_split_sim`, 0.2 ; plus haut = coupe plus souvent). Deux animations collées : `cut`.
  Frames en colonne : `group=columns` ; blocs : `group=blocks` (voir plus bas).

## Décider sans bloquer

**Escalade** : si tu ne vois pas assez bien pour décider (sprites minuscules, couleurs proches, feuille très
dense), ou si après tes essais le résultat reste mauvais, mets `status ID needs_fix "ce qui coince précisément,
ce que tu as essayé"` : la feuille passe automatiquement à un modèle à meilleure vision, qui reprendra tes
corrections et lira ta note. Ne valide JAMAIS `ok` une feuille sans avoir regardé ses planches (c'est contrôlé).

Mais une simple hésitation ne justifie pas `needs_fix` : applique ces règles, note ton choix et conclus.
- Frames qui se ressemblent (même perso / même objet / même effet, même taille, couleurs proches), rangées
  ensemble → MÊME animation (`sk entity` si l'outil ne les a pas regroupées).
- États différents d'un même objet (coffre ouvert / fermé, bombe normale / allumée) → une entité par état
  s'il y a plusieurs frames, sinon items isolés : c'est acceptable.
- Sprite seul sans frame évidente qui lui correspond → item isolé : c'est acceptable.
- Petit fragment qui appartient visiblement à un sprite voisin (ombre, pointe, étincelle collée) → `merge`.
- Feuille énorme ou très mélangée : fais d'abord des zones par bloc évident ; si après 6 allers-retours le
  résultat reste mauvais, `needs_fix` en décrivant précisément les blocs restants.
- Légende rattachée au mauvais ensemble → `sk setbox` (ou `setname none` si ce n'est pas une légende).

## Les fichiers à regarder

Après `tools/sk run ID`, dans `rpg/pipeline/qa/ID/` :
- `overview_*.png` : la feuille source, fond retiré (damier = transparent), avec une boîte par item.
  - vert = sprite gardé, rouge = texte jeté, magenta = encadré jeté, orange = jeté à la main, gris = débris
  - bleu épais = entité (groupe de frames d'un même personnage), étiquette `eN` sous la boîte
  - le numéro au-dessus de chaque boîte est le numéro d'item à utiliser dans les commandes
- `results_*.png` : ce qui est réellement produit. Une ligne par entité (`eN`) ou une case par item.
  C'est **le plus important** : c'est ce que le joueur verra dans le jeu.

Lis d'abord le rapport texte. Ouvre les images pour vérifier. Si une zone est trop petite pour juger,
utilise `sk zoom`.

## Feuilles mixtes : les zones

Une feuille mélange souvent plusieurs mises en page (un bloc de persos en grille, des objets en vrac, des
effets en ligne, un encadré de crédits). Au lieu d'un compromis global, découpe-la en **zones** :
`sk zone ID x,y,w,h réglages...` (coordonnées de la feuille source, lisibles sur l'overview). Chaque zone
a ses propres réglages ; le reste de la feuille garde les réglages globaux. Les zones apparaissent en
cyan (`Z0`, `Z1`...) sur l'overview. Grille imposée : `grid_pitch=LxH` (et si besoin `grid_origin=x,y`,
le coin d'une case) ; si l'anomalie `grid_cuts` apparaît, le pas ou l'origine est faux.

Une zone peut aussi avoir **son propre fond** : `sk zone ID x,y,w,h bg=#RRGGBB bg_mode=edge peel=4 ...`
(le fond est alors retiré seulement dans ce rectangle). Utile quand une couleur sert de fond à un endroit
et de couleur de sprite ailleurs. Avec `bg_mode=edge`, seul le fond relié au bord DE LA ZONE est retiré.

Regroupement des personnages (`group=`) :
- `chunks` : frames en ligne, coupées par paquets de `frames` (Pokémon : 9 ou 3) ;
- `rows` : une ligne entière = un perso ;
- `columns` : frames en COLONNE (de haut en bas), paquets de `frames` ; `columns_all` = colonne entière ;
- `blocks` : blocs 2D de `entity_shape` cases (ex. `3x3`), frames lues `frame_order=row` (ligne par ligne)
  ou `col` ; pour un bloc 3x3 Pokémon (rangée 1 = poses, 2 = 1er pas, 3 = 2e pas) : `template=pokemon_ow9_grid` ;
- `palette` : feuilles en vrac (Zelda) : sprites proches qui partagent la même palette (`palette_sim`, `palette_dist`).
Combine avec les zones quand une feuille mélange plusieurs rangements.

## Ce qu'est un bon résultat

1. **Un élément = une chose entière.** Un objet, un meuble, une frame de personnage, une frame d'effet.
   - Pas coupé (une épée dont la lame est séparée du manche → `merge`)
   - Pas fusionné avec son voisin (deux persos dans une seule boîte → `split`, ou `set gap=0`)
2. **Fond entièrement transparent.** Aucun rectangle de couleur derrière les sprites dans `results_*.png`.
3. **Pas de déchets** : légendes, titres, noms des rippers, encadrés de crédit (« Ripped by… »), flèches,
   croix « inutilisé », cadres décoratifs, numéros → doivent être jetés (rouge/magenta/orange).
4. **Personnages (type characters)** : chaque entité = UN personnage, toutes ses frames, dans l'ordre de la
   feuille. Les frames sont alignées (pas de saut vertical en passant d'une frame à l'autre). Pokémon GBA :
   9 frames (face, dos, profil gauche, 2 pas face, 2 pas dos, 2 pas profil) ou 3 frames (poses fixes).
5. **Effets animés** (étincelles, explosions, attaques) : quand les frames d'une animation sont rangées en
   ligne, chaque animation doit devenir UNE entité (`set ID group=rows`, ou une zone `group=rows`), pas des
   dizaines d'items isolés. Les frames identiques (=d) sont normales dans une animation.
6. Un élément ne doit contenir **qu'un seul** objet : deux poupées, deux étincelles ou deux persos dans la même
   case de results = à séparer (`split`, `carve`), même s'il n'y a aucune anomalie dans le rapport.
7. Les petits éléments **légitimes** (étincelles, gouttes, particules d'effet) doivent être GARDÉS même
   s'ils sont signalés `[small]`. Ne jette que ce qui n'est clairement pas du contenu de jeu.

## Diagnostic → correction

| Symptôme | Correction |
|---|---|
| Fond coloré resté derrière les sprites (`bg_suspect`, rectangles de couleur dans results) | `set ID bg_tol=24`, ou forcer : `set ID bg=#RRGGBB` (couleur lue sur l'overview), ou `set ID peel=6` |
| Plusieurs fonds différents (cases colorées) mal retirés | `set ID peel=6 peel_min_area=120` |
| Effets sur fond noir (le noir reste) | `set ID black_bg=true` |
| Effet PLEIN ÉCRAN (météo : pluie, neige, sable…) rangé un écran par encadré, anomalie `pulverise` (des centaines de gouttes identiques) | `set ID panel_frames=true peel=0` : chaque encadré = une frame de la taille de l'écran, son fond transparent ; puis regrouper en animation |
| Sprites voisins fusionnés en grosse boîte (`[big]`) | si partout : `set ID gap=0` ; si un seul cas : `split ID n` |
| Sprite coupé en morceaux (bras, chapeau, ombre détachés) | si partout : `set ID gap=2` (ou 3) ; si un seul cas : `merge ID a b c` |
| Grand décor/objet légitime (maison, arbre) signalé `[big]` | rien, c'est normal |
| Légende/crédit/titre gardé en vert | `drop ID n ...` |
| Contenu réel jeté en rouge (pris pour du texte) | `keep ID n ...` ; si beaucoup : `set ID drop_text=false` puis `drop` les vraies légendes |
| Personnages : segment de mauvaise longueur (`row_count`) | regarder la zone ; si c'est du décor/texte : `drop` ; si un perso a un nombre de frames différent : `set ID frames_alt=[3,4]` ; si deux persos collés : `split` |
| Personnages : frames de deux persos mélangées dans une entité | `cut ID n` sur la 1re frame du 2e perso ; si c'est partout : `set ID row_split_gap=6` |
| Personnages : lignes mélangées (frames d'une ligne au-dessus) | `set ID row_tol=3` |
| Feuille de persos où chaque perso a ses frames en ligne mais pas 9 | `set ID group=rows` (une ligne = une entité) |
| Feuille d'objets/effets à ne pas regrouper | `set ID group=none` |
| Feuille entière inutile pour un jeu (écran titre, menu, carte du monde) | `status ID skip "raison"` |
| `mixed_entity` : une frame n'a pas les couleurs du reste de l'entité | deux persos mélangés : `cut ID n` sur la 1re frame du 2e |
| Capture d'écran / quadrillage / trait gardé, ou jeté à tort (jaune sur l'overview = déchet auto) | `drop` / `keep` |
| Texte du ripper COLLÉ à un sprite (« Run », « Background »...) que `drop` ne peut pas retirer | `sk pixel ID x,y,w,h` sur le texte pour lire sa couleur, puis `sk erase ID x,y,w,h #COULEUR` (rectangle serré autour du texte : la couleur est effacée PARTOUT dans le rectangle) ; texte posé sur un fond à motif : `--fill near` ou `--fill LxH` (période du motif) |
| Tracé / arc / trait dessiné par-dessus les sprites | couleur avec `sk pixel`, puis `sk flood ID x,y` sur le tracé (d'un seul tenant) ou `sk erase ID x,y,w,h #COULEUR` |
| Fond d'un panneau rectangulaire resté (couleur différente du fond général) | `sk flood ID x,y` sur un pixel de ce fond (le message donne la taille effacée : vérifie qu'elle correspond au panneau) |
| Couleur du fond retirée AUSSI dans un sprite (trou, ex. orbite) | `set ID bg=none` (ou `bg_mode=edge`), puis `sk flood ID x,y` sur le fond extérieur ; ou zone avec `bg_mode=edge` |
| Grille régulière mal découpée (cases coupant des sprites, `disposition` en grille/xycut) | `set ID layout=blobs` (sprite par sprite) |
| Sprites collés ou morceaux détachés partout alors que `disposition` dit « taches » | `set ID layout=grid` (force le découpage par cases) ; fragments plus éloignés : `set ID frag_gap=5` |

Paramètres disponibles (voir `sk show`) : `bg bg_tol bg_mode black_bg peel peel_min_area gap min_size min_area
drop_text text_max_h drop_junk layout block_gap grid_min_conf grid_pitch grid_origin frag_gap group frames frames_alt
entity_shape frame_order col_tol row_tol row_split_gap cell anchor template palette_sim palette_dist split_own`.

La ligne `disposition` du rapport dit comment chaque bloc a été découpé : `grille` (pas régulier), `xycut`
(feuille régulière assemblée à la main : sprites collés séparés, ombres/armes détachées rattachées), `taches`
(sprite par sprite).

## Méthode (pour chaque feuille)

1. `tools/sk run ID` → lis le rapport.
2. Ouvre `overview_0_0.png` (et les autres pages s'il y en a) puis `results_*.png`.
3. Corrige d'abord les problèmes **globaux** (paramètres), relance, puis les cas **isolés** (drop/merge/split).
4. Maximum ~6 allers-retours. Si ça ne converge pas, ou si la feuille a une mise en page que les outils ne
   savent pas gérer, mets `status ID needs_fix "explication précise de ce qui ne va pas"` et passe à la suite.
   Si c'est une **limite de l'outil** (un paramètre sans effet, un cas que rien ne permet de corriger), dis-le
   explicitement dans la note avec ce que tu as essayé et les chiffres : le développeur corrigera l'outil.
5. Quand c'est bon : confirme les 3 étapes (`sk check`), puis `tools/sk status ID ok "résumé en une phrase"`.
6. Nommer (`sk name`) seulement les éléments importants et évidents (perso principal, objets connus).
   Noms en snake_case anglais. Sinon laisse les noms automatiques.
7. Avant de commencer une feuille sans réglages, `sk suggest ID` : si des feuilles sœurs ont été
   validées, `sk suggest ID --apply` donne souvent le bon point de départ.

Statut `auto_ok` : feuille validée automatiquement (aucune anomalie) mais jamais vérifiée. Si on te
donne une feuille `auto_ok` ou un « échantillon de contrôle », vérifie-la normalement : `ok` si elle est
bonne (elle devient vérifiée), sinon corrige ou `needs_fix`.

Sur la planche results : `=m` = image miroir d'une autre (gauche/droite), `=d` = doublon exact. C'est
normal et utile (Godot retourne les sprites) : ne les jette pas.

## Règles

- Ne touche qu'aux feuilles qu'on t'a assignées (l'outil refuse les autres, et les commandes globales).
- Le statut se change UNIQUEMENT avec `tools/sk status` (`sk set ... status=` est refusé).
- Ne modifie aucun fichier à la main (ni code, ni JSON, ni PNG). Uniquement `tools/sk`.
- Ne lance pas de téléchargement, n'installe rien.
- Termine par un résumé : pour chaque ID, statut final et une ligne d'explication.


## Feuilles de CARTES (type map / tileset)

Une carte n'est pas découpée en sprites mais en tuiles de 16 px (24 pour Donjon Mystère) sur une grille.
Étapes obligatoires : `grille` et `reconstruction`.
1. `tools/sk run ID` : rapport des zones (une zone = une carte ou un morceau de la feuille) avec leur grille
   (`grille=(ox,oy)`), la confiance, et « <- grille peu sûre » si douteux. Planche `regions_*.png` : les
   lignes magenta de la grille doivent tomber ENTRE les tuiles (bords des arbres, des maisons, des meubles,
   des lattes de parquet), jamais au milieu d'un objet.
2. Zone douteuse : `tools/sk gridcheck ID zN` -> 4 décalages côte à côte (A, B, C, D) ; choisis celui dont la
   grille ne coupe pas les objets : `tools/sk region ID zN offset=OX,OY`.
3. Zone qui n'est PAS une carte (titre, cadre, légende, panneau de couleurs) : `tools/sk region ID zN skip`.
4. `tools/sk recon ID` : reconstruit chaque zone à partir de ses tuiles ; confirme seul l'étape
   `reconstruction` si >= 97 % ; sinon regarde `rpg/pipeline/qa/ID/recon_zN.png` (trous = tuiles perdues).
5. Quand toutes les zones sont bonnes : `tools/sk check ID grille ok "note"`, puis `tools/sk status ID ok`.
6. **Reconstruction < 97 % : ce n'est PAS forcément un échec.** Ce qui manque est souvent du DÉCOR posé
   par-dessus la carte hors grille (pieux, clôtures, fanions, torches, statues, portraits, bandeaux) ou un
   crédit du ripper : ces éléments sont extraits à part (objets des cartes), la carte n'a pas à les reproduire.
   - crédit / portrait / texte COLLÉ à une zone de carte : `tools/sk erase ID x,y,w,h` (rectangle serré) puis
     `tools/sk recon ID` (les pixels effacés ne comptent plus) ;
   - si les manques visibles sur recon_zN.png sont seulement du décor hors grille et que les tuiles de sol /
     murs sont reproduites : `tools/sk check ID reconstruction ok "N % ; manque = décor hors grille (…)"`.
   `needs_fix` seulement si les TUILES elles-mêmes sont fausses (grille qu'aucun décalage ne corrige, trous
   dans le sol ou les murs).


## Pages d'OBJETS (type objects, ids `obj_<jeu>_NN`)

Les objets de décor (buissons, arbres, rochers, tables, lits, panneaux, maisons…) sont extraits automatiquement
des cartes et rangés par pages de 40. Un bon objet se pose tel quel sur un AUTRE décor dans le jeu.
Étape obligatoire : `objets`.

```
tools/sk run ID                       reconstruit les objets du jeu + liste numérotée (#1..#40) + planches
tools/sk objdrop ID 3 7 12            jette des objets (numéros #N de la page) ; --undo pour annuler
tools/sk objsplit ID 7 0,0,2,2        découpe l'objet #7 : rectangle EN TUILES x,y,largeur,hauteur dans l'objet
                                      (lignes pointillées cyan = grille des tuiles) ; plusieurs rectangles possibles ;
                                      le reste forme d'autres morceaux, ajoutés EN FIN de page (nouveaux numéros)
tools/sk objsplit ID 7 undo           annule un découpage (l'objet #7 est marqué DÉCOUPÉ)
tools/sk set ID split_pieces=true     si un objet découpé DISPARAÎT de la page sans morceaux en fin de page
tools/sk objname ID 5 red_mailbox     nomme un objet (anglais, snake_case) : utile mais pas obligatoire
```

Planches `rpg/pipeline/qa/ID/objets_0.png`, `objets_1.png`… (10 objets par image, regarde-les TOUTES) : pour chaque objet, à gauche l'objet extrait sur
damier (transparent), à droite le même endroit dans la carte d'origine. Les numéros ne changent jamais sur une
page (un objet jeté reste à sa place, barré en rouge).

**Garder** : tout élément de décor qu'on pourrait poser ailleurs (même petit : fleur, caillou, pancarte, pot,
chaise, coffre, statue, porte, escalier, maison entière, arbre). L'ombre sombre/semi-transparente au pied fait
partie de l'objet : c'est voulu.
**Jeter** (`objdrop`) :
- texture de sol ou de terrain sans objet dessus (herbe, sable, eau, falaise, bord de falaise, rive, chemin,
  morceau de forêt dense), même trouée de damier ;
- texte, étiquette de nom de carte (« Petalburg Woods »), crédit du ripper, logo, capture d'écran ;
- bout de pièce inutilisable : bande de mur seule, coin de pièce, bord de tapis seul, morceau de plafond ;
- objet presque vide (quelques pixels) ou visiblement coupé par le bord de la carte.
**Ne jette JAMAIS un groupe qui contient un objet utile** (table, comptoir, lit, plante collés à un mur ou à du
sol) : DÉCOUPE-le (`objsplit`) pour garder l'objet utile, puis jette seulement les morceaux de mur/sol.
**Découper** (`objsplit`) : deux objets collés (meuble collé à un mur, deux maisons accolées, table + plante) :
garde chaque objet dans son rectangle, puis jette les morceaux inutiles (le mur) qui apparaissent en fin de page.
**Sol mal retiré** (gros paquet du sol d'origine resté autour de l'objet) : garde l'objet mais signale-le dans la
note de `check` (« #12 : sol resté à gauche ») ; c'est corrigé par l'outil, pas par toi.

Méthode : `sk run ID` → regarde chaque planche → une seule commande `objdrop` avec tous les numéros à jeter →
`objsplit` si besoin → `sk run ID` (OBLIGATOIRE après une correction : `check` est refusé sinon) → vérifie
les morceaux ajoutés en fin de page → `tools/sk check ID objets ok
"N gardés, N jetés, N découpés ; remarques"` → `tools/sk status ID ok`. Si la page est inutilisable (planche
illisible, outil cassé) : `tools/sk status ID needs_fix "raison précise"`.


## Tables de TERRAINS (type terrainset, Donjon Mystère)

Feuille = un tableau : colonne « Legend » puis des groupes de 3 colonnes (Walls, Wall Alt. 1, Wall Alt. 2,
Ground, Ground Alt., Water…). Chaque case de légende est un motif 3x3 : carré plein = voisin du MÊME terrain.
L'outil extrait chaque groupe en atlas de tuiles 24 px et décode les motifs (utilisés pour les terrains Godot).
Étape obligatoire : `terrains`.
1. `tools/sk run ID` : liste des groupes extraits avec leur nom et leur nombre de tuiles ; planche
   `terrains_0.png` : en haut l'EN-TÊTE d'origine (noms des colonnes), dessous chaque groupe extrait.
2. Les noms par défaut sont devinés d'après le nombre de groupes. Compare-les à l'en-tête, dans l'ordre. S'ils
   diffèrent : `tools/sk set ID pmd_groups='["walls","wall_alt_1","ground","water"]'` (snake_case, anglais, même
   nombre que de groupes extraits), puis `tools/sk run ID`.
   Le magenta (#FF00FF) est la transparence du ripper : la colonne « Water Sparkle » (reflets) devient un calque
   transparent avec quelques pixels clairs (normal) ; dans l'eau, les tirets magenta sont remplacés par la
   couleur voisine (normal). Nomme-la `water_sparkle`.
3. Vérifie que chaque groupe montre des tuiles entières (pas de morceaux de texte, de palette, de cadre) et que
   les petits motifs blancs à gauche ressemblent à la colonne Legend de l'en-tête.
4. `tools/sk check ID terrains ok "noms vérifiés : ..."` puis `tools/sk status ID ok`. Tableau non reconnu ou
   groupes mélangés : `tools/sk status ID needs_fix "raison"`.

## Décors Donjon Mystère (catégorie scenes, type sprites)

Une feuille « scenes » montre un DÉCOR PEINT (fond de hutte, de donjon, de plaine) et, à côté, ses animations
(torches, eau, bandes de ciel en plusieurs frames). Ce n'est pas une carte en tuiles. Méthode sprites normale :
- le grand décor reste UN seul item (anomalie [big] normale : ne le découpe pas) ; un trou rectangulaire vide
  dans le décor est normal (l'animation s'y place) ;
- chaque série de frames identiques en taille = une entité (`sk entity` ; frames collées : `sk slice`) ;
- crédits, titre de la feuille (« Beau Plains, Pokémon Mystery Dungeon… »), portraits : `sk drop` ou zone skip.


## Animations des personnages (pour Godot)

Chaque personnage qui marche doit finir avec des animations par direction : `idle_down`, `idle_up`,
`idle_left`, `walk_down`, `walk_up`, `walk_left` (la droite = la gauche retournée, inutile si absente).
- Feuille Pokémon rangée comme le gabarit (9 frames : 3 poses de face/dos/gauche puis 2 pas par direction) :
  `tools/sk set ID template=pokemon_ow9` (bloc 3x3 lu par lignes : `pokemon_ow9_grid` ; 3 poses seulement :
  `pokemon_ow3`).
- Sinon, entité par entité : `tools/sk anims ID e3 idle_down=0 walk_down=1,0,2,0 idle_up=3 walk_up=4,3,5,3
  idle_left=6 walk_left=7,6,8,6` (numéros = position de la frame DANS l'entité, 0 = la première ; regarde
  `results_*.png` pour savoir dans quel ordre sont les frames et vers où regarde le perso).
- Une entité qui n'est qu'UNE animation (Zelda : « link_walk_down ») : rien à faire si son nom le dit déjà.


## Pages de BORDS de terrains (type terrainpairs, ids `tp_<jeu>_NN`)

Un BORD est une tuile de transition entre deux sols (herbe → chemin, sable → eau, falaise → sol) : Godot s'en
sert pour dessiner automatiquement les bords quand on peint un terrain. L'outil les a trouvés tout seul ; il se
trompe parfois. Étape obligatoire : `bords`.
- `tools/sk run ID` : liste des paires (A / B) et planche `bords_0.png` : une rangée par paire = tuile pure A,
  tuile pure B, puis chaque bord numéroté #n avec à sa droite 9 petits carrés (rouge = cette partie de la tuile
  est du terrain A, bleu = du terrain B).
- **Jeter** (`tools/sk tdrop ID 4 9 12`) : tout ce qui n'est PAS une transition entre A et B : meuble, flèche,
  objet posé sur le sol, texte, motif sans rapport, tuile où les carrés rouges/bleus sont manifestement faux.
- **Nommer** les terrains (anglais, snake_case : grass, tall_grass, sand, path, water, cliff, wood_floor…) :
  `tools/sk tname ID 12 sand` (id affiché dans la liste).
- `tools/sk run ID` → `tools/sk check ID bords ok "N gardés, N jetés"` → `tools/sk status ID ok`. Une paire
  entièrement fausse (deux terrains qui ne se touchent jamais vraiment) : jette tous ses bords, c'est normal.
