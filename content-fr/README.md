# content-fr — guides curatés en français

Contenu francophone pour RELIQUE. Même modèle que `content/topics/` (voir
`content/SCHEMA.md`), mais les sources sont des documents officiels français ou
francophones, cités par leur page réelle.

## Sujets

| sujet | situations | limites | préparation | approfondissement | références |
|---|---|---|---|---|---|
| `eau` — De l'eau potable sûre | 8 | 7 | 4 | 4 | 37 |
| `assainissement` — Évacuer les excréments sans risque | 5 | 5 | 3 | 3 | 24 |
| `alimentation` — Nourriture sûre et chaîne du froid | 6 | 5 | 3 | 3 | 25 |
| `catastrophe` — Cyclone : se préparer, se confiner, revenir | 6 | 6 | 4 | 3 | 31 |
| `abri` — Se mettre à l'abri et être hébergé | 6 | 6 | 4 | 4 | 32 |
| `energie` — Électricité, gaz, monoxyde : éviter l'accident | 6 | 6 | 4 | 4 | 31 |
| `soins` — Premiers secours et trousse d'urgence | 5 | 5 | 3 | 2 | 24 |
| `blessures` — Plaies, brûlures, hémorragies : faire face | 5 | 5 | 3 | 3 | 24 |
| `communications` — Alerter, être alerté, rester informé | 6 | 5 | 4 | 4 | 30 |
| `sante` — Soigner au quotidien, éviter l'aggravation | 6 | 5 | 3 | 4 | 29 |
| `reparation` — Réparer, mettre hors d'eau, déclarer | 5 | 5 | 3 | 3 | 26 |
| `terrain` — Connaître son terrain et ses risques | 6 | 5 | 3 | 3 | 28 |

**341 références vérifiées** par `validate_topics.py` (0 erreur), chaque page lue.

Documents sources (`documents/`, manifeste `manifests/eau.json`) :

| id | document | éditeur | pages |
|---|---|---|---|
| `orsec-eau-ain` | ORSEC — Mode d'action « Eau potable » | Préfecture de l'Ain, 2024 | 49 |
| `ficr-hwts` | Traitement et stockage sûr de l'eau à domicile | Fédération internationale de la Croix-Rouge | 44 |
| `hcsp-comprimes` | Avis sur les comprimés désinfectants (Mayotte) | HCSP, 2023 | 10 |
| `iode-territoriale` | Déclinaison territoriale de la doctrine IODE | SIDESA | 33 |
| `oms-fiches-eha` | Fiches techniques eau, hygiène et assainissement | OMS / WEDC, 2013 | 64 |
| `crf-latrines` | Latrines en situation d'urgence (montage ERU) | Croix-Rouge française, 2018 | 15 |
| `anses-hygiene` | Hygiène domestique | Anses, 2013 | 5 |
| `ars-coupures` | Coupures de courant : réfrigérateur, congélateur | ARS / DDETSPP | 1 |
| `mrn-cyclone` | Mémento pratique du particulier — risque cyclonique | MRN, 2005 | 20 |
| `orsec-reunion-cyclone` | ORSEC 974 — dispositif spécifique cyclones | Préfecture de La Réunion, 2014 | 98 |
| `georisques-cyclone` | Consignes à la population — risque cyclonique | Géorisques | 1 |
| `tous-responsables` | Tous responsables — face aux risques, agissons | info.gouv / SGDSN | 15 |
| `pcs66` | Canevas de Plan Communal de Sauvegarde | Préfecture des Pyrénées-Orientales | 53 |
| `dicrim-rochefort` | DICRIM — consignes de sécurité | Ville de Rochefort | 12 |
| `spf-monoxyde` | Intoxications au monoxyde de carbone (infographie) | Santé publique France | 1 |
| `spf-monoxyde-page` | Intoxications au CO — les bons gestes | Santé publique France | page web |
| `enedis-coupure` | Je n'ai plus d'électricité : les bons gestes | Enedis | page web |
| `rte-bons-reflexes` | Tension, attention — près des ouvrages électriques | RTE / Enedis, 2026 | 2 |
| `kit72h` | Votre kit d'urgence 72 h | Géorisques | 1 |
| `crf-*` | Gestes de premiers secours (étapes, PLS, étouffement, arrêt cardiaque, hémorragie, brûlure) | Croix-Rouge française | 6 pages web |
| `service-public-numeros` | Les numéros en cas d'urgence et d'écoute | Service-Public / DILA | page web |
| `masecurite-numeros` | Les numéros utiles nationaux | Ministère de l'Intérieur | page web |
| `fr-alert` | FR-Alert — alerte et information des populations | Ministère de l'Intérieur | page web |
| `ars-gastro` | Recommandations en cas de gastro-entérite | ARS de Mayotte | 2 |
| `spf-chaleur-enfant` | Fortes chaleurs et enfant — repères | Santé publique France | 4 |
| `ameli-medicaments` | Médicaments et fortes chaleurs | Assurance Maladie | page web |
| `mrn-tempetes` | Mémento pratique du particulier — risque tempêtes | MRN, 2005 | 19 |
| `sp-degat-eaux` | Assurance dégâts des eaux | Service-Public / DILA | 5 |
| `mrn-inondations` | Mémento pratique du particulier — inondations | MRN, 2005 | 20 |
| `mrn-mvt` | Mémento pratique du particulier — mouvements de terrain | MRN, 2005 | 21 |
| `dicrim-bergheim` | DICRIM — risques majeurs (inondation, mvt, TMD, séisme) | Ville de Bergheim / Géorisques | 63 |

## Reconstruire

```
python3 content-fr/build.py --out /vers/lastbook-fr
```

Assemble `<out>/library-data/` (documents + manifeste), indexe le texte avec
`engine/library.py build`, puis valide `topics/*.json`. Pour lire une page :

```
LASTBOOK_DATA=/vers/lastbook-fr python3 tools/libq.py page orsec-eau-ain 42
LASTBOOK_DATA=/vers/lastbook-fr python3 tools/libq.py search "ébullition"
```

## À vérifier à chaque ajout

- la page citée existe et dit bien ce que décrit la note ;
- `label`/`note` décrivent le contenu sans ajouter de dose ou de procédure ;
- les `limits` sont formulés dans le texte source.

## Reste à faire (J3)

Les 13 autres besoins (`assainissement`, `alimentation`, `abri`, `énergie`,
`soins`, `blessures`, `communications`, `terrain`, `eau`… ) doivent être rédigés
sur les mêmes sources françaises : sécurité civile, Croix-Rouge, Santé publique
France, ANSES, Météo-France, BRGM, FNOR, DGS, préfectures.
