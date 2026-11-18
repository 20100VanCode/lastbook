"""The map regions of France and the DOM-TOM.

One map set per region, the level closest to a US state: 12 metropolitan regions,
Corsica and the five overseas regions. Nothing here is read by a build yet; the
source of truth is docs/REGIONS-FR.md and docs/regions-fr-proposed.json, which
carry the source and licence table for every layer.

Codes are ISO 3166-2:FR (`FR-ARA`, `FR-20R`, `FR-971`). They cannot be stored as
a US-style two-letter code, so the identifier rule in engine/setup/manifest.py
accepts either a US state (`[A-Z]{2}`) or a French region (`FR-` and three
alphanumeric characters). A region code never equals a US state code.

Boxes are the union of the region's commune bounding boxes from the State's
geography API, widened by 0.15 degrees as `map_sets.state` does for US states.
"""
import re

# (code, name, box as west, south, east, north, départements)
REGIONS = (
    ('FR-ARA', 'Auvergne-Rhône-Alpes', (1.91, 43.96, 7.34, 46.96),
     '01 03 07 15 26 38 42 43 63 69 73 74'),
    ('FR-BFC', 'Bourgogne-Franche-Comté', (2.69, 46.00, 7.30, 48.56),
     '21 25 39 58 70 71 89 90'),
    ('FR-BRE', 'Bretagne', (-5.30, 47.12, -0.86, 49.06), '22 29 35 56'),
    ('FR-CVL', 'Centre-Val de Loire', (-0.10, 46.19, 3.28, 49.10), '18 28 36 37 41 45'),
    ('FR-20R', 'Corse', (8.38, 41.18, 9.71, 43.18), '2A 2B'),
    ('FR-GES', 'Grand Est', (3.23, 47.27, 8.39, 50.32), '08 10 51 52 54 55 57 67 68 88'),
    ('FR-HDF', 'Hauts-de-France', (1.23, 48.68, 4.41, 51.24), '02 59 60 62 80'),
    ('FR-IDF', 'Île-de-France', (1.29, 47.97, 3.71, 49.40), '75 77 78 91 92 93 94 95'),
    ('FR-NOR', 'Normandie', (-2.11, 48.02, 1.96, 50.23), '14 27 50 61 76'),
    ('FR-NAQ', 'Nouvelle-Aquitaine', (-1.95, 42.62, 2.77, 47.33),
     '16 17 19 23 24 33 40 47 64 79 86 87'),
    ('FR-OCC', 'Occitanie', (-0.48, 42.18, 5.00, 45.20),
     '09 11 12 30 31 32 34 46 48 65 66 81 82'),
    ('FR-PDL', 'Pays de la Loire', (-2.78, 46.11, 1.07, 48.72), '44 49 53 72 85'),
    ('FR-PAC', 'Provence-Alpes-Côte d’Azur', (4.08, 42.83, 7.87, 45.28), '04 05 06 13 83 84'),
    ('FR-971', 'Guadeloupe', (-61.96, 15.68, -60.85, 16.67), '971'),
    ('FR-972', 'Martinique', (-61.38, 14.23, -60.65, 15.03), '972'),
    ('FR-973', 'Guyane', (-54.76, 1.96, -51.46, 5.90), '973'),
    ('FR-974', 'La Réunion', (55.06, -21.54, 55.99, -20.72), '974'),
    ('FR-976', 'Mayotte', (44.86, -13.16, 45.45, -12.48), '976'),
)

REGION_CODES = frozenset(code for code, _, _, _ in REGIONS)
REGION_NAMES = {code: name for code, name, _, _ in REGIONS}
REGION_BOXES = {code: box for code, _, box, _ in REGIONS}
REGION_DEPARTEMENTS = {code: tuple(d for d in deps.split() if d) for code, _, _, deps in REGIONS}

# The five overseas regions, kept together for the setup screen and the packs.
OVERSEAS = ('FR-971', 'FR-972', 'FR-973', 'FR-974', 'FR-976')

# An address-index or map-set identifier: a US state, or a French region.
ID = re.compile(r'(?:[A-Z]{2}|FR-[A-Z0-9]{3})')


def is_region_id(value):
    """True for a French region code (`FR-ARA`, `FR-20R`, `FR-971`)."""
    return isinstance(value, str) and value.startswith('FR-') and bool(ID.fullmatch(value))
