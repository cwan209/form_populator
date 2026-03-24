import math
import unittest

import numpy as np
import pandas as pd

from populate import load_orders, split_items, str_cell


class TestStrCell(unittest.TestCase):
    def test_normal_string(self):
        self.assertEqual(str_cell("hello"), "hello")

    def test_strips_whitespace(self):
        self.assertEqual(str_cell("  hello  "), "hello")

    def test_nan_float(self):
        self.assertEqual(str_cell(float("nan")), "")

    def test_numpy_nan(self):
        self.assertEqual(str_cell(np.nan), "")

    def test_none(self):
        self.assertEqual(str_cell(None), "")

    def test_number(self):
        self.assertEqual(str_cell(42), "42")


class TestSplitItems(unittest.TestCase):
    def test_no_split_needed(self):
        items = [("Swisse", "鱼油", 5)]
        self.assertEqual(split_items(items, 8), [("Swisse", "鱼油", 5)])

    def test_exact_max(self):
        items = [("Swisse", "鱼油", 8)]
        self.assertEqual(split_items(items, 8), [("Swisse", "鱼油", 8)])

    def test_even_split(self):
        # 24 / max 15 → 2 batches of 12
        items = [("Weet-Bix", "儿童麦片", 24)]
        result = split_items(items, 15)
        self.assertEqual(result, [("Weet-Bix", "儿童麦片", 12), ("Weet-Bix", "儿童麦片", 12)])

    def test_uneven_split(self):
        # 25 / max 15 → 2 batches: 13 + 12
        items = [("Weet-Bix", "儿童麦片", 25)]
        result = split_items(items, 15)
        self.assertEqual(len(result), 2)
        self.assertEqual(sum(q for _, _, q in result), 25)
        self.assertAlmostEqual(result[0][2], result[1][2], delta=1)

    def test_three_way_split(self):
        # 31 / max 15 → 3 batches, total preserved
        items = [("Brand", "Item", 31)]
        result = split_items(items, 15)
        self.assertEqual(len(result), 3)
        self.assertEqual(sum(q for _, _, q in result), 31)
        for _, _, q in result:
            self.assertLessEqual(q, 15)

    def test_quantities_spread_evenly(self):
        # No batch should differ from another by more than 1
        for qty in range(1, 50):
            for max_qty in [8, 15]:
                items = [("B", "N", qty)]
                result = split_items(items, max_qty)
                qtys = [q for _, _, q in result]
                self.assertEqual(sum(qtys), qty)
                self.assertLessEqual(max(qtys) - min(qtys), 1)

    def test_multiple_items_mixed(self):
        items = [("A", "under", 5), ("B", "over", 20)]
        result = split_items(items, 15)
        # First item unchanged, second split into 2
        self.assertEqual(result[0], ("A", "under", 5))
        self.assertEqual(len([r for r in result if r[0] == "B"]), 2)
        self.assertEqual(sum(q for b, _, q in result if b == "B"), 20)


class TestLoadOrders(unittest.TestCase):
    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def test_groups_by_person(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "儿童麦片", "数量": 3, "备注": ""},
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "TimTam", "产品名字": "原味饼干", "数量": 2, "备注": ""},
            {"联系人（务必实名）": "李明", "联系电话": "13800000002", "地址": "上海市浦东某路", "品牌名字": "Swisse", "产品名字": "鱼油", "数量": 5, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders), 2)

    def test_items_collected_per_order(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "儿童麦片", "数量": 3, "备注": ""},
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "TimTam", "产品名字": "原味饼干", "数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders[0]['items']), 2)
        self.assertEqual(orders[0]['items'][0], ("Weet-Bix", "儿童麦片", 3))

    def test_notes_read_from_备注(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "儿童麦片", "数量": 1, "备注": "请轻放"},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['notes'], "请轻放")

    def test_empty_notes_is_empty_string(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "儿童麦片", "数量": 1, "备注": float("nan")},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['notes'], "")

    def test_skips_empty_product_name(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "", "数量": 1, "备注": ""},
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "TimTam", "产品名字": "原味饼干", "数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders[0]['items']), 1)
        self.assertEqual(orders[0]['items'][0][1], "原味饼干")

    def test_qty_defaults_to_1_when_nan(self):
        df = self._make_df([
            {"联系人（务必实名）": "王芳", "联系电话": "13800000001", "地址": "广东省深圳市某街道", "品牌名字": "Weet-Bix", "产品名字": "儿童麦片", "数量": float("nan"), "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['items'][0][2], 1)


if __name__ == '__main__':
    unittest.main()
