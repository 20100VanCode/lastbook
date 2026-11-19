# RELIQUE — adapter Lastbook à la France et aux DOM-TOM

Plan de la déclinaison française du fork `20100VanCode/lastbook`.
Branche de travail : `relique-fr` (syncable avec `Immortal-Protocols/lastbook`).

---

## 0. Résumé d'étape — 19 nov. 2026

| Jalon | Statut | Livré |
|---|---|---|
| **J1** Marque + UI | **fait** | RELIQUE (fiche, logo SVG/PNG/favicon), palette par jetons, UI 100 % française, rendu vérifié |
| **J2a** Identifiants | **fait** | 101 départements + 18 régions ; règle `FR-…` acceptée dans manifest et switch |
| **J2b** Adresses | **fait** | BAN : normalisateur + recherche français, rappel **100 %** mesuré ; index par département |
| **J2b** Carte | **fait** | `national.sqlite` depuis Geofabrik (shapefiles DROM, **GeoPackage** métropole) borné à l'emprise BAN du département |
| **J2b** Couches IGN | **fait** | BD ALTI (terrain), BD TOPO (noms d'eau, lieux-dits) en shapefiles **et** GPKG 3.5 ; bâtiments BD TOPO → vue 3D |
| **J2b** RPG + unités | **fait** | `crops.sqlite` (vignoble, vergers, petits fruits) + overlay z7-13 ; échelle, courbes et altitude en **mètres** partout |
| **J3** Contenus | **en cours** | **6 sujets français** (`eau`, `assainissement`, `alimentation`, `catastrophe`, `abri`, `energie`), 18 documents sources, **180 références vérifiées** |
| **J4** Site + packs | **en cours** | **59 packs** au 19 nov. (5 DROM complets, 54 métropolitains), relus par `install.check_zip` + `check_map` |

- **Tests** : 338, dont 2 échecs PDF préexistants (identiques sur `main` propre).
- **Branche** : `relique-fr`, poussée sur `20100VanCode/lastbook` ; `main` reste le miroir upstream.
- **Chaîne** : `tools/build_all_fr.py` (7 étapes par département, reprise, cache avec reprise `Range`),
  sources résolues par `tools/ign_feed.py`.
- **Contenu** : `content-fr/` (manifestes + documents + sujets), `content-fr/build.py` assemble et
  indexe une bibliothèque d'essai, `validate_topics.py` vérifie chaque page citée.
- **Stockage** : dépôt + 55 Go de données sur `/Volumes/EXTRADATA/RELIQUE` (disque externe, exFAT).
- **Prochain** : J3 — `catastrophe` (cyclone, Météo-France / sécurité civile), puis `abri`, `énergie`,
  `soins`, `blessures` ; et reprise du lot métropolitain (47 restants).

---

## 1. Intention

Lastbook est une **bibliothèque de survie hors-ligne** : manuels, vidéos, encyclopédies,
carte et guides pratiques sur un seul ordinateur, qui fonctionne quand l'internet et le
téléphone tombent. La version d'origine est écrite pour les États-Unis : cartes par État,
adresses US, sources FEMA/CDC, interface anglais.

**RELIQUE** reprend la même architecture et la replace dans le contexte français :
**France métropolitaine + les 5 régions d'outre-mer (Guadeloupe, Martinique, Guyane,
La Réunion, Mayotte)**, en français, avec des sources françaises et les cartes des régions
françaises.

L'ambition VAN CODE s'applique : un objet fait pour **survivre à son créateur**. Ici,
c'est une bibliothèque faite pour survivre à la panne.

---

## 2. État des lieux du fork

| Ce qui existe | Ce qui bloque pour la France |
|---|---|
| Appli desktop Mac/Win/Linux + iPad, 100 % hors-ligne, aucun port réseau | — |
| Guides curatés `content/topics/*.json` (14 besoins) | rédigés autour de sources US (FEMA, CDC, USDA) |
| Cartes par « state » : boîte, couches, index d'adresses | `STATE_CODES` = 50 États US ; `[A-Z]{2}` impose des codes à 2 lettres |
| Recherche d'adresses US (Overture, ZIP) | la BAN écrit les adresses autrement (code postal avant commune, accents, *bis/ter*) |
| UI anglais dans `web/` | tout est à traduire |
| Site `website-next/` | anglais, produits US |
| **`docs/REGIONS-FR.md` + `docs/regions-fr-proposed.json`** | **déjà une proposition complète : 18 régions, sources IGN/BAN/RPG, licences, essai de build 3 départements** |

