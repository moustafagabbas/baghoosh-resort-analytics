# Baghoosh Resort – Sales & Pricing Analysis

An end-to-end data analytics portfolio project: messy department exports → cleaning → analysis → machine-learning
model → interactive dashboard.

**Company:** Al Riyadh Real Estate (fictional Egyptian developer) · **Project:** Baghoosh Resort, North Coast ·
**Currency:** EGP · **Report date:** 30 Dec 2025 · *All data is synthetic.*

**Business goal:** understand what drives Phase 1 unit sales and pricing, and support pricing decisions.

---

## Dataset

15 raw files from 7 departments (18 tables), stored in `data/raw/`:

| Source | File | What it contains |
|---|---|---|
| ERP | `ERP_Unit_Master.xlsx` | 450 units (320 Phase 1 on sale, 130 Phase 2 planned): type, size, view, pool, handover date |
| ERP | `ERP_Project_Structure.xlsx` | 40 buildings, cluster, phase, beachfront flag, construction dates |
| Commercial | `COM_Price_List.csv` | 712 price versions for the 320 Phase 1 units |
| Commercial | `COM_Payment_Plans.xlsx`, `COM_Pricing_Policy.xlsx` | Payment plans, margin targets and price premiums |
| CRM | `CRM_Leads.csv`, `CRM_Viewings.csv`, `CRM_Reservations.csv`, `CRM_Brokers.xlsx` | Sales funnel: 3,054 leads → viewings → reservations; 12 brokers |
| Finance | `FIN_Sales_Contracts.csv`, `FIN_Cost_Ledger.csv` | 144 sales contracts; 121 shared cost lines |
| QS | `QS_Construction_Rates.xlsx` | Construction cost per sqm by property type |
| GIS | `GIS_Distances.csv` | Distance from each building to 9 facilities |
| PMO | `PMO_Build_Progress.csv` | Monthly actual vs planned construction progress |
| Market | `MKT_Market_Comps.xlsx` | 400 competitor rental comps and a quarterly price index |

The raw files contain realistic data problems: duplicates, 20+ spellings of the same category, mixed date formats,
areas stored as text, prices off by ×10, distances in metres instead of km, monthly rents typed as annual, and more.

---

## What was done

1. **Data understanding** – profiled every file (shape, types, missing values, duplicates, keys) and mapped how the tables join.
2. **Cleaning** (`analysis.ipynb`, Section 3) – about 25 documented fixes. A value is only corrected when another
   source proves the right value (for example, broken list prices are rebuilt from the cash price, and impossible areas from the price list).
3. **Wrangling** (Section 4) – one row per unit with features, launch and current prices, development cost
   (direct cost plus the cost ledger shared out by its own allocation rules), launch margin, a **policy price**, demand counts and sale details.
4. **EDA and 12 charts** (Sections 6–7) – sales trend, sell-through by type, feature and price position, the lead funnel,
   brokers, payment plans, margins, construction progress and the market index.
5. **Machine learning** (Section 9) – a classification model that predicts whether a unit sells (`is_sold`).
6. **Dashboard** (`app.py`) – Streamlit app with filters, KPIs, interactive Plotly charts, a prediction tool and a data download.

---

## Key insights

1. **Sales are slowing:** 144 of 320 Phase 1 units (45%) sold for EGP 1.79B in 20 months. At the pace since April 2025 of about
   6 a month, the remaining 176 units need about 2.5 more years – past handover (August 2026 to February 2027).
2. **Villas are the weak spot:** 22% sold (9 of 40), and only 15% of pool villas.
3. **Pricing above the company's own policy price is the biggest sales killer:** units launched at the policy price
   sold 74%; units about 15% above it sold 16%.
4. **There is room to adjust prices:** the median launch margin is 49%, against a policy minimum of 18–22%.
5. **Long payment plans** (10% down / 8 years) are the most popular and get +3% over list; cash buyers pay −13%.
6. **The biggest lead channels convert the worst:** Meta brings 32% of leads but only 2.1% buy; walk-ins convert 10.8%.
7. **The market has caught up:** launch prices were 31% above the market average; after 62% market growth they are now about +1%.
8. **Construction is slightly behind plan:** 64.3% built vs 68.6% planned, and all 28 Phase 1 buildings are behind.

## Model

| | Logistic Regression (**chosen**) | Random Forest |
|---|---|---|
| Cross-validated accuracy | **0.70** | 0.68 |
| Cross-validated F1 | **0.66** | 0.61 |
| Cross-validated ROC AUC | **0.75** | 0.73 |

- **Features:** 9 facts known on launch day. Leakage columns (later price changes, leads, reservations, sale details) are excluded.
- **Biggest driver:** how far the launch price is above the policy price.
- **Why Logistic Regression:** better on every cross-validation score, finds more of the units that sell, and is easier to explain.
- **Limitation:** with 320 units, about 3 in 10 predictions are wrong. Use it to compare prices and rank units by risk.

---

## How to run (Windows)

You need **Python 3.11+**. Open a terminal (PowerShell or the VS Code terminal) **in this folder**.

1. Create and activate a virtual environment (recommended):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
2. Install the packages:
   ```powershell
   pip install -r requirements.txt
   ```
3. (Optional) Re-run the analysis. Open `analysis.ipynb` in VS Code or Jupyter, select the `.venv` Python kernel and
   choose **Run All**. This recreates `data/cleaned_data.csv`, `data/leads_clean.csv`, `data/monthly_sales.csv` and
   `models/model.joblib`. These files are already included, so you can skip this step.
4. Start the dashboard:
   ```powershell
   streamlit run app.py
   ```
   It opens in your browser at http://localhost:8501.

---

## Folder structure

```
python_dashboard/
├── data/
│   ├── raw/                 15 original source files (never modified)
│   ├── cleaned_data.csv     main dataset – one row per unit (450 × 59)
│   ├── leads_clean.csv      cleaned leads with broker and unit info (no personal data)
│   └── monthly_sales.csv    one row per month
├── models/
│   └── model.joblib         trained Logistic Regression pipeline (preprocessing + model)
├── analysis.ipynb           cleaning, wrangling, EDA, charts, findings and the ML model
├── app.py                   Streamlit dashboard
├── requirements.txt
└── README.md
```

**Tools:** Python · pandas · NumPy · Matplotlib · seaborn · Plotly · scikit-learn · Streamlit · joblib
