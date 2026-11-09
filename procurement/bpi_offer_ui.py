"""MARL-style, persistent CatBoost simulation for one company."""
from datetime import date
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from .bpi_offers import MODEL_DIR
from . import offer_workflow as flow
from .simulation_examples import CATBOOST_EXAMPLES

TITLES={'Office Supplies':'Perlengkapan kantor','ICT Hardware':'Perangkat IT',
        'Facility Management':'Pengelolaan fasilitas','Products for Resale':'Barang untuk dijual kembali',
        'Packaging - Other':'Kemasan lainnya'}


def request_label(key):
    area,sub,item,document=key.split(' | ')
    return f"{TITLES.get(sub,sub)} · {item} · {area} · {document}"


def _start(db,rows,context,budget,proposal_date,demo=False):
    return flow.create_run(db,rows,{'context_key':context,'request_name':request_label(context),
       'budget':float(budget),'date':str(proposal_date),'is_demo':demo})


def _process(run):
    events=run['events'];key=f"workflow_step_{run['id']}"
    st.session_state.setdefault(key,1)
    st.session_state[key]=min(st.session_state[key],len(events))
    current_step=st.session_state[key]
    left,right,rest=st.columns([1,1,6])
    def move(delta):st.session_state[key]+=delta
    left.button('◀ Mundur',disabled=current_step==1,key='workflow_back',on_click=move,args=(-1,))
    right.button('Maju ▶',disabled=current_step==len(events),key='workflow_next',on_click=move,args=(1,))
    step=st.slider('Langkah agen',1,len(events),key=key)
    event=events[step-1]
    st.subheader(f"Langkah {step} · Siklus 1 · {event['agent'] if event['agent']!='ENV' else 'Evaluasi bersama'}")
    columns=st.columns(4)
    for agent,col in zip(['IRE','VMI','DA','SLM'],columns):
        past=[e for e in events[:step] if e['agent']==agent]
        with col.container(border=True):
            st.markdown('**'+agent+'**')
            if event['agent']==agent:
                st.caption('Keputusan pada langkah ini');st.info(event['explanation'])
            elif past:
                st.caption('Keputusan terakhir');st.write(past[-1]['explanation'])
            else:st.caption('Menunggu giliran')
    if event['agent']=='ENV':st.info(event['explanation'])
    st.markdown('**Penawaran vendor · permintaan ini**')
    st.dataframe(flow.visible_vendor_rows(run,step),hide_index=True,width='stretch')
    st.progress(step/len(events),text=f'{step} dari {len(events)} langkah')
    st.caption('Nominal revisi harga tidak dibuat-buat: DA memberi saran tinjauan dari model BPI. '
               'Pembayaran yang ditampilkan adalah kelompok waktu hasil prediksi.')


def _actual_transactions(labels):
    path=Path(MODEL_DIR)/'completed_transactions.json'
    if not path.exists():return
    snapshot=json.loads(path.read_text(encoding='utf-8'))
    rows=[r for r in snapshot['cases'] if r['company']==flow.COMPANY_ID]
    st.subheader('Hasil transaksi yang sudah dibayar · sumber BPI')
    st.caption(f"{snapshot['cohort_counts'].get(flow.COMPANY_ID,0):,} kasus memenuhi filter pelunasan. "
       f'Tabel berisi {len(rows)} kasus terbaru dari perusahaan sumber yang dipakai PT. Biz Indonesia Market. '
       'Riwayat ini adalah bukti historis, terpisah dari simulasi baru.')
    display=[{'Kasus':r['case_id'],'Vendor':flow.vendor_label(r['vendor'],labels),
       'Permintaan':TITLES.get(r['sub_spend_area'],r['sub_spend_area']),
       'Nilai PO anonim':r['initial_po_value'],'Tanggal invoice':r['invoice_at'],
       'Tanggal pelunasan':r['cleared_at'],'Jeda pembayaran (hari)':round(r['actual_payment_days'],2),
       'Hasil':'Pelunasan invoice tercatat'} for r in rows]
    st.dataframe(display,hide_index=True,width='stretch',height=320)
    st.download_button('Unduh transaksi aktual',pd.DataFrame(display).to_csv(index=False),
        file_name='transaksi_bpi_biz_indonesia_market.csv',mime='text/csv',key='workflow_actual_download')


