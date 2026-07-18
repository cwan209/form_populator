import unittest

import numpy as np
import pandas as pd

from populate import (RESULTS_SHEET, build_note_text, build_results,
                      find_order_no_column, load_orders, split_order,
                      str_cell, str_id, write_results)


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
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 3, "备注": ""},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": ""},
            {"收件人姓名": "李明", "电话": "13800000002", "收货地址": "上海市浦东某路", "快递品牌": "Swisse", "快递名称": "鱼油", "快递数量": 5, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders), 2)

    def test_items_collected_per_order(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 3, "备注": ""},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders[0]['items']), 2)
        self.assertEqual(orders[0]['items'][0], ("Weet-Bix", "儿童麦片", 3))

    def test_notes_read_from_备注(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": "请轻放"},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['notes'], "请轻放")

    def test_empty_notes_is_empty_string(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": float("nan")},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['notes'], "")

    def test_skips_empty_product_name(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "", "快递数量": 1, "备注": ""},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders[0]['items']), 1)
        self.assertEqual(orders[0]['items'][0][1], "原味饼干")

    def test_same_person_different_address_splits_orders(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 3, "备注": ""},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "上海市浦东某路", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0]['address'], "广东省深圳市某街道")
        self.assertEqual(orders[0]['items'], [("Weet-Bix", "儿童麦片", 3)])
        self.assertEqual(orders[1]['address'], "上海市浦东某路")
        self.assertEqual(orders[1]['items'], [("TimTam", "原味饼干", 2)])

    def test_missing_address_rows_still_loaded(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": float("nan"), "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['address'], "")

    def test_qty_defaults_to_1_when_nan(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": float("nan"), "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['items'][0][2], 1)

    def test_mogu_order_no_collected_and_deduped(self):
        df = self._make_df([
            {"蘑菇订单号": "MG001", "收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 3, "备注": ""},
            {"蘑菇订单号": "MG001", "收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['mogu_order_nos'], ["MG001"])

    def test_mogu_order_no_numeric_cell_has_no_decimal(self):
        df = self._make_df([
            {"蘑菇订单号": 20260718001.0, "收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['mogu_order_nos'], ["20260718001"])

    def test_no_order_no_column_gives_empty_list(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['mogu_order_nos'], [])

    def test_seller_notes_collected_and_deduped(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": "", "卖家备注": "尽快发货"},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "TimTam", "快递名称": "原味饼干", "快递数量": 2, "备注": "", "卖家备注": "尽快发货"},
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Swisse", "快递名称": "鱼油", "快递数量": 1, "备注": "", "卖家备注": "拆两箱"},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['seller_notes'], "尽快发货\n拆两箱")

    def test_missing_seller_notes_column_gives_empty_string(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": ""},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['seller_notes'], "")

    def test_nan_seller_notes_gives_empty_string(self):
        df = self._make_df([
            {"收件人姓名": "王芳", "电话": "13800000001", "收货地址": "广东省深圳市某街道", "快递品牌": "Weet-Bix", "快递名称": "儿童麦片", "快递数量": 1, "备注": "", "卖家备注": float("nan")},
        ])
        orders = load_orders(df)
        self.assertEqual(orders[0]['seller_notes'], "")


class TestBuildNoteText(unittest.TestCase):
    ITEMS = [("A", "麦片", 3), ("B", "饼干", 2)]

    def test_qty_only(self):
        self.assertEqual(build_note_text(self.ITEMS, ""), "5个")

    def test_with_notes(self):
        self.assertEqual(build_note_text(self.ITEMS, "请轻放"), "5个\n\n请轻放")

    def test_with_seller_notes_only(self):
        self.assertEqual(build_note_text(self.ITEMS, "", "尽快发货"), "5个\n\n尽快发货")

    def test_with_both_notes(self):
        self.assertEqual(build_note_text(self.ITEMS, "请轻放", "尽快发货"),
                         "5个\n\n请轻放\n\n尽快发货")


class TestStrId(unittest.TestCase):
    def test_integral_float(self):
        self.assertEqual(str_id(123.0), "123")

    def test_string_passthrough(self):
        self.assertEqual(str_id(" MG001 "), "MG001")

    def test_nan(self):
        self.assertEqual(str_id(float("nan")), "")


class TestFindOrderNoColumn(unittest.TestCase):
    def test_exact_match(self):
        df = pd.DataFrame(columns=["订单号", "蘑菇订单号", "收件人姓名"])
        self.assertEqual(find_order_no_column(df), "蘑菇订单号")

    def test_fallback_contains(self):
        df = pd.DataFrame(columns=["平台订单号", "收件人姓名"])
        self.assertEqual(find_order_no_column(df), "平台订单号")

    def test_none_when_absent(self):
        df = pd.DataFrame(columns=["收件人姓名", "电话"])
        self.assertIsNone(find_order_no_column(df))


def make_original(order_key, mogu_nos, name="王芳", phone="13800000001", address="广东省深圳市某街道"):
    return {'name': name, 'phone': phone, 'address': address, 'items': [],
            'notes': '', 'mogu_order_nos': mogu_nos, 'order_key': order_key}


class TestBuildResults(unittest.TestCase):
    def test_split_order_joins_ewe_numbers(self):
        originals = [make_original(("f", 0), ["MG001"])]
        submitted = [{**originals[0], 'order_no': "EWE001"},
                     {**originals[0], 'order_no': "EWE002"}]
        rows = build_results(originals, submitted)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['蘑菇订单号'], "MG001")
        self.assertEqual(rows[0]['EWE订单号'], "EWE001, EWE002")
        self.assertEqual(rows[0]['收件人'], "王芳")
        self.assertEqual(rows[0]['收件人电话'], "13800000001")
        self.assertEqual(rows[0]['地址'], "广东省深圳市某街道")

    def test_failed_order_gets_empty_ewe_cell(self):
        originals = [make_original(("f", 0), ["MG001"]),
                     make_original(("f", 1), ["MG002"], name="李明")]
        submitted = [{**originals[0], 'order_no': "EWE001"}]
        rows = build_results(originals, submitted)
        self.assertEqual(rows[0]['EWE订单号'], "EWE001")
        self.assertEqual(rows[1]['EWE订单号'], "")

    def test_group_with_multiple_mogu_orders_gets_row_each(self):
        originals = [make_original(("f", 0), ["MG001", "MG002"])]
        submitted = [{**originals[0], 'order_no': "EWE001"}]
        rows = build_results(originals, submitted)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['蘑菇订单号'] for r in rows], ["MG001", "MG002"])
        self.assertEqual(rows[0]['EWE订单号'], "EWE001")
        self.assertEqual(rows[1]['EWE订单号'], "EWE001")

    def test_missing_mogu_no_still_writes_row(self):
        originals = [make_original(("f", 0), [])]
        rows = build_results(originals, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['蘑菇订单号'], "")


class TestWriteResults(unittest.TestCase):
    def test_appends_sheet_preserving_original(self):
        import os
        import tempfile

        src = pd.DataFrame([{"收件人姓名": "王芳", "电话": "13800000001"}])
        rows = build_results([make_original(("f", 0), ["MG001"])],
                             [{**make_original(("f", 0), ["MG001"]), 'order_no': "EWE001"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "订单.xlsx")
            src.to_excel(path, sheet_name='团购发货单', index=False)
            write_results(path, rows)
            # Overwriting an existing 下单结果 sheet must also work
            write_results(path, rows)

            original = pd.read_excel(path, sheet_name='团购发货单')
            self.assertEqual(original.iloc[0]['收件人姓名'], "王芳")
            result = pd.read_excel(path, sheet_name=RESULTS_SHEET)
            self.assertEqual(list(result.columns),
                             ['蘑菇订单号', '收件人', '收件人电话', '地址', 'EWE订单号'])
            self.assertEqual(result.iloc[0]['蘑菇订单号'], "MG001")
            self.assertEqual(result.iloc[0]['EWE订单号'], "EWE001")


if __name__ == '__main__':
    unittest.main()
