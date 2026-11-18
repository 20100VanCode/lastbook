"""The 101 départements of France: the unit a detailed map is cut by.

Decision (RELIQUE): the cut is by département, not by region. A département is
small enough that its map set stays a download a person can choose, and it is the
level the Base Adresse Nationale can be sliced by through `code_insee` — the
postcode prefix is not reliable (23 communes use a neighbouring département's
prefix, 6 of them across a region boundary; see docs/REGIONS-FR.md).

Codes are the département's own: 01-95 (Corse is 2A/2B), then 971-976 overseas.
Each carries its region, so the setup screen can still group by region.
"""
# (code, name, region code)
DEPARTEMENTS = (
    ('01', 'Ain', 'FR-ARA'), ('02', 'Aisne', 'FR-HDF'), ('03', 'Allier', 'FR-ARA'),
    ('04', 'Alpes-de-Haute-Provence', 'FR-PAC'), ('05', 'Hautes-Alpes', 'FR-PAC'),
    ('06', 'Alpes-Maritimes', 'FR-PAC'), ('07', 'Ardèche', 'FR-ARA'),
    ('08', 'Ardennes', 'FR-GES'), ('09', 'Ariège', 'FR-OCC'), ('10', 'Aube', 'FR-GES'),
    ('11', 'Aude', 'FR-OCC'), ('12', 'Aveyron', 'FR-OCC'),
    ('13', 'Bouches-du-Rhône', 'FR-PAC'), ('14', 'Calvados', 'FR-NOR'),
    ('15', 'Cantal', 'FR-ARA'), ('16', 'Charente', 'FR-NAQ'),
    ('17', 'Charente-Maritime', 'FR-NAQ'), ('18', 'Cher', 'FR-CVL'),
    ('19', 'Corrèze', 'FR-NAQ'), ('2A', 'Corse-du-Sud', 'FR-20R'),
    ('2B', 'Haute-Corse', 'FR-20R'), ('21', 'Côte-d’Or', 'FR-BFC'),
    ('22', 'Côtes-d’Armor', 'FR-BRE'), ('23', 'Creuse', 'FR-NAQ'),
    ('24', 'Dordogne', 'FR-NAQ'), ('25', 'Doubs', 'FR-BFC'),
    ('26', 'Drôme', 'FR-ARA'), ('27', 'Eure', 'FR-NOR'),
    ('28', 'Eure-et-Loir', 'FR-CVL'), ('29', 'Finistère', 'FR-BRE'),
    ('30', 'Gard', 'FR-OCC'), ('31', 'Haute-Garonne', 'FR-OCC'),
    ('32', 'Gers', 'FR-OCC'), ('33', 'Gironde', 'FR-NAQ'),
    ('34', 'Hérault', 'FR-OCC'), ('35', 'Ille-et-Vilaine', 'FR-BRE'),
    ('36', 'Indre', 'FR-CVL'), ('37', 'Indre-et-Loire', 'FR-CVL'),
    ('38', 'Isère', 'FR-ARA'), ('39', 'Jura', 'FR-BFC'),
    ('40', 'Landes', 'FR-NAQ'), ('41', 'Loir-et-Cher', 'FR-CVL'),
    ('42', 'Loire', 'FR-ARA'), ('43', 'Haute-Loire', 'FR-ARA'),
    ('44', 'Loire-Atlantique', 'FR-PDL'), ('45', 'Loiret', 'FR-CVL'),
    ('46', 'Lot', 'FR-OCC'), ('47', 'Lot-et-Garonne', 'FR-NAQ'),
    ('48', 'Lozère', 'FR-OCC'), ('49', 'Maine-et-Loire', 'FR-PDL'),
    ('50', 'Manche', 'FR-NOR'), ('51', 'Marne', 'FR-GES'),
    ('52', 'Haute-Marne', 'FR-GES'), ('53', 'Mayenne', 'FR-PDL'),
    ('54', 'Meurthe-et-Moselle', 'FR-GES'), ('55', 'Meuse', 'FR-GES'),
    ('56', 'Morbihan', 'FR-BRE'), ('57', 'Moselle', 'FR-GES'),
    ('58', 'Nièvre', 'FR-BFC'), ('59', 'Nord', 'FR-HDF'),
    ('60', 'Oise', 'FR-HDF'), ('61', 'Orne', 'FR-NOR'),
    ('62', 'Pas-de-Calais', 'FR-HDF'), ('63', 'Puy-de-Dôme', 'FR-ARA'),
    ('64', 'Pyrénées-Atlantiques', 'FR-NAQ'), ('65', 'Hautes-Pyrénées', 'FR-OCC'),
    ('66', 'Pyrénées-Orientales', 'FR-OCC'), ('67', 'Bas-Rhin', 'FR-GES'),
    ('68', 'Haut-Rhin', 'FR-GES'), ('69', 'Rhône', 'FR-ARA'),
    ('70', 'Haute-Saône', 'FR-BFC'), ('71', 'Saône-et-Loire', 'FR-BFC'),
    ('72', 'Sarthe', 'FR-PDL'), ('73', 'Savoie', 'FR-ARA'),
    ('74', 'Haute-Savoie', 'FR-ARA'), ('75', 'Paris', 'FR-IDF'),
    ('76', 'Seine-Maritime', 'FR-NOR'), ('77', 'Seine-et-Marne', 'FR-IDF'),
    ('78', 'Yvelines', 'FR-IDF'), ('79', 'Deux-Sèvres', 'FR-NAQ'),
    ('80', 'Somme', 'FR-HDF'), ('81', 'Tarn', 'FR-OCC'),
    ('82', 'Tarn-et-Garonne', 'FR-OCC'), ('83', 'Var', 'FR-PAC'),
    ('84', 'Vaucluse', 'FR-PAC'), ('85', 'Vendée', 'FR-PDL'),
    ('86', 'Vienne', 'FR-NAQ'), ('87', 'Haute-Vienne', 'FR-NAQ'),
    ('88', 'Vosges', 'FR-GES'), ('89', 'Yonne', 'FR-BFC'),
    ('90', 'Territoire de Belfort', 'FR-BFC'), ('91', 'Essonne', 'FR-IDF'),
    ('92', 'Hauts-de-Seine', 'FR-IDF'), ('93', 'Seine-Saint-Denis', 'FR-IDF'),
    ('94', 'Val-de-Marne', 'FR-IDF'), ('95', 'Val-d’Oise', 'FR-IDF'),
    ('971', 'Guadeloupe', 'FR-971'), ('972', 'Martinique', 'FR-972'),
    ('973', 'Guyane', 'FR-973'), ('974', 'La Réunion', 'FR-974'),
    ('976', 'Mayotte', 'FR-976'),
)

DEPARTEMENT_CODES = frozenset(code for code, _, _ in DEPARTEMENTS)
DEPARTEMENT_NAMES = {code: name for code, name, _ in DEPARTEMENTS}
DEPARTEMENT_REGION = {code: region for code, _, region in DEPARTEMENTS}


def by_region(region_code):
    """The département codes of one region, in code order."""
    return tuple(code for code, _, region in DEPARTEMENTS if region == region_code)