def _report(db,run,labels,metadata):
    result=run['results'];selected=result['selected']
    st.subheader('Hasil akhir simulasi')
    st.write('**Perusahaan:**',flow.COMPANY_NAME)
    st.write('**Permintaan:**',run['request']['request_name'])
    st.write('**Status analisis:**',run['status'])
    st.write('**Keputusan pembelian:**',run['review_decision'])
    if selected:
        st.write('**Kandidat terpilih:**',flow.vendor_label(selected['vendor'],labels))
        st.write('**Nilai penawaran:**',f"{selected['nilai_penawaran']:,.2f}")
        st.write('**Tinjauan harga:**',selected['price_action'])
        st.write('**Perkiraan waktu pembayaran:**',selected['payment_window'])
    else:st.warning('Belum ada kandidat dalam batas nilai. Revisi anggaran atau penawaran.')
    yes,no=st.columns(2)
    if yes.button('Setujui penawaran · simulasi',disabled=selected is None,key='workflow_approve'):
        flow.review(db,run['id'],'DISETUJUI');st.rerun()
    if no.button('Tolak penawaran · simulasi',key='workflow_reject'):
        flow.review(db,run['id'],'DITOLAK');st.rerun()
    st.caption('Persetujuan dicatat untuk simulasi; tidak mengirim pesanan atau pembayaran nyata.')
    st.subheader('Riwayat transaksi simulasi')
    history=[]
    for item in flow.runs(db):
        r=flow.load_run(db,item['id']);s=r['results']['selected']
        history.append({'ID':r['id'],'Tanggal':r['created_at'],'Perusahaan':flow.COMPANY_NAME,
          'Permintaan':r['request']['request_name'],'Anggaran':r['request']['budget'],
          'Vendor':flow.vendor_label(s['vendor'],labels) if s else '—',
          'Nilai penawaran':s['nilai_penawaran'] if s else None,
          'Hasil analisis':r['status'],'Keputusan pembelian':r['review_decision']})
    st.dataframe(history,hide_index=True,width='stretch')
    st.download_button('Unduh transaksi simulasi',pd.DataFrame(history).to_csv(index=False),
      file_name='transaksi_simulasi_biz_indonesia_market.csv',mime='text/csv',key='workflow_sim_download')
    st.download_button('Unduh alur transaksi terpilih',json.dumps(run,ensure_ascii=False,indent=2),
      file_name=f"alur_catboost_{run['id']}.json",mime='application/json',key='workflow_trace_download')
    _actual_transactions(labels)
    with st.expander('Hasil pelatihan CatBoost'):
        st.dataframe([{'Model':m['label_description'],'Accuracy':m['accuracy'],'Macro-F1':m['macro_f1'],
          'Baseline accuracy':m['baseline_accuracy']} for m in metadata['models'].values()],hide_index=True)
        st.caption('ID sumber tetap dipakai model. PT. Biz Indonesia Market adalah nama tampilan perusahaan simulasi. '
          'Nama PT vendor adalah alias fiktif; ID dataset tetap dipakai model. Skor model bukan persentase persetujuan tawaran asli.')
        for m in metadata['models'].values():
            if m.get('temporal_test_warning'):st.warning(m['label_description']+': performa menurun pada periode uji dibanding validasi.')


def _settings(db,all_catalog,context,labels):
    st.subheader('Konfigurasi vendor · '+TITLES.get(context.split(' | ')[1],context.split(' | ')[1]))
    pool=all_catalog[all_catalog.context_key==context].sort_values(['historical_items','vendor'],ascending=[False,True])
    current=flow.load_settings(db,context)
    default=current['vendors'] if current else list(pool.head(5).vendor)
    selected=st.multiselect('Vendor untuk permintaan ini · minimal 5',list(pool.vendor),default=default,
      format_func=lambda v:flow.vendor_label(v,labels),key='workflow_vendor_choices_'+context)
    rows=pool[pool.vendor.isin(selected)].copy()
    values=(current or {}).get('values',{})
    editor=pd.DataFrame([{'Vendor':flow.vendor_label(r.vendor,labels),
                         'Nilai penawaran':values.get(r.vendor,float(r.initial_po_value))} for r in rows.itertuples()])
    edited=st.data_editor(editor,hide_index=True,disabled=['Vendor'],
                         key='workflow_vendor_values_'+context,width='stretch')
    if st.button('Terapkan untuk simulasi berikutnya',key='workflow_save_vendors'):
        try:
            flow.save_settings(db,context,selected,dict(zip(rows.vendor,edited['Nilai penawaran'])),list(pool.vendor))
            st.success('Konfigurasi tersimpan. Jalankan skenario baru untuk menggunakannya.')
        except (ValueError,KeyError) as exc:st.error(str(exc))
    st.caption('Vendor dapat dipakai lagi pada permintaan lain jika tercatat pada kategorinya. '
      'Nilai awal adalah median PO historis anonim, bukan harga per unit atau rupiah.')


