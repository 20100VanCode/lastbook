"""The French regions exist as identifiers the setup contract accepts.

The scheme and the boxes come from docs/REGIONS-FR.md; these tests hold the two
rules that make a region usable: a code the manifest and the switch accept, and a
code that never collides with a US state.
"""
import unittest

from engine.address_search import STATE_CODES
from engine.regions import (OVERSEAS, REGIONS, REGION_BOXES, REGION_CODES,
                            REGION_DEPARTEMENTS, REGION_NAMES, ID, is_region_id)
from engine.setup.manifest import validate


class Regions(unittest.TestCase):
    def test_eighteen_regions_including_the_five_overseas(self):
        self.assertEqual(len(REGIONS), 18)
        self.assertEqual(len(REGION_CODES), 18)
        self.assertEqual(set(OVERSEAS), {'FR-971', 'FR-972', 'FR-973', 'FR-974', 'FR-976'})
        self.assertTrue(set(OVERSEAS) <= REGION_CODES)
        self.assertEqual(len(REGION_DEPARTEMENTS['FR-IDF']), 8)
        self.assertEqual(len(REGION_DEPARTEMENTS['FR-972']), 1)

    def test_no_code_collides_with_a_us_state(self):
        self.assertFalse(set(STATE_CODES) & REGION_CODES)

    def test_every_region_id_is_accepted(self):
        for code in REGION_CODES:
            with self.subTest(code=code):
                self.assertTrue(ID.fullmatch(code))
                self.assertTrue(is_region_id(code))

    def test_bad_identifiers_are_refused(self):
        for bad in ('FR-A', 'FR-ARAA', 'FR-', 'FR_ARA', 'ara', '../FR-ARA', 'FRA-ARA', 'FR-ARA ', 'FR-ara'):
            with self.subTest(bad=bad):
                self.assertIsNone(ID.fullmatch(bad))
                self.assertFalse(is_region_id(bad))

    def test_boxes_are_west_south_east_north(self):
        for code, _, box, _ in REGIONS:
            with self.subTest(code=code):
                west, south, east, north = box
                self.assertLess(west, east)
                self.assertLess(south, north)
                self.assertEqual(REGION_BOXES[code], box)

    def test_names_are_unique_and_present(self):
        names = [name for _, name, _, _ in REGIONS]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(names))
        self.assertEqual(REGION_NAMES['FR-972'], 'Martinique')

    def test_manifest_accepts_a_french_address_index(self):
        manifest = {'version': 1, 'packs': [], 'models': [], 'maps': [],
                    'address_indexes': [{'id': 'FR-972', 'title': 'Martinique', 'available': True,
                                         'installed_bytes': 10, 'files': []}]}
        got = validate(manifest)
        self.assertIsNotNone(got)
        self.assertEqual(got['address_indexes'][0]['id'], 'FR-972')

    def test_manifest_still_refuses_a_path_in_an_id(self):
        manifest = {'version': 1, 'packs': [], 'models': [], 'maps': [],
                    'address_indexes': [{'id': '../FR-972', 'title': 'x', 'available': True,
                                         'installed_bytes': 10, 'files': []}]}
        self.assertIsNone(validate(manifest))


if __name__ == '__main__':
    unittest.main()
