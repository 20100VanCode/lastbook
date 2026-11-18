# RELIQUE — adapter Lastbook à la France et aux DOM-TOM

Plan de la déclinaison française du fork `20100VanCode/lastbook`.
Branche de travail : `relique-fr` (syncable avec `Immortal-Protocols/lastbook`).

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

- **Nom** : RELIQUE — « Le savoir qui survit. » (proposition, modifiable)
- **Jalon 1** : marque + coquille française (identité, UI, navigation, écrans, ton)
- **Fork** : on reste syncable — branche `relique-fr`, les renoms de marque sont faits
  dans `web/` et `content/`, les identifiants internes (`lastbook:`, `downloads.lastbook.org`,
  `X-Lastbook-Key`) restent en place au jalon 1 pour ne pas casser le bridge et les tests.
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

### J2 — Géographie France + DOM-TOM
- [x] Codes région : `FR-ARA` … `FR-PAC`, `FR-20R`, `FR-971`…`FR-976` (18 régions) — `engine/regions.py`
- [x] Assouplir la règle `[A-Z]{2}` (manifest + install) sans casser les index US
- [ ] Boîtes de découpe par région (BASE ADMIN EXPRESS / IGN) — table en place, découpe à écrire
- [ ] Couches : terrain BD ALTI, eau BD TOPO + ROE, bâtiments BD TOPO, lieux BD TOPO/COG,
      parcelles RPG, adresses BAN, POI OSM + listes nationales
- [ ] Projections : Lambert-93 métropole, UTM + datums locaux pour la Corse et les DROM
- [ ] Recherche d'adresses à la française (BAN, accents, *bis/ter*, communes nouvelles)
- [ ] Build d'essai d'une région (Martinique `FR-972`, 34 communes) + vérification
- [ ] Crédits et licences par source et par date

### J3 — Contenus français
- [ ] Traduire et replacer les 14 sujets (clé, eau, nourriture, énergie, abri, santé,
      blessures, assainissement, communication, terre, réparation, conservation, cicatrisation)
- [ ] Sources françaises : SPF, ANS/AMELI, Croix-Rouge, MSF, FNOR, Secourisme, Préfectures,
      Météo-France, BRGM, Santé publique France, INSEE
- [ ] Risques France/DROM : cyclone, tsunami, séisme, éruption, dengue/chikungunya,
      canicule, inondation, feu de forêt, neige/verglas, accident industriel
- [ ] Encyclopédies ZIM francophones (Wikipédia, Wikisource, Wiktionnaire)
- [ ] Vidéos francophones sous-titrées
- [ ] `content/gaps.json` français

### J4 — Site, packs, distribution
- [ ] Site vitrine français (landing, téléchargements, crédits)
- [ ] Packs Small/Medium/All France + cartes par région
- [ ] Manifest, sums, hébergement des téléchargements
- [ ] Builds Mac/Win/Linux signés

---

## 5. Géographie : le plan de bataille

Le document `docs/REGIONS-FR.md` fait foi. Résumé :

- **18 régions**, une par région (13 métropolitaines + Corse + 5 DROM), découpées par
  **départements** (101) et non par boîte, pour éviter de ramener des lignes étrangères.
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

- Nom définitif (RELIQUE est une proposition).
- Codes région : accepter `FR-XXX` dans le manifest, ou passer par les départements.
- Coupe des couches : par départements (recommandé) ou par boîte.
- Table/licence : une table par licence, ou fusion OSM + Licence Ouverte sous ODbL.
- Unités : colonnes métriques (`height_m`, `area_ha`) ou conversion à l'affichage.
- Financement / hébergement des packs (hors dépôt).