def render_offer_page():
    st.title(flow.COMPANY_NAME)
    st.caption('Simulasi pengadaan CatBoost · IRE → VMI → DA → SLM → evaluasi pembelian')
    metadata_path=Path(MODEL_DIR)/'metrics.json'
    if not metadata_path.exists():st.warning('Model penawaran CatBoost belum tersedia.');return
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    all_catalog=flow.catalog();labels=flow.names()
    contexts=sorted(all_catalog.context_key.unique(),key=lambda k:(k.split(' | ')[1]!='Office Supplies',request_label(k)))
    if not contexts:st.error('Tidak tersedia kategori dengan minimal lima vendor.');return
    db=flow.connect()
    try:
        with st.sidebar:
            st.header('Contoh simulasi CatBoost')
            example=st.selectbox('Pilih contoh CatBoost',list(CATBOOST_EXAMPLES),key='catboost_example')
            st.caption(CATBOOST_EXAMPLES[example]['goal'])
            if st.button('Terapkan contoh CatBoost',key='apply_catboost_example'):
                preset=CATBOOST_EXAMPLES[example]
                chosen=next((k for k in contexts if k.split(' | ')[1]==preset['sub'] and k.split(' | ')[2]=='Standard'),None)
                if chosen is None:chosen=next(k for k in contexts if k.split(' | ')[1]==preset['sub'])
                candidates=flow.candidates(all_catalog,chosen,flow.load_settings(db,chosen))
                factor=preset['budget_factor']
                value=.01 if factor==0 else (float(candidates.initial_po_value.max())*factor)
                if factor==.5:value=float(candidates.initial_po_value.median())
                st.session_state['workflow_context']=chosen
                st.session_state['workflow_budget']=max(value,.01)
                st.session_state['workflow_date']=date(2018,9,1)
            st.caption('Terapkan contoh, lalu klik Buat & jalankan skenario untuk melihat alurnya.')
            st.header('Permintaan baru')
            st.write('**'+flow.COMPANY_NAME+'**')
            context=st.selectbox('Jenis permintaan',contexts,format_func=request_label,key='workflow_context')
            settings=flow.load_settings(db,context)
            rows=flow.candidates(all_catalog,context,settings)
            st.session_state.setdefault('workflow_budget',max(float(rows.initial_po_value.max()),1.))
            with st.form('workflow_request'):
                budget=st.number_input('Anggaran · satuan nilai BPI',min_value=.01,
                  key='workflow_budget')
                proposal_date=st.date_input('Tanggal permintaan',key='workflow_date')
                st.caption(f'{len(rows)} vendor tersedia. Ubah nilainya pada tab Konfigurasi vendor.')
                submit=st.form_submit_button('Buat & jalankan skenario',type='primary')
            st.caption('Model memakai ID dan konteks BPI; perusahaan ditampilkan sebagai PT. Biz Indonesia Market.')
        if submit:
            with st.spinner('Menjalankan CatBoost dan merekam setiap langkah...'):
                run_id=_start(db,rows,context,budget,proposal_date)
            st.session_state['workflow_history']=run_id
        history=flow.runs(db)
        if not history:
            run_id=_start(db,rows,context,budget,proposal_date,demo=True)
            st.session_state['workflow_history']=run_id;history=flow.runs(db)
        ids=[r['id'] for r in history];lookup={r['id']:r for r in history}
        selected=st.selectbox('Riwayat skenario',ids,key='workflow_history',
            format_func=lambda n:f"#{n} · CatBoost · {lookup[n]['status']} · {lookup[n]['review_decision']}")
        run=flow.load_run(db,selected)
        if run['request'].get('is_demo'):st.caption('Contoh simulasi CatBoost otomatis dari lima vendor dataset. Buat skenario baru melalui panel kiri.')
        current_key=f"workflow_step_{run['id']}";visible_step=st.session_state.get(current_key,1)
        if visible_step>=len(run['events']):
            if run['status']=='SARAN LANJUT':st.success('Evaluasi selesai: ada kandidat untuk dilanjutkan ke review pembelian.')
            else:st.warning('Evaluasi selesai: penawaran memerlukan tinjauan atau revisi.')
        else:st.info('Simulasi siap ditelusuri. Gunakan Maju/Mundur untuk melihat keputusan setiap agen.')
        metrics=st.columns(4);s=run['results']['selected']
        metrics[0].metric('Perusahaan',flow.COMPANY_NAME)
        metrics[1].metric('Vendor diperiksa',len(run['results']['rows']))
        metrics[2].metric('Anggaran',f"{run['request']['budget']:,.2f}")
        metrics[3].metric('Nilai kandidat',f"{s['nilai_penawaran']:,.2f}" if s and visible_step>=len(run['events']) else '—')
        process,report,config=st.tabs(['Proses agen','Pelaporan','Konfigurasi vendor'])
        with process:_process(run)
        with report:_report(db,run,labels,metadata)
        with config:_settings(db,all_catalog,context,labels)
    finally:db.close()
