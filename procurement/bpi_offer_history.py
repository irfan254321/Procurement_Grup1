"""Historical cleared-invoice evidence, displayed separately from simulated offers."""
from pathlib import Path
from datetime import datetime
import json
import sqlite3
import pandas as pd
from .bpi_offers import opening_features


def export_history(source,out,limit_per_company=200):
    db=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    query='''WITH s AS (SELECT case_id,
      SUM(activity='Clear Invoice') AS clear_count,
      SUM(activity='Record Invoice Receipt') AS invoice_count,
      SUM(activity='Delete Purchase Order Item') AS deleted,
      SUM(activity IN ('Cancel Invoice Receipt','Cancel Subsequent Invoice','Vendor creates debit memo',
                       'Record Subsequent Invoice','Change Currency')) AS corrections,
      SUM(activity='Change Price') AS price_changes,
      SUM(activity='Record Goods Receipt') AS goods_receipts,
      MAX(CASE WHEN activity='Clear Invoice' THEN timestamp END) AS clear_time,
      MAX(CASE WHEN activity='Record Invoice Receipt' THEN timestamp END) AS invoice_time,
      MAX(CASE WHEN activity='Clear Invoice' THEN event_index END) AS clear_idx,
      MAX(CASE WHEN activity='Record Invoice Receipt' THEN event_index END) AS invoice_idx
      FROM bpi_events GROUP BY case_id)
      SELECT c.case_id,c.document_id,c.attributes_json,e.value,e.timestamp,s.*
      FROM s JOIN bpi_cases c ON c.case_id=s.case_id JOIN bpi_events e ON e.case_id=c.case_id
      WHERE e.activity='Create Purchase Order Item' AND s.clear_count=1 AND s.invoice_count=1
      AND s.deleted=0 AND s.corrections=0 AND s.clear_idx>s.invoice_idx
      AND s.clear_time>=s.invoice_time ORDER BY s.clear_time DESC,c.case_id'''
    rows=[]; totals={};retained={}
    for r in db.execute(query):
        attrs=json.loads(r['attributes_json']); features=opening_features(attrs,r)
        if features is None: continue
        company=features['company'];totals[company]=totals.get(company,0)+1
        if retained.get(company,0)>=limit_per_company: continue
        days=(datetime.fromisoformat(r['clear_time'])-datetime.fromisoformat(r['invoice_time'])).total_seconds()/86400
        rows.append({'case_id':r['case_id'],'document_id':r['document_id'],**features,
          'created_at':r['timestamp'],'invoice_at':r['invoice_time'],'cleared_at':r['clear_time'],
          'actual_payment_days':days,'actual_payment_class':0 if days<=7 else (1 if days<=30 else 2),
          'price_changes_observed':r['price_changes'],'goods_receipts_observed':r['goods_receipts'],
          'actual_status':'Pelunasan satu invoice tercatat, tanpa penghapusan/koreksi'})
        retained[company]=retained.get(company,0)+1
    result={'source':'BPI 2019, cleared-invoice evidence','cohort_counts':totals,
      'selection':'Latest up to 200 cases per company, one invoice/clearing, no deletion or invoice correction.',
      'limitation':'Historical outcomes do not establish that a newly simulated offer has completed.',
      'cases':rows}
    db.close();Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Historical completed-invoice cohort:',totals,'displayed:',len(rows),flush=True)
    return result


def historical_rows(snapshot,company,vendor=None):
    return [r for r in snapshot['cases'] if r['company']==company and (vendor is None or r['vendor']==vendor)]


def render_completed_panel(model_dir,company):
    import streamlit as st
    from .bpi_offers import advise
    path=Path(model_dir)/'completed_transactions.json'
    if not path.exists():
        st.info('Cuplikan hasil transaksi historis belum tersedia.');return
    snapshot=json.loads(path.read_text(encoding='utf-8'))
    with st.expander('Hasil transaksi perusahaan yang sudah dibayar',expanded=False):
        counts=snapshot['cohort_counts']
        selected_company=st.selectbox('Perusahaan pada hasil historis',list(counts),
          index=list(counts).index(company) if company in counts else 0,key='completed_company')
        rows=historical_rows(snapshot,selected_company)
        st.metric('Kasus invoice dilunasi yang lolos filter',f"{counts[selected_company]:,}")
        st.caption('Tabel menampilkan cuplikan maksimal 200 kasus terbaru per perusahaan. '
          'Setiap kasus memiliki satu invoice dan satu pelunasan, tanpa penghapusan atau koreksi invoice. '
          'Ini hasil BPI yang teramati; simulasi penawaran baru belum menjadi transaksi nyata.')
        st.dataframe([{'Kasus':r['case_id'],'Vendor':r['vendor'],'Kategori':r['sub_spend_area'],
          'Nilai PO anonim':r['initial_po_value'],'Tanggal invoice':r['invoice_at'],
          'Tanggal pelunasan':r['cleared_at'],'Jeda pembayaran (hari)':round(r['actual_payment_days'],2),
          'Revisi harga tercatat':r['price_changes_observed'],'Hasil aktual':r['actual_status']}
          for r in rows],hide_index=True,width='stretch')
        if not rows:return
        ids={r['case_id']:r for r in rows}
        case=st.selectbox('Lihat hasil satu transaksi',list(ids),key='completed_case')
        r=ids[case]
        st.write('**Hasil aktual:**',r['actual_status'])
        st.write('**Pembayaran aktual:**',f"{r['actual_payment_days']:.2f} hari setelah penerimaan invoice")
        if st.button('Bandingkan model dengan hasil transaksi ini',key='completed_predict'):
            prediction=advise(pd.DataFrame([r]),model_dir=model_dir)[0]
            st.write('**Saran model pada kondisi awal PO:**',prediction['purchase_action'])
            st.write('**Kelompok pembayaran model:**',prediction['payment_window'])
            st.write('**Kelompok aktual:**',{0:'0–7 hari',1:'>7–30 hari',2:'>30 hari'}[r['actual_payment_class']])
            st.caption('Fitur prediksi hanya konteks dan nilai saat PO dibuat. '
              'Tanggal invoice/pelunasan dan hasil akhir tidak masuk ke fitur. '
              'Contoh historis ini tidak dihitung sebagai pengujian baru yang independen.')
        st.download_button('Unduh hasil transaksi aktual',pd.DataFrame(rows).to_csv(index=False),
          file_name='hasil_transaksi_bpi.csv',mime='text/csv',key='completed_download')
