# content-fr — guides curatés en français

Contenu francophone pour RELIQUE. Même modèle que `content/topics/` (voir
`content/SCHEMA.md`), mais les sources sont des documents officiels français ou
francophones, cités par leur page réelle.

## Pilote : `eau`

`topics/eau.json` — « De l'eau potable sûre » : 8 situations, 7 limites,
4 préparations, 4 lectures d'approfondissement, **37 références vérifiées**
(`validate_topics.py`, 0 erreur).

Documents sources (`documents/`, manifeste `manifests/eau.json`) :

| id | document | éditeur | pages |
|---|---|---|---|
| `orsec-eau-ain` | ORSEC — Mode d'action « Eau potable » | Préfecture de l'Ain, 2024 | 49 |
| `ficr-hwts` | Traitement et stockage sûr de l'eau à domicile | Fédération internationale de la Croix-Rouge | 44 |
| `hcsp-comprimes` | Avis sur les comprimés désinfectants (Mayotte) | HCSP, 2023 | 10 |
| `iode-territoriale` | Déclinaison territoriale de la doctrine IODE | SIDESA | 33 |

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