Le point important : **la recherche cartographique France existe déjà dans le dépôt**,
sous forme de proposition vérifiée (17 nov. 2026). Elle n'attend que des codes.

---

## 3. Décisions prises

- **Nom** : RELIQUE — « Le savoir qui survit. » (confirmé)
- **J1** : marque + coquille française — **fait**
- **Cartographie** : l'unité de découpe est le **département** (101) ; les 18 régions
  servent de regroupement et d'entrée dans l'écran de configuration.
- **Fork** : branche `relique-fr`, syncable avec `Immortal-Protocols/lastbook`. `main`
  reste un miroir propre de l'upstream. Les identifiants internes (`lastbook:`,
  `downloads.lastbook.org`, `X-Lastbook-Key`) ne sont pas renommés.
- **Contraintes non négociables** (héritées du projet) : hors-ligne après installation,
  pas de police web dans l'app, pas de réseau hors setup, sources de cartes sous
  licence ouverte, aucun lieu ni mot de la maison dans les fichiers livrés.

---

## 4. Jalons

### J1 — Marque + coquille française _(fait)_
- [x] Fiche de marque RELIQUE (palette, typo, texture, ton, logo)
- [x] Logo SVG + icônes 192/512 + favicon + manifest
- [x] `lang="fr"`, titre, méta, thème
- [x] Navigation : Vidéos · Carte · Chat · Guides · À propos
- [x] Écran de configuration (`setup.html`/`setup.js`) en français
- [x] À propos, recherche, listes, états vides, chat, carte en français
- [x] Tests du dépôt au vert + vérification visuelle en local

### J2 — Géographie France + DOM-TOM _(en cours)_
- [x] Unité de découpe : **département** (101) — `engine/departements.py` ; les 18 régions restent le regroupement
- [x] Codes : `FR-01`…`FR-95`, `FR-2A`/`FR-2B`, `FR-971`…`FR-976` — `engine/regions.py`
- [x] Assouplir la règle `[A-Z]{2}` (manifest + install) sans casser les index US
- [ ] Boîtes de découpe par département (ADMIN EXPRESS / IGN) — table en place, découpe à écrire
- [x] Recherche d'adresses à la française (BAN, accents, *bis/ter*, communes nouvelles)
      — `engine/address_search.py` + `tools/build_addresses_fr.py` ; **rappel mesuré
      100 % sur 400 adresses réelles de Martinique × 5 variantes**
- [x] Couche OSM (routes, eau, terres, bâtiments, lieux, POI) — `tools/build_map_fr.py`
      depuis les shapefiles Geofabrik ; **Martinique : 317 074 traits, 1 015 POI,
      rendu vérifié dans l'appli** (crédit OSM, date du build, bouton « France »)
- [x] Terrain BD ALTI 25 m — `tools/build_terrain_fr.py` (grilles UTM → WGS84,
      tuiles relief z4-12) ; **Martinique : 57 tuiles, rendu vérifié dans l'appli**
- [x] Noms d'après BD TOPO — `tools/build_topo_fr.py` (lieux-dits, cours d'eau) ;
      **Martinique : 2 710 lieux-dits, 87 cours d'eau**, étiquettes vérifiées à l'écran
- [x] Bâtiments BD TOPO avec hauteurs — `tools/build_bldg_fr.py` → `buildings.sqlite`
      (table `bldg_osm`, même format que `build_osm_heights.py`) ;
      **Martinique : 151 380 bâtiments, 250 tuiles z14**, vue 3D vérifiée
      (2 641 bâtiments affichés avec hauteurs mesurées)
- [x] RPG (parcelles) — `tools/build_crops_fr.py` : GPKG régional → `crops.sqlite`
      (cellules cliquables + overlay z7-13) ; Corse : 4 692 parcelles, 317 tuiles
