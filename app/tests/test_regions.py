"""The French map units exist as identifiers the setup contract accepts.

Decision: the detailed map is cut by département (101 of them), and a region only
groups them. The scheme and the boxes come from docs/REGIONS-FR.md; these tests
hold the two rules that make a département usable: an identifier the manifest and
the switch accept, and one that never collides with a US state.
"""
import unittest

from engine.address_search import STATE_CODES
from engine.departements import (DEPARTEMENTS, DEPARTEMENT_CODES, DEPARTEMENT_NAMES,
                                 DEPARTEMENT_REGION, by_region)
from engine.regions import (OVERSEAS, REGIONS, REGION_BOXES, REGION_CODES,
                            REGION_DEPARTEMENTS, REGION_NAMES, ID, is_known_id,
                            is_region_id)
from engine.setup.manifest import validate


class Regions(unittest.TestCase):
    def test_eighteen_regions_including_the_five_overseas(self):
        self.assertEqual(len(REGIONS), 18)
        self.assertEqual(len(REGION_CODES), 18)
        self.assertEqual(set(OVERSEAS), {'FR-971', 'FR-972', 'FR-973', 'FR-974', 'FR-976'})
        self.assertTrue(set(OVERSEAS) <= REGION_CODES)

    def test_hundred_and_one_departements(self):
        self.assertEqual(len(DEPARTEMENTS), 101)
        self.assertEqual(len(DEPARTEMENT_CODES), 101)
        self.assertEqual(sum(len(v) for v in REGION_DEPARTEMENTS.values()), 101)
        for code, name, region in DEPARTEMENTS:
            with self.subTest(code=code):
                self.assertIn(region, REGION_CODES)
                self.assertEqual(DEPARTEMENT_REGION[code], region)
                self.assertEqual(by_region(region), REGION_DEPARTEMENTS[region])
                self.assertTrue(name)
        self.assertEqual(DEPARTEMENT_NAMES['972'], 'Martinique')
        self.assertEqual(DEPARTEMENT_NAMES['75'], 'Paris')

    def test_no_code_collides_with_a_us_state(self):
        self.assertFalse(set(STATE_CODES) & REGION_CODES)
        self.assertFalse(set(STATE_CODES) & DEPARTEMENT_CODES)


class Identifiers(unittest.TestCase):
    def test_a_us_state_and_a_french_departement_are_both_known(self):
        for good in ('CA', 'MI', 'FR-14', 'FR-2A', 'FR-2B', 'FR-75', 'FR-972', 'FR-976'):
            with self.subTest(good=good):
                self.assertTrue(ID.fullmatch(good))
                self.assertTrue(is_known_id(good))

    def test_bad_identifiers_are_refused(self):
        for bad in ('FR-A', 'FR-1234', 'FR-', 'FR-ARA', 'ara', '../FR-972', 'FRA-972', 'FR-972 ', '2A'):
            with self.subTest(bad=bad):
                self.assertFalse(is_known_id(bad))

    def test_regions_are_groupings_not_map_ids(self):
        self.assertTrue(is_region_id('FR-ARA'))
        self.assertFalse(is_known_id('FR-ARA'))

    def test_boxes_are_west_south_east_north(self):
        for code, _, box in REGIONS:
            with self.subTest(code=code):
                west, south, east, north = box
                self.assertLess(west, east)
                self.assertLess(south, north)
                self.assertEqual(REGION_BOXES[code], box)

    def test_names_are_unique_and_present(self):
        names = [name for _, name, _ in REGIONS]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(names))
        self.assertEqual(REGION_NAMES['FR-972'], 'Martinique')


class Manifest(unittest.TestCase):
    def test_manifest_accepts_a_french_departement_index(self):
        manifest = {'version': 1, 'packs': [], 'models': [], 'maps': [],
                    'address_indexes': [{'id': 'FR-972', 'title': 'Martinique', 'available': True,
                                         'installed_bytes': 10, 'files': []}]}
        got = validate(manifest)
        self.assertIsNotNone(got)
        self.assertEqual(got['address_indexes'][0]['id'], 'FR-972')

    def test_manifest_refuses_a_region_id_and_a_path(self):
        for bad in ('FR-ARA', '../FR-972'):
            with self.subTest(bad=bad):
                manifest = {'version': 1, 'packs': [], 'models': [], 'maps': [],
                            'address_indexes': [{'id': bad, 'title': 'x', 'available': True,
                                                 'installed_bytes': 10, 'files': []}]}
                self.assertIsNone(validate(manifest))


if __name__ == '__main__':
    unittest.main()
