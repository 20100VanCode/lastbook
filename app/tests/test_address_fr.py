"""French address lookup: the BAN's order (postcode before the commune), accents,
abbreviations and repetition indices, with no US-style state word at the end."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine.address_search import find_addresses, normalize_fr

ROWS = [
    ('14', 'Rue Écuyère', 'Caen', '14', '14000', 49.18, -0.37),
    ('14 bis', 'Rue Écuyère', 'Caen', '14', '14000', 49.18, -0.37),
    ('35', 'Rue Saint Jean', 'Caen', '14', '14000', 49.19, -0.36),
    ('11', 'Rue du Marais', 'Ri', '14', '14100', 48.80, -0.80),
    ('70', 'Allée des Moubins', "L'Ajoupa-Bouillon", '972', '97216', 14.81, -61.11),
    ('70', 'Allée des Moubins', 'Le Robert', '972', '97216', 14.68, -60.95),
]


class FrenchAddresses(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.geo = Path(self.temp.name)
        (self.geo / 'addresses').mkdir()
        db = sqlite3.connect(self.geo / 'addresses' / 'FR-972.sqlite')
        db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
        db.execute('CREATE INDEX addr_norm ON addr(norm,num)')
        db.executemany('INSERT INTO addr VALUES(?,?,?,?,?,?,?,?)',
                       ((num, street, normalize_fr(street), city, state, zip_, lat, lon)
                        for num, street, city, state, zip_, lat, lon in ROWS))
        db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)')
        db.execute("INSERT INTO meta VALUES('country','FR')")
        db.commit()
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    def names(self, query):
        return [hit['name'] for hit in find_addresses(query, self.geo)]

    def test_postcode_before_commune_and_accents(self):
        self.assertIn('14 Rue Écuyère', self.names('14 Rue Ecuyere, 14000 Caen'))

    def test_repetition_index(self):
        self.assertIn('14 bis Rue Écuyère', self.names('14 bis rue ecuyere caen'))

    def test_abbreviation_r_and_st(self):
        self.assertIn('35 Rue Saint Jean', self.names('35 r st jean caen'))

    def test_a_trailing_word_is_never_read_as_a_state(self):
        self.assertIn('11 Rue du Marais', self.names('11 rue du Marais Ri'))

    def test_the_commune_chooses_between_two_same_street_names(self):
        got = find_addresses('70 allée des moubins 97216 Le Robert', self.geo)
        self.assertEqual([hit['detail'] for hit in got], ['Le Robert, 97216'])

    def test_a_wrong_number_postcode_or_commune_is_refused(self):
        self.assertEqual(self.names('99 rue ecuyere caen'), [])
        self.assertEqual(self.names('14 rue ecuyere 99999 Caen'), [])
        self.assertEqual(self.names('14 rue ecuyere Paris'), [])


if __name__ == '__main__':
    unittest.main()