- [x] Unités métriques à l'affichage — échelle en km/m, courbes en mètres,
      altitude en mètres (vue 3D et carte 2D)
- [ ] Projections : Lambert-93 métropole, UTM + datums locaux pour la Corse et les DROM
- [x] Build complet d'un département (Martinique `FR-972`) + pack —
      `tools/build_pack_fr.py` : carte 24,4 Mo compressés / 64,3 Mo installés,
      adresses 7,1 Mo / 21,2 Mo ; vérifié par `install.check_zip` + `check_map`,
      installé dans une bibliothèque hôte, puis servi par l'appli (carte + adresse
      BAN placée à l'écran)
- [x] Crédit et date de la carte selon les données chargées (fini la liste US en dur)

### J3 — Contenus français _(en cours)_
- [x] **Pilote** : `content-fr/` — manifestes + documents sources + sujets, `build.py`
      assemble une bibliothèque d'essai et l'indexe ; `validate_topics.py` vérifie chaque page
- [x] Sujet **`eau`** — « De l'eau potable sûre » : 8 situations, 7 limites, 37 références
- [x] Sujet **`assainissement`** — « Évacuer les excréments sans risque » : 5 situations,
      5 limites, 24 références
- [x] Sujet **`alimentation`** — « Nourriture sûre et chaîne du froid » : 6 situations,
      5 limites, 25 références
- [x] Sujet **`catastrophe`** — « Cyclone : se préparer, se confiner, revenir » : 6 situations,
      6 limites, 31 références (MRN, ORSEC 974, Géorisques)
- [x] Sujet **`abri`** — « Se mettre à l'abri et être hébergé » : 6 situations, 6 limites,
      32 références (info.gouv, PCS, DICRIM)
- [x] Sujet **`energie`** — « Électricité, gaz, monoxyde : éviter l'accident » : 6 situations,
      6 limites, 31 références (SPF, Enedis, RTE)
- [ ] Sources françaises : SPF, ANS/AMELI, Croix-Rouge, MSF, FNOR, Secourisme, Préfectures,
      Météo-France, BRGM, Santé publique France, INSEE
      *(acquis : ORSEC/Préfecture de l'Ain, FICR, HCSP, SIDESA-IODE, OMS/WEDC,
      Croix-Rouge française, Anses, ARS/DDETSPP, MRN, ORSEC 974, Géorisques,
      info.gouv/SGDSN, PCS, DICRIM, Santé publique France, Enedis, RTE)*
- [ ] Risques France/DROM : cyclone, tsunami, séisme, éruption, dengue/chikungunya,
      canicule, inondation, feu de forêt, neige/verglas, accident industriel
- [ ] Encyclopédies ZIM francophones (Wikipédia, Wikisource, Wiktionnaire)
- [ ] Vidéos francophones sous-titrées
- [ ] `content/gaps.json` français

### J4 — Site, packs, distribution
- [x] Pack d'un département (carte + adresses), vérifié et installable par setup
- [ ] Site vitrine français (landing, téléchargements, crédits)
- [ ] Packs Small/Medium/All France + cartes par région
- [ ] Manifest, sums, hébergement des téléchargements
- [ ] Builds Mac/Win/Linux signés

---

## 5. Géographie : le plan de bataille

Le document `docs/REGIONS-FR.md` fait foi. Résumé :

- **18 régions** (13 métropolitaines + Corse + 5 DROM) ; la carte détaillée est découpée
  par **département** (101), et non par boîte, pour éviter de ramener des lignes étrangères.
  L'écran de configuration propose les régions pour atteindre leurs départements.
- **Sources** : BD ALTI (terrain), BD TOPO (eau, bâtiments, lieux), RPG (parcelles),
  BAN (adresses), OSM (POI de base), ROE (barrages), Géo'DAE (défibrillateurs),
  répertoire éducation, stations-service, gendarmeries.
- **Licences** : Licence Ouverte 2.0 (Etalab/IGN/INSEE/BAN/Sandre) + ODbL (OSM) ;
  attribution « Source : …, date de dernière mise à jour ».
