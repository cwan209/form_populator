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

Place xlsx files in the `input/` folder. Each file's name determines its category (e.g. `零食.xlsx`, `保健品.xlsx`). Files are read from **Sheet3**; each row is one product line item, grouped by `联系人（务必实名）` + `联系电话` into a single order.

| Column | Used for |
|---|---|
| `联系人（务必实名）` | Recipient name |
| `联系电话` | Recipient phone |
| `地址` | Recipient address |
| `品牌名字` | Item brand |
| `产品名字` | Item name |
| `数量` | Item quantity |
| `备注` | Notes (optional) |

If any item's quantity exceeds the category maximum, the order is automatically split into multiple separate submissions with quantities spread evenly.

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

| Category | Max qty per item | Service line |
|---|---|---|
| `零食` | 15 | `SERVICE_LINE` from `.env` |
| `保健品` | 8 | `SERVICE_LINE` from `.env` |
| `奶粉` | — | `经济奶粉` |
| other | unlimited | `SERVICE_LINE` from `.env` |
