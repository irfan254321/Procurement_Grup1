"""Persistent step-by-step CatBoost offer workflow; no simulated event is a real payment."""
from datetime import datetime
import hashlib,json,sqlite3
from pathlib import Path
import pandas as pd
from .bpi import ROOT
from .bpi_offers import MODEL_DIR,CATS,advise

COMPANY_ID='companyID_0000'
COMPANY_NAME='PT. Biz Indonesia Market'
DB_PATH=ROOT/'data'/'bpi_offer_audit.sqlite3'
CONTEXT=['spend_area','sub_spend_area','item_type','document_type']


def connect(path=DB_PATH):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS offer_workflow_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        company_id TEXT NOT NULL,company_name TEXT NOT NULL,request_json TEXT NOT NULL,
        results_json TEXT NOT NULL,model_json TEXT NOT NULL,status TEXT NOT NULL,
        review_decision TEXT NOT NULL DEFAULT 'MENUNGGU KEPUTUSAN');
      CREATE TABLE IF NOT EXISTS offer_workflow_events(
        run_id INTEGER REFERENCES offer_workflow_runs(id),step INTEGER,
        agent TEXT NOT NULL,vendor TEXT,explanation TEXT,payload_json TEXT NOT NULL,
        PRIMARY KEY(run_id,step));
      CREATE TABLE IF NOT EXISTS offer_workflow_settings(
        context_key TEXT PRIMARY KEY,settings_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS offer_workflow_reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER REFERENCES offer_workflow_runs(id),
        decision TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    return db


def catalog(model_dir=MODEL_DIR):
    rows=pd.read_json(Path(model_dir)/'catalog.json')
    rows=rows[rows.company==COMPANY_ID].copy()
    for col in CONTEXT:
        rows=rows[~rows[col].isin(['','__MISSING__'])]
    rows['context_key']=rows[CONTEXT].astype(str).agg(' | '.join,axis=1)
    counts=rows.groupby('context_key').vendor.nunique()
    return rows[rows.context_key.isin(counts[counts>=5].index)].copy()


def names(model_dir=MODEL_DIR):
    path=Path(model_dir)/'vendor_aliases.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def vendor_label(vendor,labels):
    from .vendor_display import vendor_name
    return labels.get(vendor,vendor_name(vendor))


def candidates(frame,context_key,settings=None):
    rows=frame[frame.context_key==context_key].sort_values(['historical_items','vendor'],ascending=[False,True])
    if settings:
        selected=settings.get('vendors',[])
        rows=rows[rows.vendor.isin(selected)].copy()
        values=settings.get('values',{})
        rows['initial_po_value']=[values.get(v,p) for v,p in zip(rows.vendor,rows.initial_po_value)]
    else:rows=rows.head(5).copy()
    if rows.vendor.nunique()<5:raise ValueError('Permintaan memerlukan minimal lima vendor berbeda dari kategori yang sama.')
    return rows


def save_settings(db,context_key,vendors,values,available):
    if len(set(vendors))<5:raise ValueError('Pilih minimal lima vendor berbeda.')
    if not set(vendors)<=set(available):raise ValueError('Vendor bukan anggota kategori permintaan ini.')
    if any(float(values[v])<=0 for v in vendors):raise ValueError('Nilai penawaran harus positif.')
    with db:
        db.execute('INSERT INTO offer_workflow_settings VALUES(?,?) ON CONFLICT(context_key) DO UPDATE SET settings_json=excluded.settings_json',
          (context_key,json.dumps({'vendors':vendors,'values':values})))


def load_settings(db,context_key):
    r=db.execute('SELECT settings_json FROM offer_workflow_settings WHERE context_key=?',(context_key,)).fetchone()
    return json.loads(r[0]) if r else None


def make_events(request,results,labels):
    events=[]
    def add(agent,text,vendor=None,payload=None):
        events.append({'step':len(events)+1,'agent':agent,'vendor':vendor,'explanation':text,'data':payload or {}})
    add('IRE',f"{COMPANY_NAME} meminta {request['request_name']}. Memeriksa {len(results)} penawaran terhadap batas nilai {request['budget']:,.2f}.",
        payload={'request_name':request['request_name'],'budget':request['budget']})
    # The source vendor order is retained; model ranking is revealed at joint review.
    by_vendor={r['vendor']:r for r in results}
    ordered=[by_vendor[v] for v in request['vendor_order']]
    for r in ordered:
        state='dalam batas nilai' if r['within_budget'] else 'melebihi batas nilai'
        add('VMI',f"Memeriksa {vendor_label(r['vendor'],labels)}: nilai {r['nilai_penawaran']:,.2f}, {state}; skor model {r['purchase_score']:.3f}.",r['vendor'],r)
    for r in ordered:
        add('DA',f"{vendor_label(r['vendor'],labels)}: {r['price_action']}. Skor revisi {r['price_revision_score']:.3f}.",r['vendor'],r)
    for r in ordered:
        add('SLM',f"{vendor_label(r['vendor'],labels)}: perkiraan kelompok pembayaran {r['payment_window']} setelah penerimaan invoice.",r['vendor'],r)
    viable=[r for r in results if r['within_budget']]
    selected=viable[0] if viable else None
    text=(f"Evaluasi bersama selesai. Kandidat: {vendor_label(selected['vendor'],labels)}. {selected['purchase_action']}."
          if selected else 'Evaluasi selesai: seluruh penawaran melampaui batas nilai. Permintaan perlu direvisi.')
    add('ENV',text,payload={'selected':selected})
    return events,selected


def create_run(db,rows,request,model_dir=MODEL_DIR):
    if len(rows)<5 or rows.vendor.nunique()<5:raise ValueError('Minimal lima vendor berbeda diperlukan.')
    if set(rows.company)!={COMPANY_ID}:raise ValueError('Perusahaan sumber tidak sesuai.')
    if any(rows[c].nunique()!=1 for c in CONTEXT):raise ValueError('Vendor harus berada pada konteks yang sama.')
    if request['budget']<=0:raise ValueError('Batas nilai harus positif.')
    features=rows[CATS+['initial_po_value']].copy()
    date=datetime.fromisoformat(request['date']);features['month']=date.month;features['weekday']=date.weekday()
    results=advise(features,model_dir=model_dir)
    for r in results:r['within_budget']=r['nilai_penawaran']<=request['budget']
    request={**request,'company_id':COMPANY_ID,'company_name':COMPANY_NAME,'vendor_order':list(rows.vendor)}
    labels=names(model_dir);events,selected=make_events(request,results,labels)
    status='PERLU REVISI' if not selected else ('SARAN LANJUT' if selected['purchase_action'].startswith('LANJUTKAN') else 'PERLU TINJAU')
    request['vendor_labels']={v:labels.get(v,v) for v in rows.vendor}
    model_path=Path(model_dir)/'metrics.json'
    model={'metadata_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
           'training_version':json.loads(model_path.read_text(encoding='utf-8')).get('training_version',1)}
    with db:
        cur=db.execute('INSERT INTO offer_workflow_runs(company_id,company_name,request_json,results_json,model_json,status) VALUES(?,?,?,?,?,?)',
            (COMPANY_ID,COMPANY_NAME,json.dumps(request),json.dumps({'rows':results,'selected':selected}),json.dumps(model),status))
        run_id=cur.lastrowid
        db.executemany('INSERT INTO offer_workflow_events VALUES(?,?,?,?,?,?)',
          [(run_id,e['step'],e['agent'],e['vendor'],e['explanation'],json.dumps(e['data'])) for e in events])
    return run_id


def runs(db):
    return [dict(r) for r in db.execute('SELECT id,created_at,status,review_decision FROM offer_workflow_runs WHERE company_id=? ORDER BY id DESC',(COMPANY_ID,))]


def load_run(db,run_id):
    row=db.execute('SELECT * FROM offer_workflow_runs WHERE id=? AND company_id=?',(run_id,COMPANY_ID)).fetchone()
    if not row:raise ValueError('Riwayat simulasi tidak ditemukan.')
    r=dict(row)
    for name in ['request','results','model']:r[name]=json.loads(r.pop(name+'_json'))
    r['events']=[{'step':e['step'],'agent':e['agent'],'vendor':e['vendor'],'explanation':e['explanation'],
                  'data':json.loads(e['payload_json'])} for e in db.execute('SELECT * FROM offer_workflow_events WHERE run_id=? ORDER BY step',(run_id,))]
    from .vendor_display import display_text
    r['request']['vendor_labels']={v:vendor_label(v,names()) for v in r['request']['vendor_order']}
    for event in r['events']:event['explanation']=display_text(event['explanation'])
    return r


def review(db,run_id,decision):
    if decision not in ['DISETUJUI','DITOLAK']:raise ValueError('Keputusan tidak dikenal.')
    r=load_run(db,run_id)
    if decision=='DISETUJUI' and not r['results']['selected']:raise ValueError('Tidak ada kandidat dalam batas nilai.')
    with db:
        db.execute('UPDATE offer_workflow_runs SET review_decision=? WHERE id=?',(decision,run_id))
        db.execute('INSERT INTO offer_workflow_reviews(run_id,decision) VALUES(?,?)',(run_id,decision))


def visible_vendor_rows(run,step):
    labels=run['request']['vendor_labels'];results={r['vendor']:r for r in run['results']['rows']}
    states={v:{'Vendor':vendor_label(v,labels),'Nilai penawaran':results[v]['nilai_penawaran'],
                'Skor model':'—','Status':'Belum diperiksa','Tinjauan harga':'—','Pembayaran':'—'} for v in run['request']['vendor_order']}
    for e in run['events'][:step]:
        if e['vendor'] not in states:continue
        row=states[e['vendor']];r=e['data']
        if e['agent']=='VMI':
            row.update({'Skor model':f"{r['purchase_score']:.3f}",'Status':'Lolos batas nilai' if r['within_budget'] else 'Di atas batas nilai'})
        elif e['agent']=='DA':row.update({'Tinjauan harga':r['price_action'],'Status':'Harga ditinjau'})
        elif e['agent']=='SLM':row.update({'Pembayaran':r['payment_window'],'Status':'Pembayaran ditinjau'})
    if step>=len(run['events']):
        selected=run['results']['selected']
        if selected:states[selected['vendor']]['Status']='Kandidat terpilih'
    return list(states.values())
