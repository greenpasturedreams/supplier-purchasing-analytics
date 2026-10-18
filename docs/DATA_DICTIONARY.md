# Data dictionary

## Official source

`data/raw/BPI_Challenge_2019.xes.gz` contains the complete original XML, compressed. A trace is a PO line item. An event is one logged activity within that trace. Published source fields are documented by the [challenge organizer](https://icpmconference.org/2019/icpm-2019/contests-challenges/bpi-challenge-2019/). License and acquisition details are in [SOURCE_AND_LICENSE.md](SOURCE_AND_LICENSE.md).

## Case attributes: raw_cases → clean_cases

Identifiers remain text, preserving leading zeros. Raw values and the complete source attributes JSON remain queryable in `raw_cases`. SQL trims strings and maps blanks to null. `source_trace` is a 1-based XML trace position.

| Source XES key | SQL field | Meaning |
|---|---|---|
| concept:name (trace) | case_id | Source purchase-document/item combination; item-grain key |
| Purchasing Document | po_id | Anonymized PO identifier; may have several items |
| Item | item_id | Item number within a PO; not a product/SKU identifier |
| Company | company_id | Anonymized company identifier |
| Vendor | vendor_id | Anonymized supplier identifier |
| Name | vendor_name | Anonymized supplier label |
| Source | source_system | Anonymized source system |
| Item Type | item_type | Standard, Service, Consignment, Third-party, Subcontracting or Limit |
| Item Category | item_category | Matching process category |
| Goods Receipt | goods_receipt_required | Boolean receipt requirement; SQL converts true/false to 1/0 |
| GR-Based Inv. Verif. | gr_based_iv | Boolean goods-receipt-based invoice verification flag |
| Spend classification text | spend_classification | Source classification code, e.g. PR or NPR; codes are not expanded without documentation |
| Spend area text | spend_area | Broad purchasing/material category |
| Sub spend area text | sub_spend_area | More specific source category |
| Document Type | document_type | Source purchasing document type |
| Purch. Doc. Category name | document_category | Purchasing document category; actual XML key differs slightly from prose source description |

## Event attributes: raw_events → clean_events

| Field | Definition / unit |
|---|---|
| event_id | 1-based global import position; not an ERP posting ID |
| case_id | Parent source case identifier |
| event_index | 1-based position within source trace; retained for deterministic timestamp ties |
| activity | `concept:name` at event level, e.g. Record Goods Receipt |
| timestamp_raw | Original `time:timestamp` string, raw table only |
| timestamp_utc | Normalized ISO timestamp with milliseconds and Z suffix |
| resource | Source `org:resource`; null for blank/NONE in clean table |
| cumulative_value_raw | Original Cumulative net worth (EUR) string, raw table only |
| cumulative_value | Numeric form of the anonymized value; never treated as original spend or independent incremental transaction value |
| attributes_json | Full preserved event attribute map, including User, raw table only |

No event records are deduplicated solely on activity/time/resource/value. Rejected events retain source fields and `rejection_reason`.

## Derived tables and processed files

| Table/file | Grain and purpose |
|---|---|
| evaluated_cases / rejected_cases | Source trace with business-validation reason; rejected_cases contains failures |
| evaluated_events / rejected_events | Source event with validation reason; rejected_events CSV contains the 104 exclusions |
| analysis_config | One row: event window, global cutoff, creation cohort dates, 90-day horizon |
| case_milestones | One row per clean PO item; full milestone/flag model |
| cohort_audit | One row per clean item with a mutually exclusive cohort status |
| analysis_cases | One row per eligible material purchase item |
| analysis_cases.csv.gz | All 100,385 main-cohort cases with 23 portable analytical columns |
| analysis_cases_preview.csv | First 500 cases ordered by case_id; browsing preview only |
| metric_observations | Long table: one case/metric/scope observation |
| metric_stats.csv | One scope × group × metric with count, mean, median, P10 and P90 |
| supplier_scorecard.csv | One supplier, all eligible suppliers |
| supplier_context.csv | One supplier with mix-benchmarked receipt coverage and context difference |
| transitions | One observed adjacent-event interval within a main-cohort item's 90-day window |

### Case metrics and flags

| Field | Definition |
|---|---|
| created_at | Earliest Create Purchase Order Item timestamp; exactly one required for cohort inclusion |
| creation_records | Number of creation events |
| horizon_end | Creation plus 90 days; display timestamp (comparison uses Julian-day arithmetic for milliseconds) |
| recorded_events | Total clean events attached to the case across the global analysis window |
| first_gr_any / gr_records_all | First goods receipt / count across the global clean window |
| gr_before_creation | Number of receipts earlier than creation |
| first_gr_90d / last_gr_90d | First/last recorded receipt from creation through day 90, inclusive |
| gr_records_90d | Count of preserved receipt postings within that window |
| receipt_observed_90d | 1 when at least one receipt is recorded by day 90, otherwise 0 |
| first_receipt_days | Creation-to-first-receipt elapsed calendar days; null when no receipt observed by day 90 |
| receipt_span_days | Last minus first observed receipt in calendar days; zero for a single receipt |
| first_confirmation_90d | First Receive Order Confirmation event within the window |
| confirmation_days | First confirmation minus creation, days; null if absent |
| first_invoice_90d | First Record Invoice Receipt within the window |
| first_clear_90d | First Clear Invoice within the window |
| receipt_to_invoice_days | First invoice minus first receipt only when ordered nonnegatively; case-milestone proxy |
| invoice_to_clear_days | First clearing minus first invoice only when ordered nonnegatively; case-milestone proxy |
| price_quantity_change_90d | 1 if Change Price or Change Quantity appears in the 90-day window |
| payment_block_removal_90d | 1 if Remove Payment Block appears in the window; not a count of unique blocked invoices |
| deletion_recorded | Any Delete Purchase Order Item event in the clean global window; does not infer final order status |
| gr_cancellation_recorded | Any Cancel Goods Receipt event in the clean global window; no receipt-level link permits netting |
| timing_issue | Missing/multiple creation, missing comparison dimension, or receipt before creation; otherwise null |
| cohort_status | Included or first failed cohort rule, as defined in SQL |

### Supplier metrics

| Field | Definition |
|---|---|
| eligible_cases / purchase_orders | Item count / distinct PO count for the supplier in the main cohort |
| received_cases | Items with a receipt by day 90 |
| receipt_share_90d | received_cases / eligible_cases; not an on-time delivery rate |
| repeated_receipt_share | Items with >1 posting / eligible_cases |
| change_share | Items with price/quantity change / eligible_cases |
| deletion_share / gr_cancellation_share | Share with each retrospective event flag |
| median_days / p10_days / p90_days | Conditional first-receipt-time percentiles among received_cases |
| p90_p10_spread_days | P90 minus P10; observed variability, not confidence interval |
| benchmarked_cases | Supplier cases in company × material subcategory × matching strata with ≥30 cases |
| observed_receipt_share | Receipt coverage within that benchmarked subset |
| mix_expected_receipt_share | Supplier-weighted mean of those strata's receipt shares, including the supplier itself |
| difference_pp | 100 × (observed_receipt_share − mix_expected_receipt_share) |

### Adjacent-event statistics

`analysis_06.csv` groups intervals by from/to activity. It reports interval count, distinct cases, summed case-days, mean, median, P90 and tied-timestamp share. Intervals are sorted by normalized timestamp and source order. Summed case-days can overlap across items and are not actual staffing hours or savings.

## Eleven analytical query outputs

1. Cohort funnel and exclusions.
2. Qualified supplier variability scorecard and context benchmark.
3. Material-family comparisons, including coverage.
4. Monthly creation cohorts with equal follow-up.
5. Recorded stage intervals and distinct populations.
6. Adjacent-event intervals ranked by summed case-days.
7. Price/quantity-change association.
8. No/one/multiple receipt-posting patterns.
9. Deletion/cancellation sensitivity.
10. Quarantined date records by activity.
11. Full-source item-type/matching-process profile.
