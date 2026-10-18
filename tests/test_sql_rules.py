"""Small in-memory fixtures verify consequential SQL edge cases, not source findings."""
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from import_xes import CASE_MAP


class SQLRules(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('CREATE TABLE raw_cases (source_trace INTEGER,'+
            ','.join(f'{v} TEXT' for v in CASE_MAP.values())+',attributes_json TEXT)')
        self.conn.execute('''CREATE TABLE raw_events (event_id INTEGER,case_id TEXT,event_index INTEGER,
            activity TEXT,timestamp_raw TEXT,timestamp_utc TEXT,resource TEXT,cumulative_value_raw TEXT,
            cumulative_value REAL,attributes_json TEXT)''')
        self.event_id=0
        for i,case in enumerate(['boundary','repeated','missing','prior','service','late','deleted','missingcreate','doublecreate'],1):
            attrs={v:'x' for v in CASE_MAP.values()}
            attrs.update(case_id=case,po_id=f'po{i}',item_id='1',company_id='company',vendor_id='vendor',
                item_type='Service' if case=='service' else 'Standard',
                item_category='3-way match, invoice before GR',goods_receipt_required='true',
                gr_based_iv='false',spend_area='Packaging',sub_spend_area='Labels')
            self.conn.execute('INSERT INTO raw_cases VALUES ('+','.join('?' for _ in range(len(CASE_MAP)+2))+')',
                (i,*[attrs[v] for v in CASE_MAP.values()],'{}'))
            if case!='missingcreate':
                self.event(case,'Create Purchase Order Item','2018-01-01T00:00:00.000Z')
            if case=='doublecreate':
                self.event(case,'Create Purchase Order Item','2018-01-02T00:00:00.000Z')
        self.event('boundary','Record Goods Receipt','2018-04-01T00:00:00.000Z')
        self.event('boundary','Record Goods Receipt','2018-04-01T00:00:00.001Z')
        self.event('repeated','Record Goods Receipt','2018-01-01T00:00:00.000Z')
        self.event('repeated','Record Goods Receipt','2018-01-01T00:00:00.000Z')
        self.event('prior','Record Goods Receipt','2017-12-31T00:00:00.000Z')
        self.event('late','Record Goods Receipt','2018-04-02T00:00:00.000Z')
        self.event('deleted','Delete Purchase Order Item','2018-01-02T00:00:00.000Z')
        self.event('missing','Vendor creates invoice','2020-01-01T00:00:00.000Z')
        self.conn.executescript((ROOT/'sql'/'01_clean_transform.sql').read_text())

    def event(self,case,activity,stamp):
        self.event_id+=1
        self.conn.execute('INSERT INTO raw_events VALUES (?,?,?,?,?,?,?,?,?,?)',
            (self.event_id,case,self.event_id,activity,stamp,stamp,'NONE','0',0,'{}'))

    def case(self,name):
        return self.conn.execute('SELECT * FROM cohort_audit WHERE case_id=?',(name,)).fetchone()

    def tearDown(self):
        self.conn.close()

    def test_day_90_is_inclusive_and_next_millisecond_excluded(self):
        c=self.case('boundary')
        self.assertEqual(c['first_receipt_days'],90)
        self.assertEqual(c['gr_records_90d'],1)

    def test_identical_records_preserved_and_zero_duration_valid(self):
        c=self.case('repeated')
        self.assertEqual(c['gr_records_90d'],2)
        self.assertEqual(c['first_receipt_days'],0)

    def test_missing_and_late_receipts_are_not_zero(self):
        for name in ['missing','late']:
            self.assertEqual(self.case(name)['receipt_observed_90d'],0)
            self.assertIsNone(self.case(name)['first_receipt_days'])

    def test_prior_receipts_and_services_excluded(self):
        self.assertEqual(self.case('prior')['cohort_status'],'receipt_before_creation')
        self.assertEqual(self.case('service')['cohort_status'],'nonstandard_item')
        self.assertEqual(self.case('missingcreate')['cohort_status'],'missing_creation')
        self.assertEqual(self.case('doublecreate')['cohort_status'],'multiple_creation_records')

    def test_deletions_retained_for_coverage_not_hidden(self):
        self.assertEqual(self.case('deleted')['cohort_status'],'Included')
        self.assertEqual(self.case('deleted')['deletion_recorded'],1)

    def test_date_quarantine_and_missing_resource(self):
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM rejected_events').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM clean_events WHERE resource IS NOT NULL').fetchone()[0],0)

    def test_even_median_and_nearest_rank_p90(self):
        stats=self.conn.execute("SELECT * FROM metric_stats WHERE scope='overall'").fetchone()
        self.assertEqual(stats['observations'],2)
        self.assertEqual(stats['median_days'],45)
        self.assertEqual(stats['p90_days'],90)


if __name__=='__main__':
    unittest.main()
