"""Read-only raw source audit; useful before choosing analytical cohorts."""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def main():
    queries = {
        'creation_years':"SELECT SUBSTR(timestamp_utc,1,4) year,COUNT(*) rows FROM raw_events WHERE activity='Create Purchase Order Item' GROUP BY 1",
        'event_years':"SELECT SUBSTR(timestamp_utc,1,4) year,COUNT(*) rows FROM raw_events GROUP BY 1",
        'spend_classification':"SELECT spend_classification,COUNT(*) rows FROM raw_cases GROUP BY 1",
        'standard_item_spend_areas':"SELECT spend_area,COUNT(*) rows FROM raw_cases WHERE item_type='Standard' GROUP BY 1 ORDER BY 2 DESC",
        'outside_analysis_window':"SELECT activity,COUNT(*) rows FROM raw_events WHERE timestamp_utc<'2017-01-01' OR timestamp_utc>='2019-02-01' GROUP BY 1 ORDER BY 2 DESC",
        'activities':"SELECT activity,COUNT(*) rows FROM raw_events GROUP BY 1 ORDER BY 2 DESC",
        'identical_event_content':'''SELECT COUNT(*) duplicate_groups,SUM(n-1) additional_rows FROM
            (SELECT COUNT(*) n FROM raw_events GROUP BY case_id,activity,timestamp_raw,resource,cumulative_value_raw HAVING COUNT(*)>1)''',
    }
    with sqlite3.connect(ROOT/'data'/'purchasing.db') as conn:
        conn.row_factory=sqlite3.Row
        audit={name:[dict(row) for row in conn.execute(query)] for name,query in queries.items()}
    (ROOT/'reports'/'raw_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print('Saved raw audit: event years, activity counts, material categories and identical-content groups.')


if __name__=='__main__':
    main()
