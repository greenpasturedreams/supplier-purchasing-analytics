"""Execute the SQL model, validate it and export compact review-ready outputs."""
from pathlib import Path
from datetime import datetime
import json
import sqlite3
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def statements(path):
    buffer=''
    for line in path.read_text(encoding='utf-8').splitlines(keepends=True):
        buffer+=line
        if sqlite3.complete_statement(buffer):
            yield buffer
            buffer=''


def validate(conn):
    def scalar(query):
        return conn.execute(query).fetchone()[0]
    checks={}
    def check(name,condition):
        checks[name]=bool(condition)
        if not condition:
            raise AssertionError(name)
    check('publisher_case_count',scalar('SELECT COUNT(*) FROM raw_cases')==251734)
    check('publisher_event_count',scalar('SELECT COUNT(*) FROM raw_events')==1595923)
    check('publisher_purchase_order_count',scalar('SELECT COUNT(DISTINCT po_id) FROM raw_cases')==76349)
    check('unique_case_ids',scalar('SELECT COUNT(*)-COUNT(DISTINCT case_id) FROM clean_cases')==0)
    check('case_quarantine_reconciliation',scalar('SELECT COUNT(*) FROM clean_cases')+scalar('SELECT COUNT(*) FROM rejected_cases')==251734)
    check('event_quarantine_reconciliation',scalar('SELECT COUNT(*) FROM clean_events')+scalar('SELECT COUNT(*) FROM rejected_events')==1595923)
    check('all_events_have_parent',scalar('SELECT COUNT(*) FROM clean_events e LEFT JOIN clean_cases c USING(case_id) WHERE c.case_id IS NULL')==0)
    check('one_case_milestone_row_per_case',scalar('SELECT COUNT(*) FROM case_milestones')==scalar('SELECT COUNT(*) FROM clean_cases'))
    check('cohort_partition_reconciles',scalar('SELECT COUNT(*) FROM cohort_audit')==scalar('SELECT COUNT(*) FROM clean_cases'))
    check('equal_90_day_followup',scalar('''SELECT COUNT(*) FROM analysis_cases c CROSS JOIN analysis_config cfg
      WHERE JULIANDAY(c.created_at)+90>JULIANDAY(cfg.as_of_utc)''')==0)
    check('receipt_times_between_0_and_90_days',scalar('SELECT COUNT(*) FROM analysis_cases WHERE first_receipt_days<0 OR first_receipt_days>90')==0)
    check('missing_receipt_is_null_not_zero',scalar('SELECT COUNT(*) FROM analysis_cases WHERE receipt_observed_90d=0 AND first_receipt_days IS NOT NULL')==0)
    check('receipt_posting_count_matches_indicator',scalar('SELECT COUNT(*) FROM analysis_cases WHERE (gr_records_90d>0)<>receipt_observed_90d')==0)
    check('receipt_span_nonnegative',scalar('SELECT COUNT(*) FROM analysis_cases WHERE receipt_span_days<0')==0)
    check('adjacent_intervals_nonnegative',scalar('SELECT COUNT(*) FROM transitions WHERE elapsed_days<0')==0)
    check('scorecard_case_denominators',scalar('SELECT SUM(eligible_cases) FROM supplier_scorecard')==scalar('SELECT COUNT(*) FROM analysis_cases'))
    check('scorecard_receipt_numerators',scalar('SELECT SUM(received_cases) FROM supplier_scorecard')==scalar('SELECT SUM(receipt_observed_90d) FROM analysis_cases'))
    check('percentiles_ordered',scalar('SELECT COUNT(*) FROM metric_stats WHERE p10_days>median_days OR median_days>p90_days')==0)
    check('export_dates_2018_jan_to_sep',scalar("SELECT COUNT(*) FROM analysis_cases WHERE created_at<'2018-01-01' OR created_at>='2018-10-01'")==0)
    observed=pd.read_sql_query('SELECT first_receipt_days FROM analysis_cases WHERE receipt_observed_90d=1',conn).first_receipt_days
    check('sql_median_equals_independent_pandas',abs(observed.median()-scalar("SELECT median_days FROM metric_stats WHERE scope='overall'"))<1e-9)
    sorted_days=observed.sort_values().reset_index(drop=True)
    import math
    check('sql_percentiles_equal_independent_order_statistics',all(
        abs(sorted_days.iloc[math.ceil(len(sorted_days)*p)-1]-scalar(f"SELECT {column} FROM metric_stats WHERE scope='overall'"))<1e-9
        for p,column in [(0.1,'p10_days'),(0.9,'p90_days')]))
    # Deterministic dispersed sample checked with independent Python datetime math,
    # against raw event times rather than the SQL milestone table.
    sample=conn.execute('SELECT case_id,created_at,first_receipt_days,gr_records_90d FROM analysis_cases ORDER BY source_trace').fetchall()[::200]
    for case_id,created,sql_days,sql_records in sample:
        start=datetime.fromisoformat(created.replace('Z','+00:00'))
        times=[datetime.fromisoformat(r[0].replace('Z','+00:00')) for r in conn.execute(
            "SELECT timestamp_utc FROM raw_events WHERE case_id=? AND activity='Record Goods Receipt'",(case_id,))]
        durations=[(ts-start).total_seconds()/86400 for ts in times]
        usable=[duration for duration in durations if 0<=duration<=90]
        assert len(usable)==sql_records
        assert (sql_days is None and not usable) or (usable and abs(min(usable)-sql_days)<1e-7)
    checks['independent_raw_event_sample']=True
    return checks,len(sample)


