"""Stream the verified XES file into source-preserving SQLite tables."""
from pathlib import Path
from datetime import datetime, timezone
import gzip
import json
import math
import sqlite3
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASE_MAP = {
    'concept:name':'case_id', 'Purchasing Document':'po_id', 'Item':'item_id',
    'Company':'company_id', 'Vendor':'vendor_id', 'Name':'vendor_name',
    'Source':'source_system', 'Item Type':'item_type', 'Item Category':'item_category',
    'Goods Receipt':'goods_receipt_required', 'GR-Based Inv. Verif.':'gr_based_iv',
    'Spend classification text':'spend_classification', 'Spend area text':'spend_area',
    'Sub spend area text':'sub_spend_area', 'Document Type':'document_type',
    'Purch. Doc. Category name':'document_category',
}


def attributes(element):
    return {child.get('key'):child.get('value') for child in element
            if child.tag.split('}')[-1] != 'event' and child.get('key') is not None}


def normalize_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    except ValueError:
        return None


def main():
    db = ROOT/'data'/'purchasing.db'
    source = ROOT/'data'/'raw'/'BPI_Challenge_2019.xes.gz'
    report = ROOT/'reports'
    report.mkdir(exist_ok=True)
    all_case_keys, all_event_keys = set(), set()
    cases, events = [], []
    trace_count, event_count = 0, 0
    with sqlite3.connect(db) as conn:
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.executescript('DROP TABLE IF EXISTS raw_cases; DROP TABLE IF EXISTS raw_events;')
        conn.execute('CREATE TABLE raw_cases (source_trace INTEGER,'+
                     ','.join(f'{c} TEXT' for c in CASE_MAP.values())+', attributes_json TEXT)')
        conn.execute('''CREATE TABLE raw_events (event_id INTEGER,case_id TEXT,event_index INTEGER,
            activity TEXT,timestamp_raw TEXT,timestamp_utc TEXT,resource TEXT,
            cumulative_value_raw TEXT,cumulative_value REAL,attributes_json TEXT)''')
        def flush():
            conn.executemany('INSERT INTO raw_cases VALUES ('+','.join('?' for _ in range(len(CASE_MAP)+2))+')',cases)
            conn.executemany('INSERT INTO raw_events VALUES (?,?,?,?,?,?,?,?,?,?)',events)
            conn.commit()
            cases.clear(); events.clear()
        with gzip.open(source,'rb') as handle:
            stream = ET.iterparse(handle,events=('start','end'))
            _,root = next(stream)
            for action,element in stream:
                if action!='end' or element.tag.split('}')[-1]!='trace':
                    continue
                trace_count += 1
                attrs = attributes(element)
                all_case_keys.update(attrs)
                case_id = attrs.get('concept:name')
                cases.append((trace_count,*(attrs.get(k) for k in CASE_MAP),json.dumps(attrs,sort_keys=True)))
                index = 0
                for child in element:
                    if child.tag.split('}')[-1]!='event':
                        continue
                    index += 1; event_count += 1
                    values = attributes(child)
                    all_event_keys.update(values)
                    ts_raw = values.get('time:timestamp')
                    value_raw = values.get('Cumulative net worth (EUR)')
                    value = None
                    if value_raw is not None:
                        try:
                            parsed = float(value_raw)
                            value = parsed if math.isfinite(parsed) else None
                        except ValueError:
                            pass
                    events.append((event_count,case_id,index,values.get('concept:name'),ts_raw,
                        normalize_timestamp(ts_raw),values.get('org:resource'),value_raw,value,
                        json.dumps(values,sort_keys=True)))
                element.clear()
                root.clear()
                if trace_count % 10000 == 0:
                    flush()
                    if trace_count % 50000 == 0:
                        print(f'Imported {trace_count:,} cases / {event_count:,} events',flush=True)
            flush()
        conn.execute('CREATE INDEX IF NOT EXISTS raw_events_case_idx ON raw_events(case_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS raw_cases_case_idx ON raw_cases(case_id)')
        conn.commit()
        profile = {
            'raw_cases':trace_count,'raw_events':event_count,
            'case_attribute_mapping':CASE_MAP,'case_attributes':sorted(all_case_keys),
            'event_attributes':sorted(all_event_keys),
            'timestamp_min':conn.execute('SELECT MIN(timestamp_utc) FROM raw_events').fetchone()[0],
            'timestamp_max':conn.execute('SELECT MAX(timestamp_utc) FROM raw_events').fetchone()[0],
            'invalid_timestamps':conn.execute('SELECT COUNT(*) FROM raw_events WHERE timestamp_utc IS NULL').fetchone()[0],
        }
        (report/'source_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
        print(f'Imported {trace_count:,} cases and {event_count:,} events. Saved reports/source_profile.json.')


if __name__=='__main__':
    main()
