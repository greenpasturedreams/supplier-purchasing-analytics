-- SQLite 3.35+. Source XES is immutable; importer preserves every attribute in JSON.
-- Timestamp syntax/UTC conversion occurs at the XML import boundary. All business
-- cleaning, milestones, cohorts, joins and elapsed-time calculations below are SQL.
DROP TABLE IF EXISTS analysis_config;
CREATE TABLE analysis_config AS SELECT
 '2017-01-01T00:00:00.000Z' earliest_event,
 '2019-01-31T23:59:59.999Z' as_of_utc,
 '2018-01-01T00:00:00.000Z' cohort_start,
 '2018-10-01T00:00:00.000Z' cohort_end_exclusive,
 90 followup_days;

DROP TABLE IF EXISTS evaluated_cases;
CREATE TABLE evaluated_cases AS
WITH keys AS (SELECT case_id,COUNT(*) n FROM raw_cases GROUP BY case_id)
SELECT r.*,
 CASE WHEN NULLIF(TRIM(r.case_id),'') IS NULL THEN 'missing_case_id'
 WHEN k.n<>1 THEN 'duplicate_case_id'
 WHEN NULLIF(TRIM(po_id),'') IS NULL OR NULLIF(TRIM(item_id),'') IS NULL THEN 'missing_po_item'
 WHEN goods_receipt_required NOT IN ('true','false') OR goods_receipt_required IS NULL
   OR gr_based_iv NOT IN ('true','false') OR gr_based_iv IS NULL THEN 'invalid_boolean'
 ELSE NULL END rejection_reason
FROM raw_cases r JOIN keys k ON r.case_id=k.case_id;
DROP TABLE IF EXISTS rejected_cases;
CREATE TABLE rejected_cases AS SELECT * FROM evaluated_cases WHERE rejection_reason IS NOT NULL;
DROP TABLE IF EXISTS clean_cases;
CREATE TABLE clean_cases AS
SELECT source_trace,TRIM(case_id) case_id,TRIM(po_id) po_id,TRIM(item_id) item_id,
 NULLIF(TRIM(company_id),'') company_id,NULLIF(TRIM(vendor_id),'') vendor_id,
 NULLIF(TRIM(vendor_name),'') vendor_name,NULLIF(TRIM(source_system),'') source_system,
 NULLIF(TRIM(item_type),'') item_type,NULLIF(TRIM(item_category),'') item_category,
 CASE goods_receipt_required WHEN 'true' THEN 1 ELSE 0 END goods_receipt_required,
 CASE gr_based_iv WHEN 'true' THEN 1 ELSE 0 END gr_based_iv,
 NULLIF(TRIM(spend_classification),'') spend_classification,
 NULLIF(TRIM(spend_area),'') spend_area,NULLIF(TRIM(sub_spend_area),'') sub_spend_area,
 NULLIF(TRIM(document_type),'') document_type,NULLIF(TRIM(document_category),'') document_category
FROM evaluated_cases WHERE rejection_reason IS NULL;
CREATE UNIQUE INDEX clean_cases_pk ON clean_cases(case_id);

DROP TABLE IF EXISTS evaluated_events;
CREATE TABLE evaluated_events AS
SELECT r.*,
 CASE WHEN c.case_id IS NULL THEN 'missing_or_rejected_parent'
 WHEN NULLIF(TRIM(activity),'') IS NULL THEN 'missing_activity'
 WHEN timestamp_utc IS NULL THEN 'invalid_timestamp'
 WHEN timestamp_utc<cfg.earliest_event OR timestamp_utc>cfg.as_of_utc THEN 'outside_analysis_window'
 ELSE NULL END rejection_reason
