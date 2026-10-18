-- 01. Cohort funnel: mutually exclusive reasons in business-rule priority order.
SELECT cohort_status,COUNT(*) cases FROM cohort_audit GROUP BY 1 ORDER BY cases DESC;

-- 02. Supplier scorecard. Thresholds are analytical display choices, not quality targets.
SELECT s.*,c.benchmarked_cases,c.observed_receipt_share,c.mix_expected_receipt_share,c.difference_pp
FROM supplier_scorecard s LEFT JOIN supplier_context c USING(vendor_id)
WHERE s.eligible_cases>=50 AND s.received_cases>=30
ORDER BY s.p90_p10_spread_days DESC,s.eligible_cases DESC;

-- 03. Product-family differences with coverage denominators retained.
SELECT c.spend_area,COUNT(*) eligible_cases,SUM(c.receipt_observed_90d) received_cases,
 AVG(c.receipt_observed_90d) receipt_share_90d,s.median_days,s.p90_days
FROM analysis_cases c LEFT JOIN metric_stats s ON s.scope='spend_area' AND s.group_key=c.spend_area
GROUP BY c.spend_area ORDER BY eligible_cases DESC;

-- 04. Jan-Sep creation cohorts get the same 90-day outcome window.
SELECT SUBSTR(c.created_at,1,7) month,COUNT(*) eligible_cases,
 AVG(c.receipt_observed_90d) receipt_share_90d,s.median_days,s.p90_days,
 AVG(c.deletion_recorded) deletion_share,AVG(c.gr_cancellation_recorded) receipt_cancellation_share
FROM analysis_cases c LEFT JOIN metric_stats s ON s.scope='month' AND s.group_key=SUBSTR(c.created_at,1,7)
GROUP BY 1 ORDER BY 1;

-- 05. Stage proxies are case milestones, not matched invoice/payment transactions.
SELECT * FROM metric_stats WHERE scope='stage' ORDER BY median_days DESC;

-- 06. Adjacent event intervals: elapsed calendar time, not labor time or savings.
WITH ranked AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY from_activity,to_activity ORDER BY elapsed_days,event_id) rn,
 COUNT(*) OVER(PARTITION BY from_activity,to_activity) n FROM transitions
)
SELECT from_activity,to_activity,COUNT(*) intervals,COUNT(DISTINCT case_id) cases,
 SUM(elapsed_days) total_case_days,AVG(elapsed_days) mean_days,
 AVG(CASE WHEN rn IN ((n+1)/2,(n+2)/2) THEN elapsed_days END) median_days,
 MAX(CASE WHEN rn=(9*n+9)/10 THEN elapsed_days END) p90_days,
 AVG(timestamp_tie) tied_timestamp_share
FROM ranked GROUP BY 1,2 HAVING COUNT(*)>=100 ORDER BY total_case_days DESC;

-- 07. Price/quantity changes: association only. More elapsed time allows more changes.
SELECT c.price_quantity_change_90d,COUNT(*) eligible_cases,AVG(c.receipt_observed_90d) receipt_share_90d,
 s.median_days,s.p90_days FROM analysis_cases c LEFT JOIN metric_stats s
 ON s.scope='change' AND s.group_key=CAST(c.price_quantity_change_90d AS TEXT)
GROUP BY 1;

-- 08. Receipt multiplicity includes ties/identical content. It is not confirmed partial delivery.
SELECT CASE WHEN gr_records_90d=0 THEN 'No receipt by day 90'
 WHEN gr_records_90d=1 THEN 'One receipt posting' ELSE 'Multiple receipt postings' END receipt_pattern,
 COUNT(*) cases FROM analysis_cases GROUP BY 1 ORDER BY cases DESC;

-- 09. Sensitivity: keep selection differences visible, never replace the main population.
WITH groups AS (
 SELECT 'All eligible' scenario,* FROM analysis_cases
 UNION ALL SELECT 'Exclude deletion or receipt cancellation',* FROM analysis_cases
 WHERE deletion_recorded=0 AND gr_cancellation_recorded=0
), ranked AS (
 SELECT scenario,first_receipt_days,ROW_NUMBER() OVER(PARTITION BY scenario ORDER BY first_receipt_days,case_id) rn,
 COUNT(*) OVER(PARTITION BY scenario) n FROM groups WHERE receipt_observed_90d=1
), medians AS (
 SELECT scenario,AVG(CASE WHEN rn IN ((n+1)/2,(n+2)/2) THEN first_receipt_days END) median_days
 FROM ranked GROUP BY 1
)
SELECT g.scenario,COUNT(*) eligible_cases,AVG(g.receipt_observed_90d) receipt_share_90d,m.median_days
FROM groups g JOIN medians m USING(scenario) GROUP BY 1;

-- 10. Inspect actual time exclusions rather than silently correcting source dates.
SELECT rejection_reason,activity,COUNT(*) events,MIN(timestamp_raw) first_source_time,
 MAX(timestamp_raw) last_source_time FROM rejected_events GROUP BY 1,2 ORDER BY events DESC;

-- 11. Inventory and supplier identity are intentionally absent from financial claims:
-- these are record counts only, not spend in original euros (values are anonymized).
SELECT item_type,item_category,COUNT(*) cases FROM clean_cases GROUP BY 1,2 ORDER BY cases DESC;
