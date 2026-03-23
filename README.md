# order_populater

Automates submitting orders into the EWE logistics system by reading `input.xlsx` and using Playwright to fill each order form in a headed browser.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Fill in EWE_USERNAME, EWE_PASSWORD, and SERVICE_LINE in .env
```

## Usage

```bash
python populate.py
```

The script will:
1. Open a Chromium browser and navigate to the EWE login page
2. Auto-fill your username and password, then pause for you to solve the image CAPTCHA
3. After login, all orders from **Sheet3** of `input.xlsx` are filled and submitted automatically — no further interaction needed
4. Each order preview is printed to the terminal as it is processed

## Input format

Reads from **Sheet3** of `input.xlsx`. Each row is one product line item; rows are grouped by `联系人（务必实名）` + `联系电话` into a single order.

| Column | Used for |
|---|---|
| `联系人（务必实名）` | Recipient name (smart address) |
| `联系电话` | Recipient phone (smart address) |
| `地址` | Recipient address (smart address) |
| `品牌名字` | Item brand |
| `产品名字` | Item name |
| `数量` | Item quantity |

The three address fields are pasted into the smart address textarea, which auto-parses province/city/district via Baidu geocoding.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EWE_USERNAME` | — | Login username |
| `EWE_PASSWORD` | — | Login password |
| `SERVICE_LINE` | `经济杂货` | Service line: `经济奶粉`, `经济杂货`, or `标准杂货` |
