"""Generate GitHub narrative and tables from validated, executed analysis outputs."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'processed'


def main():
    validation=json.loads((ROOT/'reports'/'validation.json').read_text())
    assert validation['all_checks_passed'], 'Do not publish unvalidated findings'
    source=json.loads((ROOT/'data'/'raw'/'source_manifest.json').read_text())
    assert source['source_verified']
    audit=json.loads((ROOT/'reports'/'raw_audit.json').read_text())
    stats=pd.read_csv(DATA/'metric_stats.csv')
    overall=stats.loc[stats.scope=='overall'].iloc[0]
    areas=pd.read_csv(DATA/'analysis_03.csv').set_index('spend_area')
    stage=pd.read_csv(DATA/'analysis_05.csv').set_index('group_key')
    sensitivity=pd.read_csv(DATA/'analysis_09.csv').set_index('scenario')
    suppliers=pd.read_csv(DATA/'analysis_02.csv')
    changes=pd.read_csv(DATA/'analysis_07.csv').set_index('price_quantity_change_90d')
    months=pd.read_csv(DATA/'analysis_04.csv')
    sep=months.loc[months.month=='2018-09'].iloc[0]
    best_supported_areas=areas.loc[areas.eligible_cases>=30]
    family_table='\n'.join(
        f'| {name} | {int(r.eligible_cases):,} | {r.receipt_share_90d:.1%} | {r.median_days:.1f} | {r.p90_days:.1f} |'
        for name,r in best_supported_areas.iterrows())
    supplier_table='\n'.join(
        f'| {r.vendor_id} | {r.eligible_cases:,} | {r.receipt_share_90d:.1%} | {r.median_days:.1f} | {r.p90_days:.1f} | {r.p90_p10_spread_days:.1f} |'
        for r in suppliers.nlargest(8,'eligible_cases').itertuples())
    funnel=pd.read_csv(DATA/'analysis_01.csv')
    funnel_table='\n'.join(f'| {r.cohort_status.replace("_"," ")} | {r.cases:,} |' for r in funnel.itertuples())
    excluded=sensitivity.loc['Exclude deletion or receipt cancellation']
    cleared=stage.loc['First invoice record to first clearing']
    text=f'''# Supplier Lead-Time Variability & Purchasing Bottlenecks

**A SQL and Python analysis of real, anonymized purchasing records from a multinational paints and coatings manufacturer, using the BPI Challenge 2019 dataset.**

I built a reproducible pipeline to turn a nested purchasing event log into a supplier scorecard, receipt-time comparisons and process investigation priorities. The analysis distinguishes recorded elapsed time from contractual lateness, first receipt from full delivery, and missing outcomes from confirmed open orders.

## Business problem

A purchasing manager wants to understand which suppliers and material categories have variable receipt times and where purchasing transactions spend time between recorded milestones.

The project answers:

- How variable is the time from PO item creation to first recorded goods receipt?
- Which suppliers warrant a closer review after considering material mix and sample size?
- Which purchasing and invoice intervals account for substantial elapsed time?
- How do receipt coverage, order changes and repeated receipt postings affect interpretation?

The dataset has no promised-delivery dates, usable inventory balances or material-consumption history. Therefore, this project evaluates **recorded receipt times and purchasing processes**, rather than on-time delivery, stockouts or supplier-caused delays.

## Key findings

| Measure | Result | Interpretation |
|---|---:|---|
| Eligible material purchase items | {validation['eligible_cases']:,} | Standard material-labelled items created January–September 2018 |
| Suppliers represented | {validation['eligible_suppliers']:,} | Anonymized supplier identifiers |
| Receipt recorded within 90 days | {validation['receipt_share_90d']:.1%} | {validation['received_by_day_90']:,} items; a coverage measure, not an on-time rate |
| Median time to first receipt | {overall.median_days:.1f} days | Among items with an observed receipt within 90 days |
| P90 time to first receipt | {overall.p90_days:.1f} days | The 90th percentile of that observed-receipt population |
| Multiple receipt postings within 90 days | {validation['multiple_receipt_cases']:,} items | Posting multiplicity does not prove partial physical delivery |

Three findings shape the recommended investigations:

1. **Material mix changes the comparison.** Titanium Dioxides has a {areas.loc['Titanium Dioxides','median_days']:.1f}-day median and {areas.loc['Titanium Dioxides','receipt_share_90d']:.1%} receipt coverage, versus {areas.loc['Packaging','median_days']:.1f} days and {areas.loc['Packaging','receipt_share_90d']:.1%} for Packaging. Different sourcing arrangements may explain part of the gap.
2. **Invoice clearing deserves a separate process review.** The interval from first invoice receipt record to first clearing record has a {cleared.median_days:.1f}-day median across {int(cleared.observations):,} eligible milestone pairs. Payment terms and transaction matching must be checked before calling this avoidable delay.
3. **Selection changes apparent performance.** Excluding items with deletion or receipt-cancellation records raises receipt coverage from {validation['receipt_share_90d']:.1%} to {excluded.receipt_share_90d:.1%}. This changes the population; it does not improve the underlying process.

## Data source and provenance

**Source:** van Dongen, Boudewijn (2019), *BPI Challenge 2019*, 4TU.ResearchData. [Dataset DOI](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1) · [Official challenge description](https://icpmconference.org/2019/icpm-2019/contests-challenges/bpi-challenge-2019/).

The complete source contains **{validation['source_cases']:,} PO line items**, **{validation['purchase_orders']:,} purchase documents**, and **{validation['source_events']:,} event records**. Each line item can have several receipts, invoices or changes. Source company/vendor identifiers and monetary values are anonymized.

The organizer's compressed XES file is included in `data/raw/`. Its decompressed XML matches the publisher's checksum:

```text
MD5: {source['xml_md5']}
Original XML bytes: {source['xml_bytes']:,}
```

The dataset license is **CC BY 4.0**. The original source is preserved; CSVs, figures and findings are derived analytical outputs. See [source attribution and license](docs/SOURCE_AND_LICENSE.md) and the [source manifest](data/raw/source_manifest.json).

## Analytical design

**Grain:** one purchase-order item. **Unit of time:** elapsed calendar days using UTC timestamps.

The main cohort includes January–September 2018 creations, Standard item type, a required goods receipt, a 3-way matching process and specified manufacturing-material categories. Each item is observed from creation through **day 90 inclusive**. That horizon is an analytical choice, not a delivery promise. The resulting cohort represents **{validation['eligible_companies']} anonymized company identifier**, rather than all of the manufacturer's subsidiaries.

| Cohort status | Items |
|---|---:|
{funnel_table}

Exclusion reasons are mutually exclusive and follow rule priority. The complete source remains available in the local SQLite database. The main cohort retains deletion and receipt-cancellation flags; a separate sensitivity query shows the effect of excluding those cases.

**Receipt coverage uses all eligible cases. Receipt-time percentiles use only cases with a recorded receipt within 90 days.** Items with no receipt in the window remain in the coverage denominator and have null time values. This avoids treating missing receipts as zero-day deliveries, but does not estimate the full lead-time distribution of unreceived or later-received items.

The [methodology](docs/METHODOLOGY.md) explains the cohort, censoring limits, repeat postings, benchmark and event-pairing rules. The [data dictionary](docs/DATA_DICTIONARY.md) defines every source and derived field.

## Workflow and SQL

`Verified XES → source-preserving SQLite tables → SQL cleaning and milestones → item-level cohort → supplier/process summaries → Python EDA → README`

**Tools:** Python 3.12, SQLite, pandas, NumPy, Matplotlib and standard-library XML/gzip tools. No database server or paid software is required.

### Source import and cleaning

[import_xes.py](src/import_xes.py) streams the original XML and preserves source attributes in JSON. Timestamp syntax checking and UTC normalization occur at the import boundary. [01_clean_transform.sql](sql/01_clean_transform.sql) owns business cleaning, quarantine, milestone extraction, cohort selection and calculations:

1. Standardize blank strings, identifiers and documented boolean flags.
2. Preserve repeated event content unless a reliable posting key establishes duplication.
3. Quarantine dates outside the analytical window, retaining their original values.
4. Build one row per PO item before calculating supplier denominators.
5. Extract first and repeated receipt milestones within an equal 90-day horizon.
6. Retain unavailable outcomes, deletion/cancellation flags and exclusion reasons.
7. Calculate exact medians and nearest-rank P10/P90 with SQL window functions.
8. Build supplier scorecards, contextual benchmarks and adjacent-event intervals.

The raw audit found **{validation['rejected_events']} out-of-window events**, including dates before 2017 or after January 2019, and **{audit['identical_event_content'][0]['additional_rows']:,} additional identical-content event records**. The former are quarantined; the latter are preserved because identical content alone does not prove duplicate transactions.

Example first-receipt extraction pattern:

```sql
MIN(CASE
    WHEN e.activity = 'Record Goods Receipt'
     AND e.timestamp_utc >= d.created_at
     AND JULIANDAY(e.timestamp_utc) <= JULIANDAY(d.created_at) + 90
    THEN e.timestamp_utc
END) AS first_gr_90d
```

Example supplier coverage query after the model has run:

```sql
SELECT
    vendor_id,
    COUNT(*) AS eligible_items,
    SUM(receipt_observed_90d) AS items_with_receipt,
    AVG(receipt_observed_90d) AS receipt_share_90d
FROM analysis_cases
GROUP BY vendor_id;
```

[02_analysis.sql](sql/02_analysis.sql) provides **11 executable analytical queries**: cohort funnel, supplier variability, material families, monthly cohorts, stage intervals, adjacent-event intervals, order changes, receipt multiplicity, deletion/cancellation sensitivity, date quarantine and the source process profile. Executed results are saved under `data/processed/analysis_01.csv` through `analysis_11.csv`.

## Exploratory analysis

### 1. Distribution of first recorded receipt times

![Distribution of first recorded receipt times](reports/figures/01_receipt_time_distribution.png)

The median is {overall.median_days:.1f} days and P90 is {overall.p90_days:.1f} days among {validation['received_by_day_90']:,} observed outcomes. The distribution has a long right tail. The {validation['no_receipt_by_day_90']:,} items with no receipt by day 90 are reported separately, rather than inserted into the histogram as zeroes or presumed 90-day completions.

### 2. Supplier variability with coverage shown

![Suppliers with wide recorded receipt-time ranges](reports/figures/02_supplier_variability.png)

The chart shows the 12 widest P10–P90 ranges among **{validation['qualified_suppliers']} qualified suppliers** with at least 50 eligible items and 30 observed receipts. The dot is the median; the line is the observed variability range. Labels show item counts and receipt coverage. These are review candidates, not a ranking of supplier fault.

For comparison, the eight largest qualified suppliers are:

| Supplier | Eligible items | Receipt by day 90 | Median days | P90 days | P90−P10 days |
|---|---:|---:|---:|---:|---:|
{supplier_table}

### 3. Material-family context

![Receipt times and coverage by material family](reports/figures/03_material_family_comparison.png)

| Material family | Eligible items | Receipt by day 90 | Median days | P90 days |
|---|---:|---:|---:|---:|
{family_table}

Only families with at least 30 eligible items are shown here; the full SQL export retains the single Chemicals & Intermediates item. Packaging contributes {areas.loc['Packaging','eligible_cases']/validation['eligible_cases']:.1%} of the main cohort, so an overall figure is heavily influenced by that family. Titanium Dioxides warrants a review of sourcing terms and receipt recording, not an assumption that its suppliers missed a promise.

### 4. Monthly cohorts with equal follow-up

![Monthly receipt-time and coverage trends](reports/figures/04_monthly_cohorts.png)

Each creation month has the same 90-day outcome window. September receipt coverage is {sep.receipt_share_90d:.1%}, while its observed median remains {sep.median_days:.1f} days. This is a useful reminder that a stable median among received items can coexist with fewer observed receipts overall. Changes in deletion status, material mix and recording should be checked before interpreting the pattern.

### 5. Purchasing and invoice milestone intervals

![Recorded purchasing stage intervals](reports/figures/05_purchasing_stage_intervals.png)

Invoice receipt to first clearing has the longest median of the four milestone proxies shown. Investigate payment terms, blocks and posting practices before interpreting it as an inefficiency. Each interval has a different population, and receipt/invoice/payment records cannot be transaction-matched from these fields. The stage medians must not be added into one process duration.

### 6. Supplier comparisons in purchasing-mix context

![Supplier receipt coverage relative to its purchasing mix](reports/figures/06_supplier_mix_context.png)

The benchmark compares receipt-by-day-90 coverage within company × material subcategory × matching process groups containing at least 30 items. It reports observed minus mix-expected coverage in percentage points for the 15 largest qualified suppliers with sufficient benchmark coverage. The benchmark includes the focal supplier and is descriptive; a large supplier can influence its own baseline. It is not an isolated supplier effect or contractual service rating.

### 7. Adjacent-event intervals identify investigation priorities

![Adjacent-event intervals ranked by summed elapsed case-days](reports/figures/07_event_interval_bottlenecks.png)

The interval from Record Invoice Receipt to Clear Invoice accounts for the largest summed elapsed case-days among the displayed transitions. This ranking combines interval frequency and duration. Different PO items often run concurrently: these totals are not labor time, unique calendar days, production downtime or recoverable savings.

### 8. Repeated receipts and incomplete outcomes

![Receipt posting patterns and spans](reports/figures/08_repeated_receipt_postings.png)

There are {validation['multiple_receipt_cases']:,} items with multiple receipt postings in the window. These can represent separate receipts, recurring postings or identical-content events. First receipt and last observed receipt are not certified delivery-completion milestones. Quantities and unique posting/reversal links would be required to measure in-full delivery.

The order-change query also finds a {changes.loc[1,'median_days']:.1f}-day observed median for items with price/quantity changes versus {changes.loc[0,'median_days']:.1f} days without them. This is an association: complexity, longer exposure and changes made after receipt can affect the result.

## Recommendations

| Priority | Proposed action | Evidence or next measurement |
|---|---|---|
| Review long-tail materials | Inspect Titanium Dioxides and other long-tail material categories with buyers | Compare agreed sourcing lead times, order-release timing, transport and physical arrival |
| Review supplier variability | Start with suppliers having adequate samples, wide receipt-time ranges and relevant material comparisons | Inspect matched material/order examples and missing-outcome reasons |
| Explain unreceived records | Separate deleted, superseded, reversed, later-received and genuinely open items | Use current line status, receipt quantities and reversal links |
| Review invoice clearing | Check contractual terms and payment blocks before seeking faster clearing | Obtain invoice IDs, due dates, payment dates and blocking reasons |
| Improve the next analysis | Add promised dates, material IDs, quantities and time-phased stock/demand | Enables on-time/in-full and stockout analysis that this source cannot support |

See [applying the analysis at work](docs/WORKPLACE_APPLICATION.md) for concrete ERP fields, management questions and a practical review sequence.

## Reproduce the project

Use Python 3.12. The package includes the verified compressed source and completed outputs, so network access is not needed to rebuild it.

```powershell
# Windows PowerShell, from this project's root folder
py -3.12 -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python run_project.py
```

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_project.py
```

The pipeline verifies the source checksum, imports all events, profiles the source, runs SQL, validates results, exports data, creates eight figures, refreshes this README and runs the unit tests. It replaces generated project outputs. The full local database is large because it preserves raw attributes and intermediate SQL tables; allow several GB of free disk space. The import is streamed, and processing can take several minutes depending on your computer.

If the compressed source has been removed, retrieve it from the official hosts with:

```bash
python run_project.py --download
```

For SQL/report iteration after a successful import:

```bash
python run_project.py --skip-import
```

Individual stages:

```bash
python src/acquire_data.py
python src/import_xes.py
python src/profile_source.py
python src/build_analysis.py
python src/eda.py
python src/write_readme.py
python -m unittest discover -s tests -v
```

Open `data/purchasing.db` in a SQLite client to inspect raw tables and run queries. SQL uses SQLite date functions and window functions. The raw XES and full processed case file are compressed; pandas reads `data/processed/analysis_cases.csv.gz` directly with `pd.read_csv()`.

## Validation and limitations

The executed audit passes **{len(validation['checks'])} validation checks**, including published source counts, source-to-clean reconciliation, parent keys, cohort grain, time bounds, missing outcomes, supplier denominators, percentile ordering and an independent calculation from raw events for **{validation['independent_sample_cases']} cases**. See [validation.json](reports/validation.json). Seven SQL edge-case tests cover the day-90 boundary, zero-duration receipts, repeated postings, missing receipts, excluded processes, deletions, date quarantine and percentile calculation.

The analysis is historical and observational. The main cohort is concentrated in Packaging and represents one anonymized company ID. Supplier mix, planned lead times, order complexity and recording practices affect comparisons. Conditional receipt-time percentiles omit unreceived/later-received outcomes. Event sequences do not establish causation, contractual lateness, in-full delivery, stockout risk or savings. Anonymized financial values are not reported as original spend. Source dates after January 2019 are excluded rather than treated as verified future business history.

## Repository structure

```text
data/
  raw/
    BPI_Challenge_2019.xes.gz   # Complete, verified official source
    publisher_metadata.json
    source_manifest.json
  processed/
    analysis_cases.csv.gz     # All main-cohort item metrics
    analysis_cases_preview.csv
    analysis_01.csv ... analysis_11.csv
    supplier_scorecard.csv
    supplier_context.csv
    metric_stats.csv
    analysis_config.csv
    rejected_events.csv
docs/
  DATA_DICTIONARY.md
  METHODOLOGY.md
  SOURCE_AND_LICENSE.md
  WORKPLACE_APPLICATION.md
reports/
  figures/                    # Eight finished PNG charts
  source_profile.json
  raw_audit.json
  validation.json
sql/
  01_clean_transform.sql
  02_analysis.sql
src/
  acquire_data.py
  import_xes.py
  profile_source.py
  build_analysis.py
  eda.py
  write_readme.py
tests/
  test_sql_rules.py
requirements.txt
run_project.py
README.md
```

## Portfolio skills demonstrated

Verified public-data acquisition, streaming XML parsing, relational modeling, source-preserving cleaning, SQL CTEs and window functions, exact percentile calculation, follow-up-aware cohort design, supplier benchmarking, pandas/Matplotlib EDA, edge-case tests and evidence-based operational recommendations.

## Publish on GitHub

Suggested repository name: **`supplier-purchasing-analytics`**.

Suggested description: **SQL and Python analysis of supplier receipt-time variability and purchasing bottlenecks using real BPI Challenge 2019 manufacturing records.**

Upload the **contents of this project folder** to the repository root, including the data, docs, reports, sql, src and tests folders. Keep `README.md` at the root so the project and charts display on the main page. The local SQLite database and runtime folders are excluded from the upload package. Retain the source citation and license notice.
'''
    (ROOT/'README.md').write_text(text,encoding='utf-8')
    print('GitHub README generated from validated results')


if __name__=='__main__':
    main()
