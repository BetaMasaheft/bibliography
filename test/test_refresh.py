#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_refresh():
    path = ROOT / "bin" / "refresh-ethiostudies.py"
    spec = importlib.util.spec_from_file_location("refresh", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.r = load_refresh()

    def test_csl_item_key_from_zotero_id(self):
        self.assertEqual(self.r.csl_item_key({"id": "2279228/ZHYISS79"}), "ZHYISS79")
        self.assertEqual(self.r.csl_item_key({"id": "ZHYISS79"}), "ZHYISS79")

    def test_parse_csljson_accepts_list_or_items_wrapper(self):
        item = {"id": "ZHYISS79", "title": "x"}
        self.assertEqual(self.r.parse_csljson([item]), [item])
        self.assertEqual(self.r.parse_csljson({"items": [item]}), [item])

    def test_join_by_tag_skips_invalid_bm_tags(self):
        tags = {
            "ZHYISS79": ["bm:2020GnisciPsalter", "bm: bad space", "bm:"],
            "MISSING": ["bm:ghost"],
        }
        items = [{"id": "2279228/ZHYISS79", "title": "Kingship"}]
        joined = self.r.join_by_tag(tags, items)
        self.assertEqual(list(joined), ["bm:2020GnisciPsalter"])
        self.assertEqual(joined["bm:2020GnisciPsalter"]["title"], "Kingship")


if __name__ == "__main__":
    unittest.main()
