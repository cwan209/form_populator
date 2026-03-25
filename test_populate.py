import unittest

import numpy as np
import pandas as pd

from populate import load_orders, split_order, str_cell


def make_order(items, notes=""):
    return {
        'name': '王芳', 'phone': '13800000001',
        'address': '广东省深圳市某街道',
        'items': items, 'notes': notes,
        'max_qty': None, 'category': '零食',
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
    def test_no_split_under_max(self):
        order = make_order([("A", "麦片", 5), ("B", "饼干", 3)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['items'], [("A", "麦片", 5), ("B", "饼干", 3)])

    def test_exact_max_no_split(self):
        order = make_order([("A", "麦片", 8)])
        result = split_order(order, 8)
        self.assertEqual(len(result), 1)

    def test_no_max_qty_no_split(self):
        order = make_order([("A", "麦片", 100)])
        result = split_order(order, None)
        self.assertEqual(len(result), 1)

    def test_single_item_even_split(self):
        # total=24, max=15 → 2 orders of 12
        order = make_order([("A", "麦片", 24)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['items'], [("A", "麦片", 12)])
        self.assertEqual(result[1]['items'], [("A", "麦片", 12)])

    def test_single_item_uneven_split(self):
        # total=25, max=15 → 2 orders: 13 + 12
        order = make_order([("A", "麦片", 25)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        qtys = [o['items'][0][2] for o in result]
        self.assertEqual(sum(qtys), 25)
        self.assertLessEqual(max(qtys) - min(qtys), 1)

    def test_three_way_split(self):
        # total=40, max=15 → 3 orders
        order = make_order([("A", "麦片", 40)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 3)
        total = sum(o['items'][0][2] for o in result)
        self.assertEqual(total, 40)
        for o in result:
            self.assertLessEqual(o['items'][0][2], 15)

    def test_multiple_items_total_exceeds(self):
        # A(10) + B(8) = 18, max=15 → 2 orders of 9 each
        order = make_order([("A", "麦片", 10), ("B", "饼干", 8)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        totals = [sum(q for _, _, q in o['items']) for o in result]
        self.assertEqual(sum(totals), 18)
        self.assertLessEqual(max(totals) - min(totals), 1)

    def test_multiple_items_split_distributes_items(self):
        # A(10) + B(8) + C(6) = 24, max=15 → 2 orders of 12
        order = make_order([("A", "麦片", 10), ("B", "饼干", 8), ("C", "糖果", 6)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 2)
        totals = [sum(q for _, _, q in o['items']) for o in result]
        self.assertEqual(totals, [12, 12])
        # Total per product preserved
        all_items = {}
        for o in result:
            for brand, name, qty in o['items']:
                all_items[(brand, name)] = all_items.get((brand, name), 0) + qty
        self.assertEqual(all_items[("A", "麦片")], 10)
        self.assertEqual(all_items[("B", "饼干")], 8)
        self.assertEqual(all_items[("C", "糖果")], 6)

    def test_item_can_span_two_orders(self):
        # A(10) + B(8) = 18, max=15 → B gets split: some in order 1, rest in order 2
        order = make_order([("A", "麦片", 10), ("B", "饼干", 8)])
        result = split_order(order, 15)
        # B should appear in both orders
        all_items = {}
        for o in result:
            for brand, name, qty in o['items']:
                key = (brand, name)
                all_items[key] = all_items.get(key, 0) + qty
        self.assertEqual(all_items[("A", "麦片")], 10)
        self.assertEqual(all_items[("B", "饼干")], 8)

    def test_each_sub_order_within_max(self):
        # Exhaustive: various totals and max values
        for total in range(1, 60):
            for max_qty in [8, 15]:
                order = make_order([("A", "Item", total)])
                result = split_order(order, max_qty)
                for o in result:
                    sub_total = sum(q for _, _, q in o['items'])
                    self.assertLessEqual(sub_total, max_qty,
                                         f"total={total}, max={max_qty}: sub-order has {sub_total}")
                # Total preserved
                grand_total = sum(sum(q for _, _, q in o['items']) for o in result)
                self.assertEqual(grand_total, total)

    def test_sub_orders_spread_evenly(self):
        for total in range(1, 50):
            for max_qty in [8, 15]:
                order = make_order([("A", "Item", total)])
                result = split_order(order, max_qty)
                totals = [sum(q for _, _, q in o['items']) for o in result]
                if len(totals) > 1:
                    self.assertLessEqual(max(totals) - min(totals), 1,
                                         f"total={total}, max={max_qty}: uneven split {totals}")

    def test_preserves_order_metadata(self):
        order = make_order([("A", "麦片", 24)], notes="请轻放")
        result = split_order(order, 15)
        for o in result:
            self.assertEqual(o['name'], '王芳')
            self.assertEqual(o['notes'], '请轻放')

    def test_no_items_below_max(self):
        # All items fit, no split
        order = make_order([("A", "麦片", 3), ("B", "饼干", 2), ("C", "糖", 1)])
        result = split_order(order, 15)
        self.assertEqual(len(result), 1)


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
