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
    """Split one order into multiple orders if any item exceeds max_qty.

    Each item is divided into evenly-sized batches. The number of sub-orders
    equals the maximum number of batches needed by any single item. Items that
    don't need splitting are included in the first sub-order only.

    Example (max_qty=15):
      Item A qty=24 → [12, 12]
      Item B qty=5  → [5]
      → Sub-order 1: A(12), B(5)
      → Sub-order 2: A(12)
    """
    if not max_qty:
        return [order]

    # Build per-item batch lists
    item_batches = []
    for brand, item_name, qty in order['items']:
        if qty <= max_qty:
            item_batches.append([(brand, item_name, qty)])
        else:
            n = math.ceil(qty / max_qty)
            base, remainder = divmod(qty, n)
            item_batches.append([
                (brand, item_name, base + (1 if i < remainder else 0))
                for i in range(n)
            ])

    n_orders = max(len(b) for b in item_batches)
    sub_orders = []
    for i in range(n_orders):
        sub_items = [batches[i] for batches in item_batches if i < len(batches)]
        if sub_items:
            sub_orders.append({**order, 'items': sub_items})
    return sub_orders


def fill_order(page, name, phone, address, items, notes, category=None):
    # Navigate to fresh form
    page.goto(EWE_URL)
    page.wait_for_load_state('networkidle')
    if is_login_page(page):
        print("Session expired — log in again in the browser, then press Enter...")
        input()

    # Fill smart address textarea and trigger JS parsing + Baidu geocoding
    page.locator('#address_content').fill(f"{name} {phone} {address}")
    page.locator('input[onclick="readAddressContent()"]').click()
    # Wait for geocoding AJAX to populate city field
    try:
        page.wait_for_function("document.getElementById('shi').value !== ''", timeout=8000)
    except Exception:
        print("  Warning: address geocoding may not have completed — check browser.")

    # Fill items table
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
    """Group Sheet3 rows by person into a list of order dicts."""
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

    orders = []
    for f in files:
        category = os.path.splitext(os.path.basename(f))[0]
        max_qty = CATEGORY_MAX_QTY.get(category)
        df = pd.read_excel(f, sheet_name='Sheet3')
        file_orders = load_orders(df)
        for o in file_orders:
            o['max_qty'] = max_qty
            o['category'] = category
        print(f"Loaded {len(file_orders)} orders from {f} (category: {category}, max qty/item: {max_qty or 'unlimited'})")
        orders.extend(file_orders)
    expanded = []
    for o in orders:
        expanded.extend(split_order(o, o['max_qty']))
    orders = expanded
    print(f"Total: {len(orders)} orders.\n")

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
            max_qty = order['max_qty']
            category = order['category']

            print(f"\n{'='*60}")
            print(f"Order {idx + 1}/{len(orders)} [{category}]")
            print(f"  Name:    {name}")
            print(f"  Phone:   {phone}")
            print(f"  Address: {address}")
            print(f"  Items:")
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
                    continue

            # Submit via the AJAX button
            page.locator('#ajaxScuuceeBtn').click()
            try:
                page.wait_for_selector('.mask', state='visible', timeout=10000)
                order_no = page.locator('#successOrderNo').inner_text()
                print(f"Order {idx + 1} submitted. Order no: {order_no}")
            except Exception:
                print(f"Order {idx + 1}: submit response unclear — check browser.")

        browser.close()


if __name__ == '__main__':
    main()
