import glob
import math
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EWE_USERNAME = os.getenv("EWE_USERNAME", "")
EWE_PASSWORD = os.getenv("EWE_PASSWORD", "")
SERVICE_LINE = os.getenv("SERVICE_LINE", "经济杂货")
CONFIRM_EACH_ORDER = os.getenv("CONFIRM_EACH_ORDER", "false").lower() == "true"
EWE_URL = "https://jerry.ewe.com.au/eweJerry/ewe/order/orderInto"

SERVICE_LINE_VALUES = {
    "经济奶粉": "ecnMilkpower",
    "经济杂货": "ecnGoods",
    "标准杂货": "standGoods",
}

# Max quantity per line item for each category (keyed by filename stem)
CATEGORY_MAX_QTY = {
    "保健品": 8,
    "零食": 15,
    "奶粉": 3,
}

# Override service line per category (keyed by filename stem)
CATEGORY_SERVICE_LINE = {
    "奶粉": "经济奶粉",
}


def str_cell(val):
    """Convert a DataFrame cell to str, treating NaN/None as empty string."""
    if pd.isna(val):
        return ''
    return str(val).strip()


def is_login_page(page):
    return page.query_selector('#j_username') is not None


def login(page):
    page.goto(EWE_URL)
    page.wait_for_load_state('networkidle')
    if not is_login_page(page):
        print("Already logged in.")
        return
    print("Logging in...")
    page.fill('#j_username', EWE_USERNAME)
    page.fill('#j_password', EWE_PASSWORD)
    print("CAPTCHA required — solve it in the browser, then press Enter here...")
    try:
        input()
    except EOFError:
        print("(no stdin — waiting 30s for CAPTCHA to be solved manually...)")
        import time; time.sleep(30)
    # Login button is input[type=submit], not a <button>
    for sel in ['input[type=submit]', 'input[value="登录"]', 'button:has-text("登录")', 'button[type=submit]']:
        btn = page.locator(sel)
        if btn.count():
            btn.first.click()
            break
    else:
        page.keyboard.press('Enter')
    page.wait_for_load_state('networkidle')
    if is_login_page(page):
        print("Login may have failed — check the browser. Press Enter to continue anyway...")
        input()
    print("Logged in.")


def split_order(order, max_qty):
    """Split an order into multiple orders if total quantity exceeds max_qty.

    The total quantity across all items is checked. If it exceeds max_qty,
    the order is split into ceil(total/max_qty) sub-orders with quantities
    distributed as evenly as possible.

    Example (max_qty=15):
      A(10), B(8), C(6) → total=24, 2 sub-orders of 12
      → Sub-order 1: A(10), B(2)
      → Sub-order 2: B(6), C(6)
    """
    if not max_qty:
        return [order]

    items = order['items']
    total_qty = sum(qty for _, _, qty in items)

    if total_qty <= max_qty:
        return [order]

    n_orders = math.ceil(total_qty / max_qty)

    # Expand items into individual units, then split into even chunks
    flat = []
    for brand, item_name, qty in items:
        flat.extend([(brand, item_name)] * qty)

    base, remainder = divmod(len(flat), n_orders)
    chunks = []
    start = 0
    for i in range(n_orders):
        size = base + (1 if i < remainder else 0)
        chunks.append(flat[start:start + size])
        start += size

    # Re-aggregate each chunk back into (brand, name, qty) tuples
    sub_orders = []
    for idx, chunk in enumerate(chunks):
        seen = {}
        sub_items = []
        for brand, item_name in chunk:
            key = (brand, item_name)
            if key in seen:
                b, n, q = sub_items[seen[key]]
                sub_items[seen[key]] = (b, n, q + 1)
            else:
                seen[key] = len(sub_items)
                sub_items.append((brand, item_name, 1))
        if sub_items:
            sub_orders.append({**order, 'items': sub_items,
                               'split_part': idx + 1, 'split_total': n_orders})

    return sub_orders


def fill_order(page, name, phone, address, items, notes, category=None):
    # Navigate to fresh form
    page.goto(EWE_URL)
    page.wait_for_load_state('networkidle')
    if is_login_page(page):
        print("Session expired — log in again in the browser, then press Enter...")
        input()

    # 1. Fill address into 详细地址 field and click 确认 to trigger geocoding
    page.locator('#recieverAddDetail').fill(address)
    page.locator('input[onclick="analys(this)"]').click()
    try:
        page.wait_for_function("document.getElementById('shi').value !== ''", timeout=8000)
    except Exception:
        print("  Warning: address geocoding may not have completed — check browser.")

    # 2. Fill recipient name and phone into their own fields
    page.locator('#recieverName').fill(name)
    page.locator('#recieverMobile').fill(phone)

    # 3. Fill items table
    # Table has 7 inputs per row: sku(0), brand(1), productName(2), number(3),
    #   monovalent(4), barCode(5), deleteBtn(6)
    # IDs follow pattern: brand0, productName0, number0, brand1, productName1, ...
    for i, (brand, item_name, qty) in enumerate(items):
        if i > 0:
            page.locator('input[value="添加新物品"]').click()
            page.wait_for_timeout(300)
        page.locator(f'#brand{i}').fill(brand)
        page.locator(f'#productName{i}').fill(item_name)
        page.locator(f'#number{i}').fill(str(qty))

    # Select service line radio by value attribute (category overrides .env)
    service_line = CATEGORY_SERVICE_LINE.get(category, SERVICE_LINE) if category else SERVICE_LINE
    radio_value = SERVICE_LINE_VALUES.get(service_line, "ecnGoods")
    page.locator(f'input[name="serviceProduction"][value="{radio_value}"]').check()

    # Fill notes: total quantity, then actual note on a new line if present
    total_qty = sum(qty for _, _, qty in items)
    note_text = f"{total_qty}个"
    if notes:
        note_text += f"\n\n{notes}"
    page.locator('#commentRemark').fill(note_text)


