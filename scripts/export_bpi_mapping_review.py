"""Build a review-only BPI extraction; does not train or alter the original data."""
from collections import Counter
from datetime import datetime
from itertools import groupby
from pathlib import Path
import argparse
import json
import sqlite3


def build(source_path, output_dir):
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/'bpi_mapping_review.sqlite3'
    if target.exists():
        raise FileExistsError('Use a new output directory; existing review is preserved.')
    raw=sqlite3.connect(Path(source_path).resolve().as_uri()+'?mode=ro',uri=True)
    raw.row_factory=sqlite3.Row
    out=sqlite3.connect(target)
    out.executescript('''
      CREATE TABLE review_meta(status TEXT, source_sha256 TEXT, rules_json TEXT);
      CREATE TABLE vendor_transactions(case_id TEXT PRIMARY KEY,document_id TEXT,vendor TEXT,
        company TEXT,spend_area TEXT,sub_spend_area TEXT,item_type TEXT,event_index INTEGER,
        created_at TEXT,observed_po_value REAL,interpretation TEXT);
      CREATE TABLE price_revision_events(case_id TEXT,event_index INTEGER,timestamp TEXT,
        previous_activity TEXT,observed_value_before REAL,observed_value_after REAL,
        observed_value_direction TEXT,quantity_change_also_recorded INTEGER,
        interpretation TEXT,PRIMARY KEY(case_id,event_index));
      CREATE TABLE payment_behavior(case_id TEXT PRIMARY KEY,vendor TEXT,invoice_event_index INTEGER,
        clear_event_index INTEGER,invoice_time TEXT,clear_time TEXT,elapsed_days REAL,
        proposed_behavior_class TEXT,interpretation TEXT);
      CREATE TABLE payment_term_change_events(case_id TEXT,event_index INTEGER,timestamp TEXT,
        vendor TEXT,observed_value REAL,interpretation TEXT,PRIMARY KEY(case_id,event_index));
      CREATE TABLE request_revision_cases(case_id TEXT PRIMARY KEY,quantity_change_events INTEGER,
        interpretation TEXT);
      CREATE TABLE review_case_labels(case_id TEXT PRIMARY KEY,document_id TEXT,has_clear_invoice INTEGER,
        price_revision_recorded INTEGER,quantity_revision_recorded INTEGER,
        payment_term_change_recorded INTEGER,interpretation TEXT);
    ''')
    counts=Counter()
    examples={'vendor':[],'price_revision':[],'payment_behavior':[],'payment_term_change':[]}
    attrs_by_case={r['case_id']:r for r in raw.execute('SELECT case_id,document_id,vendor,attributes_json FROM bpi_cases')}
    event_cursor=raw.execute('SELECT * FROM bpi_events ORDER BY case_id,event_index')
    with out:
        for case_id,items in groupby(event_cursor,key=lambda r:r['case_id']):
            events=list(items)
            case=attrs_by_case[case_id]
            attrs=json.loads(case['attributes_json'])
            activities=Counter(e['activity'] for e in events)
            counts['cases']+=1
            counts['events']+=len(events)
            creates=[e for e in events if e['activity']=='Create Purchase Order Item']
            if len(creates)==1:
                e=creates[0]
                out.execute('INSERT INTO vendor_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (case_id,case['document_id'],case['vendor'],attrs.get('Company'),attrs.get('Spend area text'),
                     attrs.get('Sub spend area text'),attrs.get('Item Type'),e['event_index'],e['timestamp'],e['value'],
                     'Observed PO transaction for chosen vendor; NOT a vendor bid or unit price'))
                counts['vendor_transactions']+=1
                if len(examples['vendor'])<4:
                    examples['vendor'].append({'case_id':case_id,'vendor':case['vendor'],
                        'category':attrs.get('Sub spend area text'),'observed_po_value':e['value']})
            quantity_count=activities['Change Quantity']
            if quantity_count:
                out.execute('INSERT INTO request_revision_cases VALUES(?,?,?)',(case_id,quantity_count,
                    'Quantity revision event observed; original/revised quantities and urgency allocation absent'))
                counts['quantity_revision_cases']+=1
            for i,e in enumerate(events):
                if e['activity']=='Change Price':
                    previous=events[i-1] if i else None
                    before=previous['value'] if previous else None
                    after=e['value']
                    direction='missing' if before is None or after is None else (
                        'unchanged' if abs(before-after)<1e-9 else ('decrease' if after<before else 'increase'))
                    out.execute('INSERT INTO price_revision_events VALUES(?,?,?,?,?,?,?,?,?)',
                        (case_id,e['event_index'],e['timestamp'],previous['activity'] if previous else None,
                         before,after,direction,int(quantity_count>0),
                         'Recorded price-change activity; observed cumulative value delta is NOT a counteroffer price'))
                    counts['price_revision_events']+=1
                    counts['price_value_'+direction]+=1
                    if len(examples['price_revision'])<4:
                        examples['price_revision'].append({'case_id':case_id,'event_index':e['event_index'],
                          'before':before,'after':after,'direction':direction})
                if e['activity']=='Change payment term':
                    out.execute('INSERT INTO payment_term_change_events VALUES(?,?,?,?,?,?)',
                        (case_id,e['event_index'],e['timestamp'],case['vendor'],e['value'],
                         'Actual term-change event; old/new contractual terms are NOT present'))
                    counts['payment_term_change_events']+=1
                    examples['payment_term_change'].append({'case_id':case_id,'event_index':e['event_index'],
                        'timestamp':e['timestamp'],'vendor':case['vendor']})
            invoices=[e for e in events if e['activity']=='Record Invoice Receipt']
            clears=[e for e in events if e['activity']=='Clear Invoice']
            if invoices and not clears:
                counts['invoice_without_clear_observed']+=1
            if len(invoices)>1 or len(clears)>1:
                counts['complex_invoice_cases_excluded']+=1
            corrections=any(activities[a] for a in ('Cancel Invoice Receipt','Cancel Subsequent Invoice',
                'Vendor creates debit memo','Record Subsequent Invoice','Change Currency'))
            if len(invoices)==len(clears)==1 and not corrections:
                invoice,clear=invoices[0],clears[0]
                days=(datetime.fromisoformat(clear['timestamp'])-datetime.fromisoformat(invoice['timestamp'])).total_seconds()/86400
                if days<0 or clear['event_index']<=invoice['event_index']:
                    counts['payment_invalid_order_excluded']+=1
                else:
                    # Exact elapsed time: 7.1 days belongs to (7,30].
                    label='within_7_days' if days<=7 else ('over_7_to_30_days' if days<=30 else 'over_30_days')
                    out.execute('INSERT INTO payment_behavior VALUES(?,?,?,?,?,?,?,?,?)',
                        (case_id,case['vendor'],invoice['event_index'],clear['event_index'],invoice['timestamp'],
                         clear['timestamp'],days,label,
                         'Derived elapsed-time bucket; NOT agreed due date, early-payment discount or instalment schedule'))
                    counts['payment_behavior_cases']+=1
                    counts['payment_'+label]+=1
                    if len(examples['payment_behavior'])<6:
                        examples['payment_behavior'].append({'case_id':case_id,'elapsed_days':round(days,2),
                          'proposed_label':label})
            out.execute('INSERT INTO review_case_labels VALUES(?,?,?,?,?,?,?)',
                (case_id,case['document_id'],int(bool(clears)),int(activities['Change Price']>0),
                 int(quantity_count>0),int(activities['Change payment term']>0),
                 'Full-trace outcomes for label review only; absent event does NOT imply rejected offer or optimal acceptance'))
            if counts['cases']%50000==0:
                print('Reviewed',counts['cases'],'cases',flush=True)
        vendor_count=out.execute('SELECT COUNT(DISTINCT vendor) FROM vendor_transactions').fetchone()[0]
        groups=out.execute('''SELECT COUNT(*) FROM (SELECT company,spend_area,sub_spend_area,item_type
           FROM vendor_transactions GROUP BY company,spend_area,sub_spend_area,item_type HAVING COUNT(DISTINCT vendor)>=2)''').fetchone()[0]
        rules={'status':'PENDING_USER_APPROVAL','payment_days_thresholds_proposed':[7,30],
          'payment_cohort':'exactly one invoice receipt + one clear, no cancellations/debit/subsequent/currency change, valid time order',
          'vendor':'chosen vendor and PO item value are transaction proxies; not tender offers',
          'price':'Change Price occurrence is observed; price counteroffers and acceptance absent',
          'training':'No new model trained; these are draft proxy labels, not the old simulator action ground truth'}
        meta=dict(raw.execute('SELECT * FROM bpi_dataset WHERE id=1').fetchone())
        out.execute('INSERT INTO review_meta VALUES(?,?,?)',('PENDING_USER_APPROVAL',meta['sha256'],json.dumps(rules)))
    result={'status':'PENDING_USER_APPROVAL','source':meta,'counts':dict(counts),
      'unique_vendors':vendor_count,'broad_category_groups_with_multiple_historical_vendors':groups,
      'rules':rules,'examples':examples}
    (output_dir/'BPI_MAPPING_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    out.close();raw.close()
    print(json.dumps({k:v for k,v in result.items() if k not in ('examples','source')},indent=2),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    build(args.source,args.out)