def main():
    out=ROOT/'data'/'processed'
    out.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(ROOT/'data'/'purchasing.db') as conn:
        conn.execute('PRAGMA temp_store=FILE')
        conn.executescript((ROOT/'sql'/'01_clean_transform.sql').read_text(encoding='utf-8'))
        checks,sample_count=validate(conn)
        for i,query in enumerate(statements(ROOT/'sql'/'02_analysis.sql'),1):
            result=pd.read_sql_query(query,conn)
            result.to_csv(out/f'analysis_{i:02}.csv',index=False)
        assert i==11
        for table in ['supplier_scorecard','supplier_context','metric_stats','analysis_config']:
            pd.read_sql_query(f'SELECT * FROM {table}',conn).to_csv(out/f'{table}.csv',index=False)
        columns='''case_id,po_id,item_id,company_id,vendor_id,item_type,item_category,
            spend_area,sub_spend_area,created_at,first_gr_90d,last_gr_90d,
            gr_records_90d,receipt_observed_90d,first_receipt_days,receipt_span_days,
            confirmation_days,receipt_to_invoice_days,invoice_to_clear_days,
            price_quantity_change_90d,payment_block_removal_90d,deletion_recorded,gr_cancellation_recorded'''
        cases=pd.read_sql_query(f'SELECT {columns} FROM analysis_cases ORDER BY case_id',conn)
        # All main-cohort cases included. Gzip keeps individual GitHub uploads small.
        cases.to_csv(out/'analysis_cases.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        cases.head(500).to_csv(out/'analysis_cases_preview.csv',index=False)
        pd.read_sql_query('SELECT * FROM rejected_events ORDER BY event_id',conn).to_csv(out/'rejected_events.csv',index=False)
        scalar=lambda q:conn.execute(q).fetchone()[0]
        report={
            'source_cases':scalar('SELECT COUNT(*) FROM raw_cases'),
            'source_events':scalar('SELECT COUNT(*) FROM raw_events'),
            'purchase_orders':scalar('SELECT COUNT(DISTINCT po_id) FROM raw_cases'),
            'rejected_cases':scalar('SELECT COUNT(*) FROM rejected_cases'),
            'rejected_events':scalar('SELECT COUNT(*) FROM rejected_events'),
            'retained_events':scalar('SELECT COUNT(*) FROM clean_events'),
            'eligible_cases':len(cases),'eligible_suppliers':int(cases.vendor_id.nunique()),
            'eligible_companies':int(cases.company_id.nunique()),
            'received_by_day_90':int(cases.receipt_observed_90d.sum()),
            'no_receipt_by_day_90':int((cases.receipt_observed_90d==0).sum()),
            'receipt_share_90d':float(cases.receipt_observed_90d.mean()),
            'multiple_receipt_cases':int((cases.gr_records_90d>1).sum()),
            'deletion_cases':int(cases.deletion_recorded.sum()),
            'receipt_cancellation_cases':int(cases.gr_cancellation_recorded.sum()),
            'qualified_suppliers':scalar('SELECT COUNT(*) FROM supplier_scorecard WHERE eligible_cases>=50 AND received_cases>=30'),
            'independent_sample_cases':sample_count,'checks':checks,'all_checks_passed':all(checks.values()),
        }
        (ROOT/'reports'/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
