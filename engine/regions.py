"""The 18 map regions of France and the DOM-TOM.

A region groups départements: the detailed map is cut by département
(`engine/departements.py`), and a region is how the setup screen offers them and
how the packs are described. The source of truth is docs/REGIONS-FR.md and
docs/regions-fr-proposed.json, which carry the source and licence table.

Codes are ISO 3166-2:FR (`FR-ARA`, `FR-20R`, `FR-971`). Boxes are the union of the
region's commune bounding boxes from the State's geography API, widened by 0.15
degrees. Nothing here is read by a build yet.
"""
import re

from .address_search import STATE_CODES
from .departements import DEPARTEMENT_CODES, by_region

# (code, name, box as west, south, east, north)
REGIONS = (
    ('FR-ARA', 'Auvergne-Rhône-Alpes', (1.91, 43.96, 7.34, 46.96)),
    ('FR-BFC', 'Bourgogne-Franche-Comté', (2.69, 46.00, 7.30, 48.56)),
    ('FR-BRE', 'Bretagne', (-5.30, 47.12, -0.86, 49.06)),
    ('FR-CVL', 'Centre-Val de Loire', (-0.10, 46.19, 3.28, 49.10)),
    ('FR-20R', 'Corse', (8.38, 41.18, 9.71, 43.18)),
    ('FR-GES', 'Grand Est', (3.23, 47.27, 8.39, 50.32)),
    ('FR-HDF', 'Hauts-de-France', (1.23, 48.68, 4.41, 51.24)),
    ('FR-IDF', 'Île-de-France', (1.29, 47.97, 3.71, 49.40)),
    ('FR-NOR', 'Normandie', (-2.11, 48.02, 1.96, 50.23)),
    ('FR-NAQ', 'Nouvelle-Aquitaine', (-1.95, 42.62, 2.77, 47.33)),
    ('FR-OCC', 'Occitanie', (-0.48, 42.18, 5.00, 45.20)),
    ('FR-PDL', 'Pays de la Loire', (-2.78, 46.11, 1.07, 48.72)),
    ('FR-PAC', 'Provence-Alpes-Côte d’Azur', (4.08, 42.83, 7.87, 45.28)),
    ('FR-971', 'Guadeloupe', (-61.96, 15.68, -60.85, 16.67)),
    ('FR-972', 'Martinique', (-61.38, 14.23, -60.65, 15.03)),
    ('FR-973', 'Guyane', (-54.76, 1.96, -51.46, 5.90)),
    ('FR-974', 'La Réunion', (55.06, -21.54, 55.99, -20.72)),
    ('FR-976', 'Mayotte', (44.86, -13.16, 45.45, -12.48)),
)

REGION_CODES = frozenset(code for code, _, _ in REGIONS)
REGION_NAMES = {code: name for code, name, _ in REGIONS}
REGION_BOXES = {code: box for code, _, box in REGIONS}
REGION_DEPARTEMENTS = {code: by_region(code) for code in REGION_CODES}

# The five overseas regions, kept together for the setup screen and the packs.
OVERSEAS = ('FR-971', 'FR-972', 'FR-973', 'FR-974', 'FR-976')

# An address-index or map-set identifier: a US state, or a French département.
ID = re.compile(r'(?:[A-Z]{2}|FR-[0-9A-Z]{2,3})')
KNOWN_IDS = frozenset(STATE_CODES) | frozenset('FR-' + code for code in DEPARTEMENT_CODES)


def is_region_id(value):
    """True for a French region code (`FR-ARA`, `FR-20R`, `FR-971`)."""
    return isinstance(value, str) and value in REGION_CODES


def is_known_id(value):
    """True for an identifier a map set or address index may carry."""
    return isinstance(value, str) and bool(ID.fullmatch(value)) and value in KNOWN_IDS
