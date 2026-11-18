# RELIQUE — fiche de marque

Déclinaison de l'identité **VAN CODE** (monochrome, tramage, rétro-technique, typographie
sans empattement) appliquée à une bibliothèque de survie hors-ligne.

---

## Nom

**RELIQUE**
Baseline : **« Le savoir qui survit. »**
Sous-titre : *Bibliothèque hors-ligne — France & DOM-TOM.*

Un objet précieux, fini, fait pour traverser le temps et survivre à qui le possède.
La version knowledge : une bibliothèque qui fonctionne quand tout le reste tombe.

## Ton

- Direct, factuel, sans alarmisme.
- On dit ce qui marche, ce qui ne marche pas, et on cite la source.
- Pas de superlatif, pas d'emoji, pas d'orange.
- Phrases courtes. Verbes d'action. Le « vous » n'est pas utilisé : on s'adresse à la
  personne sans familiarité (« allez à… », « choisissez… », « le guide indique… »).

## Palette

| Rôle | Clair | Foncé | Hex |
|---|---|---|---|
| Encre | `papier` | `fond` | `#111111` |
| Papier | | | `#f2efe7` |
| Fond (foncé) | | | `#141414` |
| Texte secondaire | `#5c5c56` | `#a9a79e` | |
| Ligne | `#d9d5c9` | `#33322e` | |
| Accent (secours) | `#8a2b1f` | `#c24a3a` | brique/oxblood |
| Accord (carte) | `#2f4f47` | `#4f7a6e` | ardoise verte |

Une seule marque d'accent : le brique. L'ardoise verte sert uniquement la cartographie.

## Texture et forme

- **Tramage** : dégradés rendus en trame de points (halftone), jamais en dégradé lisse.
- **Grille** : pas de 8 px, lignes 1 px, coins 2–4 px, aucune ombre portée.
- **Séparateurs** : filet 1 px + bande tramée.
- **Motif signature** : le cercle tramé (la « relique ») et la croix de coordonnées.

## Typographie

L'appli est hors-ligne et **ne charge aucune police web** (contrainte du projet) :

- App : pile système — `system-ui`, `SF Pro`, `Segoe UI` ; titres en majuscules,
  `letter-spacing` serré, graisse 650 ; chiffres tabulaires.
- Site web (hors app) : **Space Grotesk** (préférence VAN CODE), fallback système.

## Logo

- **Marque** : un carré encre, un cercle tramé (halftone) et, au centre, un livre ouvert
  blanc surmonté d'un point — la carte, l'archive et le nœud hors-ligne.
- **Variantes** : `icon.svg` (couleur), `icon-192.png`, `icon-512.png`, `favicon.svg`.
- **Zone de protection** : 1/4 de la largeur du cercle, tout autour.
- **Interdits** : dégradé lisse, ombre portée, contour extérieur, inversion sur fond tramé.

## Application à l'app

Les jetons sont dans `web/app.css` (`:root`) : `--brand`, `--accent`, `--logo`,
`--ink`, `--paper`, `--line`. Le logo est `web/icon.svg`. Le mot « RELIQUE » remplace
« Lastbook » dans les chaînes visibles uniquement.