- **Adresses** : BAN, un CSV par département ; `code_insee` pour découper (pas le code postal).
- **Projections** : Lambert-93 en métropole ; UTM 20/GUAD88 (Guadeloupe), UTM 40 Sud/REUN89
  (La Réunion), etc. À écrire dans les outils.
- **Essai déjà mesuré** (3 départements, 414 Mo sur disque, ~209 Mo gzip) : 28/28 requêtes
  d'adresses trouvées avec le moteur français, 1/28 avec le moteur US.

## 6. Contenu : sources françaises de référence

| Besoin | Sources privilégiées |
|---|---|
| Secours / blessures | Croix-Rouge française, MSF, FNOR, « secourisme » du ministère |
| Eau / assainissement | SPF, OMS, préfectures, ARS |
| Nourriture / conservation | ANS/AMELI, DGCCRF, instituts techniques |
| Risques | Météo-France, BRGM, Schweitzer, préfectures, ORSEC |
| Santé | Santé publique France, AMELI, OMS, MSF |
| Énergie / électricité | RTE, Enedis, DGE |
| Terre / eau / agriculture | IGN, Agreste, Chambres d'agriculture |

Règle héritée : les guides **décrivent** ce que dit la source, ne prescivent pas ;
les limites et les « quand appeler à l'aide » restent cités.

## 7. Ce qui reste ouvert

- Table/licence : une table par licence, ou fusion OSM + Licence Ouverte sous ODbL.
- Unités : colonnes métriques (`height_m`, `area_ha`) ou conversion à l'affichage.
- Lecteur IGN : BD ALTI / BD TOPO / RPG.
- Projections d'outre-mer : UTM + datums locaux à écrire dans les outils.
- Le pack d'un département (terrain, eau, bâtiments, parcelles, adresses) reste à assembler.
- Financement / hébergement des packs (hors dépôt).

---

## 8. Journal

**18 nov. 2026**
- J1 : marque RELIQUE (fiche, logo, jetons) + UI 100 % française. 330 tests, 2 échecs
  PDF préexistants (pypdfium2 vendored hors path, identiques sur `main`).
- J2a : 101 départements + 18 régions ; règle d'identifiant `FR-…` acceptée dans le
  manifest et le switch.
- J2b (adresses) : BAN Martinique, 138 230 adresses indexées ; normalisateur et
  recherche français ; **rappel 100 %** sur 400 adresses × 5 variantes.
- J2b (carte) : `tools/build_map_fr.py` (shapefiles Geofabrik → `national.sqlite`) ;
  **Martinique : 317 074 traits, 1 015 POI**, rendu vérifié dans l'appli. Crédit et
  date de la carte désormais issus des données chargées.
- J2b (terrain) : `tools/build_terrain_fr.py` (BD ALTI 25 m, UTM → WGS84) ;
  **Martinique : 57 tuiles relief z4-12**, rendu vérifié (ombrage + courbes).
- J2b (noms BD TOPO) : `tools/build_topo_fr.py` (BD TOPO 3.0, 53 couches → fusion dans
  `national.sqlite`) ; **Martinique : 2 710 lieux-dits + 87 cours d'eau**, étiquettes
  vérifiées à l'écran. Trois pièges corrigés : table `poi` à recopier, parseur WKB
  multi-anneaux, géométries 3D (`ST_Force2D`).
- J2b/J4 (pack) : `tools/build_pack_fr.py` assemble le map set (`map-set.json` +
  `national.sqlite` + `terrain.sqlite` + statut) et l'index d'adresses, les vérifie
  comme setup (`install.check_zip` + `check_map`), et écrit le fragment de manifest.
  **Martinique : carte 19,7 Mo / 59,3 Mo installés, adresses 7,1 Mo / 21,2 Mo.**
  Vérifié bout-en-bout : pack installé dans une bibliothèque hôte, l'appli sert la
  carte et place une adresse BAN à l'écran.