FROM raw_events r LEFT JOIN clean_cases c ON r.case_id=c.case_id CROSS JOIN analysis_config cfg;
DROP TABLE IF EXISTS rejected_events;
CREATE TABLE rejected_events AS SELECT * FROM evaluated_events WHERE rejection_reason IS NOT NULL;
DROP TABLE IF EXISTS clean_events;
CREATE TABLE clean_events AS
SELECT event_id,TRIM(case_id) case_id,event_index,TRIM(activity) activity,timestamp_utc,
 CASE WHEN resource IS NULL OR TRIM(resource) IN ('','NONE') THEN NULL ELSE TRIM(resource) END resource,
 cumulative_value
FROM evaluated_events WHERE rejection_reason IS NULL;
-- Identical activity/time/value records are NOT blindly deduplicated: no source
-- posting identifier proves they are duplicate transactions. event_id is positional.
CREATE UNIQUE INDEX clean_events_pk ON clean_events(event_id);
CREATE INDEX clean_events_case_time ON clean_events(case_id,timestamp_utc,event_index);

DROP TABLE IF EXISTS case_milestones;
CREATE TABLE case_milestones AS
WITH create_dates AS (
 SELECT case_id,MIN(timestamp_utc) created_at,
 COUNT(*) creation_records FROM clean_events
 WHERE activity='Create Purchase Order Item' GROUP BY case_id
), observed AS (
 SELECT c.*,d.created_at,d.creation_records,
 DATETIME(d.created_at,'+'||cfg.followup_days||' days') horizon_end,
 COUNT(e.event_id) recorded_events,
 MIN(CASE WHEN e.activity='Record Goods Receipt' THEN e.timestamp_utc END) first_gr_any,
 SUM(CASE WHEN e.activity='Record Goods Receipt' AND e.timestamp_utc<d.created_at THEN 1 ELSE 0 END) gr_before_creation,
 SUM(CASE WHEN e.activity='Record Goods Receipt' THEN 1 ELSE 0 END) gr_records_all,
 SUM(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Record Goods Receipt' THEN 1 ELSE 0 END) gr_records_90d,
 MIN(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Record Goods Receipt' THEN e.timestamp_utc END) first_gr_90d,
 MAX(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Record Goods Receipt' THEN e.timestamp_utc END) last_gr_90d,
 MIN(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Receive Order Confirmation' THEN e.timestamp_utc END) first_confirmation_90d,
 MIN(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Record Invoice Receipt' THEN e.timestamp_utc END) first_invoice_90d,
 MIN(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Clear Invoice' THEN e.timestamp_utc END) first_clear_90d,
 MAX(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity IN ('Change Price','Change Quantity') THEN 1 ELSE 0 END) price_quantity_change_90d,
 MAX(CASE WHEN e.timestamp_utc>=d.created_at
   AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(d.created_at)+cfg.followup_days
   AND e.activity='Remove Payment Block' THEN 1 ELSE 0 END) payment_block_removal_90d,
 MAX(CASE WHEN e.activity='Delete Purchase Order Item' THEN 1 ELSE 0 END) deletion_recorded,
 MAX(CASE WHEN e.activity='Cancel Goods Receipt' THEN 1 ELSE 0 END) gr_cancellation_recorded
 FROM clean_cases c LEFT JOIN create_dates d USING(case_id)
 LEFT JOIN clean_events e USING(case_id) CROSS JOIN analysis_config cfg
 GROUP BY c.case_id
)
SELECT o.*,
 CASE WHEN created_at IS NULL THEN 'missing_creation'
 WHEN creation_records<>1 THEN 'multiple_creation_records'
 WHEN company_id IS NULL OR vendor_id IS NULL THEN 'missing_comparison_dimension'
 WHEN gr_before_creation>0 THEN 'receipt_before_creation'
 ELSE NULL END timing_issue,
 CASE WHEN first_gr_90d IS NOT NULL THEN 1 ELSE 0 END receipt_observed_90d,
 JULIANDAY(first_gr_90d)-JULIANDAY(created_at) first_receipt_days,
 JULIANDAY(last_gr_90d)-JULIANDAY(first_gr_90d) receipt_span_days,
 JULIANDAY(first_confirmation_90d)-JULIANDAY(created_at) confirmation_days,
 CASE WHEN first_invoice_90d>=first_gr_90d
 THEN JULIANDAY(first_invoice_90d)-JULIANDAY(first_gr_90d) END receipt_to_invoice_days,
 CASE WHEN first_clear_90d>=first_invoice_90d
 THEN JULIANDAY(first_clear_90d)-JULIANDAY(first_invoice_90d) END invoice_to_clear_days
FROM observed o;
CREATE UNIQUE INDEX case_milestones_pk ON case_milestones(case_id);

-- Standard material purchases only; exclude services, resale, capital and other
-- categories whose receipt postings can represent a different business process.
DROP TABLE IF EXISTS cohort_audit;
CREATE TABLE cohort_audit AS
SELECT m.*,
 CASE WHEN timing_issue IS NOT NULL THEN timing_issue
 WHEN created_at<cfg.cohort_start OR created_at>=cfg.cohort_end_exclusive THEN 'outside_cohort_dates'
 WHEN JULIANDAY(created_at)+cfg.followup_days>JULIANDAY(cfg.as_of_utc) THEN 'insufficient_followup'
 WHEN item_type<>'Standard' OR item_type IS NULL THEN 'nonstandard_item'
 WHEN goods_receipt_required<>1 THEN 'receipt_not_required'
 WHEN item_category NOT IN ('3-way match, invoice before GR','3-way match, invoice after GR') THEN 'different_matching_process'
 WHEN spend_area IS NULL OR spend_area NOT IN
 ('Packaging','Additives','Latex & Monomers','Pigments & Colorants','Solvents',
  'Specialty Resins','Titanium Dioxides','Commodity Resins','Chemicals & Intermediates') THEN 'outside_material_scope'
 ELSE 'Included' END cohort_status
FROM case_milestones m CROSS JOIN analysis_config cfg;
DROP TABLE IF EXISTS analysis_cases;
CREATE TABLE analysis_cases AS SELECT * FROM cohort_audit WHERE cohort_status='Included';
CREATE UNIQUE INDEX analysis_cases_pk ON analysis_cases(case_id);

-- Deletions and reversals are retained and flagged in the main cohort. Removing
-- them would preferentially keep uncomplicated purchases. Sensitivity excludes them.
-- A missing receipt by day 90 is not automatically an open order or stockout.

DROP TABLE IF EXISTS transitions;
CREATE TABLE transitions AS
WITH ordered AS (
 SELECT e.case_id,e.event_id,e.activity from_activity,e.timestamp_utc from_time,
 LEAD(e.activity) OVER(PARTITION BY e.case_id ORDER BY e.timestamp_utc,e.event_index,e.event_id) to_activity,
 LEAD(e.timestamp_utc) OVER(PARTITION BY e.case_id ORDER BY e.timestamp_utc,e.event_index,e.event_id) to_time
 FROM clean_events e JOIN analysis_cases c USING(case_id)
 WHERE e.timestamp_utc>=c.created_at AND JULIANDAY(e.timestamp_utc)<=JULIANDAY(c.created_at)+90
)
SELECT *,JULIANDAY(to_time)-JULIANDAY(from_time) elapsed_days,
 CASE WHEN to_time=from_time THEN 1 ELSE 0 END timestamp_tie
FROM ordered WHERE to_time IS NOT NULL;

-- Generic long table supports exact SQL medians and nearest-rank percentiles.
DROP TABLE IF EXISTS metric_observations;
CREATE TABLE metric_observations AS
SELECT 'overall' scope,'All material purchases' group_key,'first_receipt_days' metric,case_id,first_receipt_days value
 FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'supplier',vendor_id,'first_receipt_days',case_id,first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'spend_area',spend_area,'first_receipt_days',case_id,first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'company',company_id,'first_receipt_days',case_id,first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'month',SUBSTR(created_at,1,7),'first_receipt_days',case_id,first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'change',CAST(price_quantity_change_90d AS TEXT),'first_receipt_days',case_id,first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1
UNION ALL SELECT 'stage','PO creation to first receipt','elapsed_days',case_id,first_receipt_days FROM analysis_cases WHERE first_receipt_days IS NOT NULL
UNION ALL SELECT 'stage','PO creation to first confirmation','elapsed_days',case_id,confirmation_days FROM analysis_cases WHERE confirmation_days IS NOT NULL
UNION ALL SELECT 'stage','First receipt to first invoice record','elapsed_days',case_id,receipt_to_invoice_days FROM analysis_cases WHERE receipt_to_invoice_days IS NOT NULL
UNION ALL SELECT 'stage','First invoice record to first clearing','elapsed_days',case_id,invoice_to_clear_days FROM analysis_cases WHERE invoice_to_clear_days IS NOT NULL
UNION ALL SELECT 'receipt_span','Repeated receipt postings','receipt_span_days',case_id,receipt_span_days FROM analysis_cases WHERE gr_records_90d>1;

DROP TABLE IF EXISTS metric_stats;
CREATE TABLE metric_stats AS
WITH ranked AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY scope,group_key,metric ORDER BY value,case_id) rn,
 COUNT(*) OVER(PARTITION BY scope,group_key,metric) n FROM metric_observations
)
SELECT scope,group_key,metric,MAX(n) observations,AVG(value) mean_days,
 AVG(CASE WHEN rn IN ((n+1)/2,(n+2)/2) THEN value END) median_days,
 MAX(CASE WHEN rn=(n+9)/10 THEN value END) p10_days,
 MAX(CASE WHEN rn=(9*n+9)/10 THEN value END) p90_days
FROM ranked GROUP BY scope,group_key,metric;

DROP TABLE IF EXISTS supplier_scorecard;
CREATE TABLE supplier_scorecard AS
WITH coverage AS (
 SELECT vendor_id,COUNT(*) eligible_cases,COUNT(DISTINCT po_id) purchase_orders,
 SUM(receipt_observed_90d) received_cases,
 AVG(receipt_observed_90d) receipt_share_90d,
 AVG(CASE WHEN gr_records_90d>1 THEN 1.0 ELSE 0 END) repeated_receipt_share,
 AVG(price_quantity_change_90d) change_share,
 AVG(deletion_recorded) deletion_share,AVG(gr_cancellation_recorded) gr_cancellation_share
 FROM analysis_cases GROUP BY vendor_id
)
SELECT c.*,s.median_days,s.p10_days,s.p90_days,s.p90_days-s.p10_days p90_p10_spread_days
FROM coverage c LEFT JOIN metric_stats s ON s.scope='supplier' AND c.vendor_id=s.group_key;

-- Mix-aware descriptive benchmark: compare outcomes within company × subcategory ×
-- matching process. Minimum 30 cases per stratum. This includes the focal supplier,
-- so it is a contextual baseline, not a leave-one-out or causal supplier effect.
DROP TABLE IF EXISTS supplier_context;
CREATE TABLE supplier_context AS
WITH benchmarks AS (
 SELECT company_id,COALESCE(sub_spend_area,'Unknown') sub_spend_area,item_category,
 COUNT(*) stratum_cases,AVG(receipt_observed_90d) benchmark_receipt_share
 FROM analysis_cases GROUP BY 1,2,3 HAVING COUNT(*)>=30
)
SELECT c.vendor_id,COUNT(*) benchmarked_cases,
 AVG(c.receipt_observed_90d) observed_receipt_share,
 AVG(b.benchmark_receipt_share) mix_expected_receipt_share,
 100*(AVG(c.receipt_observed_90d)-AVG(b.benchmark_receipt_share)) difference_pp
FROM analysis_cases c JOIN benchmarks b ON c.company_id=b.company_id
 AND COALESCE(c.sub_spend_area,'Unknown')=b.sub_spend_area AND c.item_category=b.item_category
GROUP BY c.vendor_id;
