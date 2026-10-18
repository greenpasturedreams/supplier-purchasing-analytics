# Analytical methodology

## Decision and scope

The purchasing manager needs a defensible way to prioritize supplier and process reviews. This analysis examines variation in the time from a purchase-order item's recorded creation to its first recorded goods receipt, alongside purchasing and invoice milestones. It does not measure contractual delivery performance or physical stock availability.

The source is the full BPI Challenge 2019 XES event log, verified against its publisher-supplied checksum. No business records are generated or supplemented. The source is a multinational coatings and paints manufacturer's anonymized purchase-to-pay history. Source attribution, license, checksum and download locations are in [SOURCE_AND_LICENSE.md](SOURCE_AND_LICENSE.md).

## Source grain and safe joins

- One trace is one purchase-order **item**, not one purchase order. Several items can share a PO.
- Each item contains a sequence of event records. A receipt can recur many times.
- `case_id` is the join key. Source purchase document and item identifiers remain text.
- Normalize source events and aggregate them to one row per item **before** calculating supplier item counts. Joining event detail directly to item totals would multiply denominators.
- Preserve case and event attributes in raw JSON alongside flattened fields. The raw XES remains unchanged.

## Cleaning rules

1. Parse the XML with streaming ElementTree to avoid loading the entire document into memory. Namespace prefixes are ignored only for tag identification, not source attribute values.
2. Preserve original timestamp strings and normalize timezone-aware timestamps to UTC at the import boundary. Invalid or timezone-free values remain unavailable and are quarantined by SQL. Source timestamps are valid syntactically, but some are not plausible for this analysis.
3. SQL trims textual identifiers and converts blank dimensions to nulls. It converts documented boolean flags to 0/1. It does not infer categorical values or overwrite source records.
4. SQL quarantines all conflicting duplicate case IDs rather than choosing one arbitrarily. It preserves event records with identical content: without a source posting ID, distinct transactions cannot be safely distinguished from export duplication. The raw audit counts identical-content groups explicitly.
5. The accepted event window is January 1, 2017 through January 31, 2019 UTC. The upper bound is an analytical cutoff tied to the publication period, not a verified ERP extraction timestamp. Earlier/future events are retained in `rejected_events` for inspection. The 104 excluded records are invoice-creation or debit-memo events, not goods receipts. Do not claim all source dates were corrected.
6. Null and `NONE` resources become null. Resource identity is not needed for supplier rankings and is not used for personnel evaluation.
7. Cases with missing or multiple creation milestones, missing comparison dimensions, or receipt postings before creation are excluded from timing comparisons. The source yields no exclusions for these rules, but unit tests verify the behavior.
8. Values labelled EUR in the source were anonymized. They are retained for traceability but not used to claim original purchasing spend, savings, invoice amounts or ROI.

## Main cohort

The cohort contains items created **January 1–September 30, 2018**, followed for **90 elapsed calendar days from their own creation timestamp**. Eligibility requires:

- Item Type = `Standard`.
- Goods Receipt flag = true.
- Item Category = one of the two documented 3-way matching processes.
- Spend area = Packaging, Additives, Latex & Monomers, Pigments & Colorants, Solvents, Specialty Resins, Titanium Dioxides, Commodity Resins, or Chemicals & Intermediates.
- Valid single creation milestone, known supplier/company and no receipt before creation.

This narrows the analysis to material-labelled purchases and excludes service, consignment, resale and capital-process differences. Labels alone do not prove physical delivery semantics in every individual case. The resulting cohort has **100,385 items, 741 suppliers, and one anonymized company identifier**. Do not describe it as a measured comparison of 60 subsidiaries.

Every case has the same maximum outcome window. Creation dates after September are left out to avoid comparing shorter-followed recent purchases with older ones. The 90-day duration is an analytical horizon, **not a promised delivery date or SLA**. The September cohort has lower receipt coverage; this is reported rather than repaired or attributed to seasonality.

Exclusion reasons in `cohort_audit` are mutually exclusive and use the SQL rule order. A case that fails several conditions appears under the first failed rule; counts are not independent counts of every possible problem. The full source remains available in SQLite.

## Receipt measures and incomplete outcomes

`first_receipt_days = julianday(first Record Goods Receipt within 90 days) − julianday(PO creation)`.

