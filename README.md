# order_populater

Automates submitting orders into the EWE logistics system by reading xlsx files and using Playwright to fill each order form in a headed browser.

## Setup

### macOS / Linux

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Fill in EWE_USERNAME, EWE_PASSWORD, and SERVICE_LINE in .env
```

### Windows

```bat
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

Then open `.env` in Notepad and fill in your credentials.

> **Note:** Run commands in **Command Prompt** or **PowerShell**. If `python` is not recognised, try `py` instead.

## Usage

```bash
python populate.py
```

The script will:
1. Open a Chromium browser and navigate to the EWE login page
2. Auto-fill your username and password, then pause for you to solve the image CAPTCHA
3. After login, all orders are filled and submitted automatically — no further interaction needed
4. Each order preview is printed to the terminal as it is processed

If `CONFIRM_EACH_ORDER=true` is set in `.env`, the script will pause after filling each form so you can review it in the browser before submitting.

## Input format

Place xlsx files in the `input/` folder. Each file's name determines its category (e.g. `零食.xlsx`, `保健品.xlsx`). Files are read from **录单表**; each row is one product line item, grouped by `联系人（务必实名）` + `联系电话` into a single order.

| Column | Used for |
|---|---|
| `联系人（务必实名）` | Recipient name |
| `联系电话` | Recipient phone |
| `地址` | Recipient address |
| `品牌名字` | Item brand |
| `产品名字` | Item name |
| `数量` | Item quantity |
| `备注` | Notes (optional) |

If an order's total quantity exceeds the category maximum, the order is automatically split into multiple separate submissions with quantities spread evenly.

## Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Default | Description |
|---|---|---|
| `EWE_USERNAME` | — | Login username |
| `EWE_PASSWORD` | — | Login password |
| `SERVICE_LINE` | `经济杂货` | Default service line: `经济奶粉`, `经济杂货`, or `标准杂货` |
| `CONFIRM_EACH_ORDER` | `false` | Set to `true` to manually confirm each order before submitting |

## Category rules

Category is determined by the xlsx filename stem:

| Category | Max qty per order | Service line |
|---|---|---|
| `零食` | 15 | `SERVICE_LINE` from `.env` |
| `保健品` | 8 | `SERVICE_LINE` from `.env` |
| `奶粉` | 3 | `经济奶粉` |
| other | unlimited | `SERVICE_LINE` from `.env` |

## Step-by-step guide

1. **Prepare your xlsx files.** Each file should be named after its category (e.g. `零食.xlsx`, `保健品.xlsx`, `奶粉.xlsx`). Each file must have a sheet named **录单表** with the columns listed above.

2. **Drop the files into the `input/` folder.**
   ```
   input/
     零食.xlsx
     保健品.xlsx
     奶粉.xlsx
   ```

3. **Run the script.**
   ```bash
   python populate.py
   ```
   Or pass specific files:
   ```bash
   python populate.py input/零食.xlsx input/奶粉.xlsx
   ```

4. **Solve the CAPTCHA.** A Chromium browser will open and navigate to the EWE login page. Your username and password are filled in automatically. Solve the image CAPTCHA in the browser, then press **Enter** in the terminal.

5. **Watch it run.** The script processes each order:
   - Prints a preview to the terminal (name, phone, address, items)
   - Fills the form in the browser (smart address, items, service line, notes)
   - Submits the order and prints the order number
   - If `CONFIRM_EACH_ORDER=true`, it pauses after filling the form so you can review before submitting (press **Enter** to submit, **Ctrl+C** to skip)

6. **Order splitting.** If an order's total quantity exceeds the category max, it is automatically split into multiple submissions. Split orders are highlighted in the terminal:
   ```
   Order 3/9 [保健品]  *** SPLIT 1/2 ***
     Name:    张伟
     Items (4个):
       - [Blackmores] 鱼油胶囊  x4
   Order 4/9 [保健品]  *** SPLIT 2/2 ***
     Name:    张伟
     Items (4个):
       - [Blackmores] 鱼油胶囊  x3
       - [Swisse] 叶黄素  x1
   ```

7. **Review the summary.** After all orders are processed, a summary report is printed:
   ```
   SUMMARY REPORT
   ============================================================
   Files processed:
     input/保健品.xlsx [保健品]: 3 orders → 5 submissions (2 split)
     input/零食.xlsx [零食]: 3 orders → 4 submissions (1 split)

   Total original orders: 6
   Total submissions:     9 (3 from splitting)
   Submitted:             9

   Order numbers:
     EWE20260325001 — 张伟 (4个)
     EWE20260325002 — 张伟 (4个)
     ...
   ```
