import unittest

import numpy as np
import pandas as pd

from populate import load_orders, split_order, str_cell


def make_order(items, max_qty=None, notes=""):
    return {
        'name': '王芳', 'phone': '13800000001',
        'address': '广东省深圳市某街道',
        'items': items, 'notes': notes,
        'max_qty': max_qty, 'category': '零食',
    }


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


class TestSplitOrder(unittest.TestCase):
    def test_no_split_needed(self):
        order = make_order([("Swisse", "鱼油", 5)], max_qty=8)
        result = split_order(order, 8)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['items'], [("Swisse", "鱼油", 5)])

    def test_exact_max_no_split(self):
        order = make_order([("Swisse", "鱼油", 8)], max_qty=8)
        result = split_order(order, 8)
        self.assertEqual(len(result), 1)

    def test_no_max_qty_no_split(self):
        order = make_order([("Swisse", "鱼油", 100)], max_qty=None)
        result = split_order(order, None)
        self.assertEqual(len(result), 1)

    def test_single_item_even_split(self):
        # qty=24, max=15 → 2 orders of 12
        order = make_order([("Weet-Bix", "儿童麦片", 24)], max_qty=15)
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['items'], [("Weet-Bix", "儿童麦片", 12)])
        self.assertEqual(result[1]['items'], [("Weet-Bix", "儿童麦片", 12)])

    def test_single_item_uneven_split(self):
        # qty=25, max=15 → 2 orders: 13 + 12
        order = make_order([("Weet-Bix", "儿童麦片", 25)], max_qty=15)
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        qtys = [o['items'][0][2] for o in result]
        self.assertEqual(sum(qtys), 25)
        self.assertLessEqual(max(qtys) - min(qtys), 1)

    def test_single_item_three_way_split(self):
        # qty=31, max=15 → 3 orders
        order = make_order([("Brand", "Item", 31)], max_qty=15)
        result = split_order(order, 15)
        self.assertEqual(len(result), 3)
        self.assertEqual(sum(o['items'][0][2] for o in result), 31)
        for o in result:
            self.assertLessEqual(o['items'][0][2], 15)

    def test_spread_evenly_all_quantities(self):
        for qty in range(1, 50):
            for max_qty in [8, 15]:
                order = make_order([("B", "N", qty)], max_qty=max_qty)
                result = split_order(order, max_qty)
                qtys = [o['items'][0][2] for o in result]
                self.assertEqual(sum(qtys), qty)
                self.assertLessEqual(max(qtys) - min(qtys), 1)

    def test_multiple_items_item_exceeding_goes_to_next_order(self):
        # Item A qty=24, max=15 → 2 batches [12, 12]
        # Item B qty=5,  max=15 → 1 batch  [5]
        # → Order 1: A(12), B(5)  |  Order 2: A(12)
        order = make_order([("A", "麦片", 24), ("B", "饼干", 5)], max_qty=15)
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['items'], [("A", "麦片", 12), ("B", "饼干", 5)])
        self.assertEqual(result[1]['items'], [("A", "麦片", 12)])

    def test_multiple_items_both_exceeding(self):
        # Item A qty=24, max=15 → [12, 12]
        # Item B qty=30, max=15 → [15, 15]
        # → 2 orders, each with both items
        order = make_order([("A", "麦片", 24), ("B", "饼干", 30)], max_qty=15)
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]['items']), 2)
        self.assertEqual(len(result[1]['items']), 2)
        total_a = sum(o['items'][0][2] for o in result)
        total_b = sum(o['items'][1][2] for o in result)
        self.assertEqual(total_a, 24)
        self.assertEqual(total_b, 30)

    def test_preserves_order_metadata(self):
        order = make_order([("A", "麦片", 24)], max_qty=15, notes="请轻放")
        result = split_order(order, 15)
        for o in result:
            self.assertEqual(o['name'], '王芳')
            self.assertEqual(o['notes'], '请轻放')


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
