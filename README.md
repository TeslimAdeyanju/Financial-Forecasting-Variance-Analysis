# Financial Forecasting & Variance Analysis

This project looks at whether a card portfolio's monthly spending can be forecast, which customers deviate from their expected spending, and where value and fraud are concentrated. It uses about 13 million card transactions from the Kaggle *Financial Transactions Dataset* and is built with Python, DuckDB SQL and time-series and machine-learning methods.

## The research question

> **How predictable is a card portfolio's monthly spending, which customers deviate from their expected spending, and where are value and fraud concentrated?**

| # | Sub-question | Method |
| --- | --- | --- |
| 1 | Can next month's portfolio **net spend** be forecast more accurately than simple benchmarks? | Walk-forward backtest: naive, seasonal naive, SARIMA, XGBoost (with SHAP) |
| 2 | Which customers and months **deviate materially** from budget, and is the deviation systematic? | Variance against a trailing three-month budget, tested at customer level (t-test, Wilcoxon) |
| 3 | How **concentrated** is customer value, and where is labelled **fraud** concentrated? | RFM segments with a K-means cross-check, Pareto analysis, fraud-rate profiling |

The data contains cardholder transactions but no issuer revenue, so the project measures **transaction value (net spend)**, not revenue.

[Explore the full project methodology and documentation](PROJECT_DOCUMENTATION.md).

## Key findings

Based on 13,305,915 transactions from 1,219 customers, January 2010 to October 2019 (118 complete months, $571.8m net spend). All 16 integrity controls pass, and every gold model reconciles to the transactions to the cent.

| Question | Finding |
| --- | --- |
| **Forecasting** | Monthly net spend is stable and strongly seasonal, at about $4.4m–$5.1m a month. The best model, **SARIMA, reached 0.70% MAPE** over a 24-month walk-forward backtest, but that is **only 0.4% better than the seasonal-naive benchmark**. For this portfolio, "same month last year" is almost as good as a statistical model. The 12-month outlook carries a ±4% 95% interval. |
| **Variance** | Against a trailing three-month budget, net variance is **+0.1% of budget**. That is statistically significant (p < 0.001), but only because the sample is so large; economically it is negligible. At customer level the same budget is noisy: **65% of customer-months miss by 10% or more**. |
| **Value** | Value is moderately concentrated. The **top 10% of customers generate 24%** of net spend, and 60% generate 80%. Champions (43% of customers) account for 64% of spend. 91% of customers transacted on the final day of the data, and only 13 have lapsed. |
| **Fraud** | Among labelled transactions, **online fraud runs at 0.84% against 0.06% in person (about 14×)**. Transactions flagged with an error carry 0.40% fraud against 0.15% overall. Prepaid debit cards (0.23%) have the highest rate by card type. |

The February dip in spend each year matches its shorter month (28 days against 30–31), not a change in behaviour. Annual spend grew 2–3% a year to 2013 and has been flat since 2016.

These findings come from the executive summary generated in [stage 6](notebook/06-data-visualisation-and-insights/06-data-visualisation-and-insights.ipynb). Read them against the [limitations](#limitations): the data shows the method, not a real bank's portfolio.

## Data analytics lifecycle

| Stage | Notebook | What it does |
| --- | --- | --- |
| 1 | [Data Sourcing](notebook/01-data-sourcing/01-data-sourcing.ipynb) | Research question, source schema, OneDrive availability check, source limitations |
| 2 | [Data Ingestion](notebook/02-data-ingestion/02-data-ingestion.ipynb) | One pull from OneDrive into **bronze** (text-only Parquet) with row-count reconciliation |
| 3 | [Data Cleaning & Transformation](notebook/03-data-cleaning-and-transformation/03-data-cleaning-and-transformation.ipynb) | Typed **silver** tables, documented cleaning rules, 22 SQL data-quality controls |
| 4 | [Data Modelling & Analytics](notebook/04-data-modelling-and-analytics/04-data-modelling-and-analytics.ipynb) | **Gold** SQL models, forecasting backtest, variance tests, RFM/K-means, customer KPIs |
| 5 | [Data Preparation for Reporting](notebook/05-data-preparation-for-reporting/05-data-preparation-for-reporting.ipynb) | Gold-to-silver reconciliation, star-schema CSV extracts and a data dictionary for Power BI |
| 6 | [Data Visualisation & Insights](notebook/06-data-visualisation-and-insights/06-data-visualisation-and-insights.ipynb) | Charts, an executive summary generated from the data, and limitations |

## Data architecture

```text
OneDrive  TeslimDataLakes/financial_transactions_dataset_analytics_kaggle/   (5 source files)
   │  onedrive_loader.load()  (Microsoft Graph API, read-only)
   ▼
data/bronze/*.parquet   text-only copy of the source            python/ingestion.py
   ▼
data/silver/*.parquet   typed, cleaned, conformed keys           python/cleaning.py + sql/quality/
   ▼
data/gold/*.parquet     analytical models and model outputs      sql/gold/*.sql + python/forecasting.py, segmentation.py
   ▼
outputs/powerbi/*.csv   reconciled reporting extracts            stage 5 notebook
```

DuckDB queries the Parquet files directly through `silver_*` and `gold_*` views ([`python/warehouse.py`](python/warehouse.py)), so the 13-million-row transaction table never has to fit in pandas for the SQL steps. `data/` and `outputs/` are gitignored and can be rebuilt from OneDrive by running stages 2–6.

## Methodological corrections

This repository replaces an earlier single notebook, which is kept in [`archive/`](archive/). These corrections change the results, not just how the project is laid out:

1. **Forecast leakage.** The old rolling-average and cumulative features included the month being predicted. All features now use prior months only.
2. **Circular variance.** The old "budget" was the same month's average, so variances summed to zero by construction. The budget now comes only from earlier months.
3. **Double counting.** The old segmentation query repeated each customer's totals once per active month.
4. **Broken joins and dates.** Fraud labels and MCC descriptions were never reshaped, so their joins couldn't resolve, and card open dates were parsed into NaT.
5. **Over-stated scope.** The old notebook described the data as revenue and claimed LSTM, DBSCAN and Power BI work it didn't contain.

## Reproducing the analysis

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -e /Users/teslim/TeslimWorkSpace/OneDrive-Connector

# run the six stages in order (stage 2 is the only one that contacts OneDrive)
for s in notebook/0*/; do
  n=$(basename "$s"); .venv/bin/jupyter nbconvert --to notebook --execute --inplace "$s$n.ipynb"
done
```

OneDrive access needs the [OneDrive-Connector](https://github.com/UthmanAdeyanju/OneDrive-Connector) `.env` (Azure app client ID, tenant ID and secret). **Source:** [Financial Transactions Dataset: Analytics (Kaggle)](https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets).

## Limitations

The publisher doesn't document how the records were produced, so the findings show the method rather than describe a real bank. Fraud labels cover only part of the transactions. The variance "budget" is a statistical expectation, not an approved plan. See [stage 6](notebook/06-data-visualisation-and-insights/06-data-visualisation-and-insights.ipynb#6.5-Limitations) for the full list.

## Author

**Teslim Adeyanju** | [Portfolio](https://adeyanjuteslim.co.uk) | [LinkedIn](https://www.linkedin.com/in/adeyanjuteslimuthman)

[Previous README (October 2026)](docs/readme-history.md) | [Original README](docs/legacy-readme.md)