def load_orders(df):
    """Group 录单表 rows by person into a list of order dicts."""
    orders = []
    for key, group in df.groupby(['联系人（务必实名）', '联系电话'], sort=False):
        first = group.iloc[0]
        name = str_cell(first.get('联系人（务必实名）', ''))
        phone = str_cell(first.get('联系电话', ''))
        address = str_cell(first.get('地址', ''))
        notes = str_cell(first.get('备注', ''))

        items = []
        for _, row in group.iterrows():
            brand = str_cell(row.get('品牌名字', ''))
            item_name = str_cell(row.get('产品名字', ''))
            qty_raw = row.get('数量', 1)
            qty = int(qty_raw) if not pd.isna(qty_raw) else 1
            if item_name:
                items.append((brand, item_name, qty))

        if name or phone:
            orders.append({'name': name, 'phone': phone, 'address': address,
                           'items': items, 'notes': notes})
    return orders


def main():
    files = sys.argv[1:] or sorted(glob.glob('input/*.xlsx'))
    if not files:
        print("No xlsx files found.")
        return

    # Load and split orders, tracking stats per file
    orders = []
    original_count = 0
    file_stats = {}
    for f in files:
        category = os.path.splitext(os.path.basename(f))[0]
        max_qty = CATEGORY_MAX_QTY.get(category)
        df = pd.read_excel(f, sheet_name='录单表')
        file_orders = load_orders(df)
        for o in file_orders:
            o['max_qty'] = max_qty
            o['category'] = category
        original_file_count = len(file_orders)
        original_count += original_file_count
        expanded_file = []
        for o in file_orders:
            expanded_file.extend(split_order(o, o['max_qty']))
        split_count = len(expanded_file) - original_file_count
        file_stats[f] = {'category': category, 'original': original_file_count,
                         'submitted': len(expanded_file), 'split': split_count}
        print(f"Loaded {original_file_count} orders from {f} (category: {category}, max qty/item: {max_qty or 'unlimited'})")
        orders.extend(expanded_file)
    print(f"Total: {len(orders)} submissions ({original_count} orders, {len(orders) - original_count} from splitting).\n")

    # Track results
    submitted = []
    failed = []
    skipped = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        login(page)

        for idx, order in enumerate(orders):
            name = order['name']
            phone = order['phone']
            address = order['address']
            items = order['items']
            notes = order['notes']
            category = order['category']

            split_part = order.get('split_part')
            split_total = order.get('split_total')

            print(f"\n{'='*60}")
            header = f"Order {idx + 1}/{len(orders)} [{category}]"
            if split_part:
                header += f"  *** SPLIT {split_part}/{split_total} ***"
            print(header)
            print(f"  Name:    {name}")
            print(f"  Phone:   {phone}")
            print(f"  Address: {address}")
            print(f"  Items ({sum(q for _, _, q in items)}个):")
            for brand, item_name, qty in items:
                print(f"    - [{brand}] {item_name}  x{qty}")
            if notes:
                print(f"  Notes:   {notes}")
            print(f"{'='*60}")

            fill_order(page, name, phone, address, items, notes, category)

            if CONFIRM_EACH_ORDER:
                try:
                    input("Press Enter to SUBMIT this order, Ctrl+C to skip... ")
                except KeyboardInterrupt:
                    print("\nSkipped.")
                    skipped.append(order)
                    continue

            # Submit via the AJAX button
            page.locator('#ajaxScuuceeBtn').click()
            try:
                page.wait_for_selector('.mask', state='visible', timeout=10000)
                order_no = page.locator('#successOrderNo').inner_text()
                print(f"Order {idx + 1} submitted. Order no: {order_no}")
                submitted.append({**order, 'order_no': order_no})
            except Exception:
                print(f"Order {idx + 1}: submit response unclear — check browser.")
                failed.append(order)

        browser.close()

    # Print summary report
    print(f"\n{'='*60}")
    print("SUMMARY REPORT")
    print(f"{'='*60}")
    print(f"\nFiles processed:")
    for f, stats in file_stats.items():
        split_note = f" ({stats['split']} split)" if stats['split'] > 0 else ""
        print(f"  {f} [{stats['category']}]: {stats['original']} orders → {stats['submitted']} submissions{split_note}")
    print(f"\nTotal original orders: {original_count}")
    print(f"Total submissions:     {len(orders)} ({len(orders) - original_count} from splitting)")
    print(f"Submitted:             {len(submitted)}")
    if failed:
        print(f"Failed/unclear:        {len(failed)}")
    if skipped:
        print(f"Skipped:               {len(skipped)}")
    if submitted:
        print(f"\nOrder numbers:")
        for s in submitted:
            total_qty = sum(q for _, _, q in s['items'])
            print(f"  {s['order_no']} — {s['name']} ({total_qty}个)")
    if failed:
        print(f"\nFailed orders (check manually):")
        for f_order in failed:
            print(f"  {f_order['name']} {f_order['phone']}")
    if skipped:
        print(f"\nSkipped orders:")
        for s_order in skipped:
            print(f"  {s_order['name']} {s_order['phone']}")
    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