- J2b (bâtiments) : `tools/build_bldg_fr.py` (BD TOPO `BATIMENT.HAUTEUR` →
  `buildings.sqlite`/`bldg_osm`) ; **Martinique : 151 380 bâtiments**, la vue 3D
  extrude 2 641 bâtiments avec hauteurs mesurées. `build_pack_fr.py` embarque
  `buildings.sqlite` (pack 24,4 Mo / 64,3 Mo installés).
- J1 (terrain3d.js) : la vue 3D était encore en anglais et en pieds — libellés
  français, altitudes en mètres, source des hauteurs dite « BD TOPO ».
- Lot 101 (18 nov., après 14 h) : `tools/ign_feed.py` résout les adresses IGN
  (**BD TOPO 99 départements + 18 régions, BD ALTI 104**) ; `tools/build_all_fr.py`
  enchaîne les 6 étapes avec reprise. **44 packs faits en 4 h 45**, ~6,5 min par
  département, aucun échec. Sources : BAN (data.gouv), Geofabrik (DROM en shapefiles,
  métropole en **GeoPackage** par ancienne région), IGN BD ALTI + BD TOPO (3.0 en
  shapefiles, **3.5 en GPKG** — 76 départements). Cinq départements (53, 54, 55,
  56, 57) n'ont pas d'édition départementale : on découpe l'édition régionale à
  l'emprise BAN.
- Coût observé : pack métropolitain **100 à 180 Mo** (453-467 Mo installés),
  DROM 25 à 123 Mo ; cache stable à ~3 Go (extractions supprimées au fil de l'eau),
  ~15 Go de packs et ~40 Go de travail au total.
- **J2b RPG** : `tools/build_crops_fr.py` (RPG 4.0, un GPKG par région ; groupe 21 =
  vignoble, 20/23 = vergers, FRA/FLA/FLP = petits fruits) → `crops.sqlite` et
  overlay coloré z7-13. Corse : 4 692 parcelles.
- **Unités** : échelle en km/m, courbes et altitude en mètres, partout (2D et 3D).
- **J3b pilote « eau »** : `content-fr/` — 4 sources officielles françaises
  (ORSEC Ain, manuel Croix-Rouge, avis HCSP, doctrine IODE), sujet rédigé en
  français, 37 références vérifiées par `validate_topics.py`, bibliothèque
  d'essai indexée par `content-fr/build.py`.
- Prochaine étape : J3 — les 13 autres besoins (assainissement, alimentation,
  abri, énergie, soins, blessures, communications, terrain…) sur les mêmes
  sources françaises.

**19 nov. 2026**
- **Stockage** : dépôt + `data/{cache,work,packs,ign}` (55 Go) déplacés sur
  `/Volumes/EXTRADATA/RELIQUE` ; disque interne libéré (183 Go). Un débranchement
  accidentel du volume exFAT a fait paniquer le montage — donnée intacte.
- **Lot 101** : **59 packs** (5 DROM complets avec noms BD TOPO + cultures, 54
  métropolitains), 0 échec. Correctif : l'étape « noms BD TOPO » se déclenche
  désormais sur `meta.topo`, pas sur « la carte vient d'être reconstruite ».
- **J3 (contenu)** : `content-fr/` — `build.py` assemble `library-data/` depuis
  manifestes + documents, indexe avec `engine/library.py`, puis valide les sujets
  avec `validate_topics.py`. **8 documents, 221 pages indexées.**
  - `eau` : ORSEC Préfecture de l'Ain (2024), manuel FICR, avis HCSP (2023),
    doctrine IODE — 37 références.
  - `assainissement` : fiches OMS/WEDC (2013) + guide latrines Croix-Rouge
    française (2018) — 24 références.
  - `alimentation` : fiche hygiène domestique **Anses** (récupérée par `fetch`
    dans le navigateur : ANSES bloque `curl`) + fiche ARS/DDETSPP sur les
    coupures de courant — 25 références.
  - **86 références, 0 erreur**, chaque page citée lue et vérifiée.
- Prochaine étape : J3 — `catastrophe` (cyclone, Météo-France, sécurité civile),
  puis `abri`, `énergie`, `soins`, `blessures`. Reprise du lot métropolitain
  (47 restants) ensuite.