- Include exact day 90. Preserve same-day or same-timestamp receipts as zero elapsed days.
- `receipt_share_90d` uses all eligible cases as the denominator.
- First-receipt median/P10/P90 use **only cases with a recorded receipt within 90 days**. They describe a truncated observed-outcome population; they do not estimate the full lead-time distribution of every order.
- A case without a receipt in that window may be deleted, received later, incompletely recorded or unresolved. It is not automatically overdue, currently open, failed, or a stockout. No survival estimate or imputed receipt date is substituted.
- A first receipt may be a partial or administrative posting. `last_gr_90d` is the last observed receipt **within the window**, not the full-delivery completion date.
- `gr_records_90d` counts preserved postings, including content-identical events and ties. Multiple postings are not labelled confirmed partial shipments. Their span is last minus first observed posting.
- Deletion and receipt-cancellation flags are retained in the main population, including flags recorded after the item's first 90 days but before the global cutoff. This is retrospective description, not a prediction-time feature set. A separate sensitivity table excludes them and shows how selection changes coverage.

Supplier scorecards report all eligible suppliers. Comparison charts require at least **50 eligible items and 30 observed receipts**. These are pragmatic display thresholds, not evidence of statistical significance. P10 and P90 are nearest-rank percentiles; the median is the usual average of the middle two observations for even counts. SQL window functions calculate these explicitly. The P90−P10 range measures within-observed-receipt variability, not a confidence interval.

## Comparing supplier mix

Raw supplier comparisons can reflect different materials or ordering practices. The contextual benchmark groups cases by **company × material subcategory × matching process**, requiring at least 30 eligible cases in each stratum. The supplier's expected receipt-by-day-90 share is the average of its cases' stratum rates. Report observed minus expected in percentage points, with benchmarked case coverage.

The focal supplier is included in its stratum baseline. Single-supplier strata will pull comparisons toward zero. The metric is neither a leave-one-out supplier effect nor causal risk adjustment. It does not control for order quantity, terms, urgency, transportation, month or missing product identifiers. Larger effects need case-level investigation, not automatic supplier replacement. Correlated items within POs and suppliers also make naive item-level significance tests inappropriate.

## Purchasing bottleneck measures

The stage chart reports four observed case-level intervals inside the item's 90-day window:

1. PO creation to first receipt.
2. PO creation to first recorded order confirmation.
3. First receipt to first invoice-receipt record, only when that first invoice record is on or after the receipt.
4. First invoice-receipt record to first clearing record, only when that first clearing is on or after the invoice record.

The latter two are **milestone proxies**, not matched receipt/invoice/payment transactions: there are no invoice or posting IDs linking those events. Earlier first invoices/clearings are not replaced by later events just to manufacture a positive duration. Each interval has its own denominator; the medians cannot be added into one end-to-end process time. Missing confirmations do not prove the vendor never confirmed. Contractual payment terms may explain invoice-to-clearing intervals.

The adjacent-event analysis orders events within each case by normalized time, original event index, then positional event ID. It takes `LEAD()` to find the next recorded event. Tied timestamps have zero duration and arbitrary source-order sequence; tied shares are reported. Summed case-days combine elapsed time over many PO items, often concurrently. They are not working hours, plant downtime, unique calendar days or potential savings. Types with fewer than 100 intervals are omitted from the ranked output.

Price/quantity changes are associated with longer recorded receipt times. This is descriptive: complex orders can take longer and longer observation periods before receipt can allow more changes. Events after receipt can also set the 90-day change flag. The project does not establish that changing an order caused a delay.

## Validation

- Reconcile imported case, document and event counts to the published source.
- Reconcile clean plus quarantined records, validate parent keys and unique case grains.
- Check nonnegative elapsed times, bounds, equal follow-up and null treatment.
- Reconcile supplier denominators/numerators to the main cohort.
- Compare the SQL median to pandas and independently recompute receipt times from raw events for 502 dispersed source cases using Python datetime arithmetic.
- Run seven unit tests for day-90 boundaries, exact repeated records, zero duration, missing/late receipts, services, prior receipts, deletion retention, date quarantine, null resources, and percentile logic.
- Visually review all eight final charts and verify README local links.

Results are observational investigation priorities. To study genuine contractual lateness or stockout risk, add the fields described in [WORKPLACE_APPLICATION.md](WORKPLACE_APPLICATION.md).
