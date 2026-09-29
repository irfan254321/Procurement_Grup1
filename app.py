"""Dashboard dua kebijakan MARL: jalankan episode, lalu telusuri jejak agen."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from procurement.rl_service import (CHECKPOINTS, default_vendor_rows, scenario_from_request,
                                    scenario_from_snapshot, simulate, validate_vendor_rows)
from procurement.rl_storage import (connect, load_events, load_run, load_vendor_settings,
                                    reset_vendor_settings, runs, save_run, save_vendor_settings)
from procurement.rl_presentation import audit_rows, brief_event
from procurement.baseline_ml import classify_decision, metrics_report
from procurement.models import Scenario as ReportScenario
from procurement.simulator import run as report_rule_trace
from procurement_marl.presentation import STOP_REASON, VIOLATION, rp
from procurement_marl.scenario import composite_scores, eligible_vendors


STATUS_REASON = {
    "skor": "Gagal skor", "kapasitas": "Gagal kapasitas",
    "lead_time": "Gagal tenggat", "dikecualikan": "Dikeluarkan DA",
}
PAYMENT_LABEL = {
    "bayar_cepat": "Bayar cepat", "bayar_jatuh_tempo": "Jatuh tempo",
    "revisi_termin": "Revisi termin",
}


def vendor_progress_rows(scenario, log: list[dict], step: int, current_round: int) -> list[dict]:
    """Bangun keadaan tabel sampai langkah yang sedang dibaca, bukan dari hasil akhir."""
    visible = log[:step]
    event = visible[-1]
    batch = event.get("batch")
    if batch is None:
        batch = next((x["batch"] for x in reversed(visible)
                      if x["round"] == current_round and "batch" in x), 0)
    state = {v.name: {"status": "Belum diperiksa", "price": None, "payment": "—"}
             for v in scenario.vendors}
    for item in visible:
        if item["round"] != current_round or item.get("batch", batch) != batch:
            continue
        vendor = item.get("vendor")
        kind = item.get("event")
        if kind == "vendor_check_start" and vendor:
            state[vendor]["status"] = "Sedang diperiksa"
        elif kind == "vendor_screening" and vendor:
            failed_labels = {"score": "skor", "capacity": "kapasitas", "deadline": "tenggat",
                             "not_excluded": "dikeluarkan DA"}
            failures = ", ".join(failed_labels.get(x, x) for x in item.get("failed_checks", []))
            state[vendor]["status"] = "Lolos" if item["passed"] else f"Gagal: {failures}"
        elif item["agent"] == "VMI" and vendor and kind is None:
            # Log lama belum mempunyai event pemeriksaan; alasan mask tetap direkonstruksi.
            for rejected, reason in item.get("masked", {}).items():
                state[rejected]["status"] = STATUS_REASON.get(reason, "Gagal pemeriksaan")
            for name in state:
                if name == vendor:
                    state[name]["status"] = "Dipilih"
                elif state[name]["status"] == "Lolos":
                    state[name]["status"] = "Lolos, tidak dipilih"
                elif state[name]["status"] == "Belum diperiksa" and name not in item.get("masked", {}):
                    state[name]["status"] = "Lolos, tidak dipilih"
        elif kind == "vendor_opening_offer" and vendor:
            state[vendor]["status"] = "Penawaran awal otomatis"
            state[vendor]["price"] = item["offer"]
        elif kind == "vendor_counter_offer" and vendor:
            state[vendor]["status"] = ("Sepakat" if item["accepted"] else
                                       f"Counter offer ronde {item['negotiation_round']}")
            state[vendor]["price"] = item["vendor_offer"]
        elif kind == "vendor_quote_ready" and vendor:
            state[vendor]["status"] = ("Siap dibandingkan" if item["accepted"]
                                       else "Penawaran akhir, belum sepakat")
            state[vendor]["price"] = item["price"]
        elif item["agent"] == "DA" and vendor and kind != "term_response":
            if item.get("price") is None:
                state[vendor]["status"] = "Dikeluarkan DA"
            elif item.get("withdrew"):
                state[vendor]["status"] = "Mengundurkan diri"
            else:
                state[vendor]["status"] = "Dipilih"
                state[vendor]["price"] = item["price"]
        elif kind == "payment_plan" and vendor:
            state[vendor]["payment"] = PAYMENT_LABEL.get(item["mode"], item["mode"])

    scores = composite_scores(scenario)
    return [{"Vendor": v.name, "Harga awal": rp(v.initial_offer),
             # pyrefly: ignore [bad-argument-type]
             "Penawaran terkini": rp(state[v.name]["price"]) if state[v.name]["price"] else "—",
             "Diskon cepat": f"{v.discount_pct}%", "Kapasitas": v.capacity,
             "Kirim": f"{v.lead_time} hari", "Skor": round(scores[v.name], 2),
             "Status": state[v.name]["status"], "Pembayaran": state[v.name]["payment"]}
            for v in scenario.vendors]


def competition_round_rows(log: list[dict], step: int, cycle: int, batch: int) -> list[dict]:
    """Tampilkan respons A/B/C berdampingan tanpa membocorkan langkah berikutnya."""
    rows: dict[int, dict] = {}
    for event in log[:step]:
        if event["round"] != cycle or event.get("batch") != batch:
            continue
        vendor = event.get("vendor")
        if vendor not in {"A", "B", "C"}:
            continue
        if event.get("event") == "vendor_opening_offer":
            rows.setdefault(0, {"Putaran": "Awal", "A": "—", "B": "—", "C": "—"})[vendor] = rp(event["offer"])
        elif event.get("event") == "vendor_counter_offer":
            number = event["negotiation_round"]
            rows.setdefault(number, {"Putaran": number, "A": "—", "B": "—", "C": "—"})[vendor] = (
                f"Kita {rp(event['buyer_offer'])} → vendor {rp(event['vendor_offer'])} · "
                f"{'sepakat' if event['accepted'] else 'lanjut'}")
    return [rows[key] for key in sorted(rows)]


st.set_page_config(page_title="MARL Procurement", layout="wide")
db = connect(ROOT / "data" / "procurement.sqlite3")
active_vendor_rows = load_vendor_settings(db) or default_vendor_rows()
st.title("Multi-Agent Procurement Simulator")
st.caption("Empat agen procurement terlatih bernegosiasi dengan agen vendor berbasis utilitas")

with st.sidebar:
    st.header("Skenario baru")
    with st.form("new_scenario"):
        policy_name = st.radio("Metode agen", ["CTDE", "IQL"], horizontal=True)
        quantity = st.number_input("Jumlah unit", min_value=1, value=1000, step=100)
        urgent = st.number_input("Unit mendesak", min_value=0, max_value=int(quantity),
                                 value=min(700, int(quantity)), step=100)
        budget = st.number_input("Anggaran (Rp)", min_value=1, value=100_000_000, step=1_000_000)
        seed = st.number_input("Seed simulasi", min_value=0, value=0, step=1,
                               help="Seed sama menghasilkan respons vendor yang dapat diulang.")
        submitted = st.form_submit_button("Buat & jalankan skenario", type="primary")
    st.caption("Tenggat 10 hari, kas awal Rp150 juta, dan kewajiban lain Rp70 juta memakai acuan BAB 6.")
    if submitted:
        if int(urgent) > int(quantity):
            st.error("Unit mendesak tidak boleh melebihi jumlah unit.")
        elif not CHECKPOINTS[policy_name].exists():
            st.error(f"Model {policy_name} belum dilatih. Jalankan scripts/train.py terlebih dahulu.")
        else:
            with st.spinner("Empat agen sedang menjalankan skenario..."):
                request, result, report = simulate(policy_name, int(quantity), int(urgent), int(budget), int(seed),
                                                   active_vendor_rows)
                new_id = save_run(db, policy_name, int(seed), request, result, report)
                st.session_state["run_id"] = new_id
                st.session_state["view_run"] = new_id
                st.session_state["view_step"] = 1
            st.rerun()

saved = runs(db)
run_id = None
if saved:
    ids = [row["id"] for row in saved]
    selected = st.session_state.get("run_id", ids[0])
    run_id = st.selectbox("Riwayat skenario", ids,
                          index=ids.index(selected) if selected in ids else 0,
                          format_func=lambda n: (
                              f"#{n} · {next(r['policy'] for r in saved if r['id'] == n)} · "
                              f"{next(r['status'] for r in saved if r['id'] == n)}"
                          ))
    st.session_state["run_id"] = run_id

process_tab, report_tab, vendor_tab = st.tabs(["Proses agen", "Pelaporan", "Konfigurasi vendor"])
with process_tab:
    if run_id is None:
        st.info("Masukkan tiga data inti di panel kiri, pilih CTDE atau IQL, lalu jalankan skenario.")
    else:
        saved_run = load_run(db, run_id)
        snapshot = json.loads(saved_run["scenario_json"])
        report = json.loads(saved_run["report_json"])
        scenario = scenario_from_snapshot(snapshot)
        log = load_events(db, run_id)

        if report.get("model", {}).get("model_version", 0) != 7:
            st.warning("Run arsip memakai versi aturan berbeda; status lama tidak dinilai ulang. "
                       "Jalankan skenario baru untuk melihat hasil versi sekarang.")

        if report["status"] == "LAYAK":
            st.success("Konsensus rencana: seluruh kendala simulasi terpenuhi.")
            if report.get("cash") and min(report["cash"]) < scenario.min_cash:
                st.warning("Kas akhir berada di bawah target Rp60 juta. Rencana layak menurut "
                           "syarat wajib simulasi, tetapi memiliki risiko likuiditas.")
        elif report["status"] == "TIDAK FEASIBLE":
            st.error("Skenario tidak feasible: dana tersedia tidak cukup bahkan pada biaya minimum.")
        else:
            st.warning("Agen meminta revisi sebelum rencana dapat disetujui.")
        a, b, c, d = st.columns(4)
        a.metric("Permintaan", f"{scenario.quantity} unit")
        b.metric("Mendesak", f"{scenario.urgent_quantity} unit")
        c.metric("Anggaran", rp(scenario.budget))
        d.metric("Batas biaya minimum" if report.get("total_kind") == "batas_bawah" else "Biaya rencana",
                 rp(report["total"]))

        if st.session_state.get("view_run") != run_id:
            st.session_state["view_run"] = run_id
            st.session_state["view_step"] = 1
        st.session_state["view_step"] = min(st.session_state["view_step"], len(log))
        back, forward, _ = st.columns([1, 1, 6])
        if back.button("◀ Mundur", disabled=st.session_state["view_step"] == 1):
            st.session_state["view_step"] -= 1
            st.rerun()
        if forward.button("Maju ▶", disabled=st.session_state["view_step"] == len(log)):
            st.session_state["view_step"] += 1
            st.rerun()
        step = st.slider("Langkah agen", 1, len(log), key="view_step")
        event = log[step - 1]
        st.subheader(f"Langkah {step} · Siklus {event['round']} · {event.get('reviewer', event['agent'])}")

        # Penawaran ditaruh sebelum kartu agen agar alasan pemilihan mudah dilihat.
        current_round = event["round"]
        display_batch = event.get("batch")
        if display_batch is None:
            display_batch = next((x["batch"] for x in reversed(log[:step])
                                  if x["round"] == current_round and "batch" in x), 0)
        st.markdown(f"**Penawaran vendor · batch {display_batch + 1}**")
        rounds = competition_round_rows(log, step, current_round, display_batch)
        if rounds:
            st.dataframe(pd.DataFrame(rounds), hide_index=True, width="stretch")
            st.caption("Harga per unit. Setiap sel menampilkan tawaran pembeli dan respons vendor pada putaran yang sama.")
        vendor_rows = vendor_progress_rows(scenario, log, step, current_round)
        st.dataframe(pd.DataFrame(vendor_rows), hide_index=True, width="stretch")

        # Pernyataan keputusan diletakkan di kartu pelakunya supaya pembaca langsung
        # melihat siapa yang mengambil keputusan pada langkah rekaman ini.
        message = brief_event(event)
        cards = st.columns(4)
        for card, agent in zip(cards, ("IRE", "VMI", "DA", "SLM")):
            prior_actions = [x for x in log[:step] if x["round"] == current_round and x["agent"] == agent]
            with card.container(border=True):
                st.markdown(f"**{agent}**")
                st.caption("Keputusan pada langkah ini" if event["agent"] == agent else
                           "Sudah bertindak" if prior_actions else "Menunggu giliran")
                if event["agent"] == agent:
                    st.info("**Keputusan pada langkah ini**\n\n" + message)

        # Vendor mempunyai kebijakan utilitas sendiri, tetapi bukan agen MARL
        # kelima. Kotak khusus menunjukkan kapan lawan negosiasi sedang berpikir.
        if event["agent"].startswith("VENDOR "):
            with st.container(border=True):
                st.markdown(f"**{event['agent']} · Agen negosiasi lawan**")
                st.info("**Respons vendor pada langkah ini**\n\n" + message)
                if event.get("utility") is not None:
                    st.caption(f"Nilai utilitas internal: {event['utility']:.2f}. "
                               "Vendor tidak pernah menawarkan harga di bawah batas minimumnya.")

        # ENV adalah pemeriksa sistem, bukan salah satu dari empat agen pembelajar.
        if event["agent"] == "ENV":
            with st.container(border=True):
                st.markdown("**Evaluator Sistem · Hasil langkah ini**")
                st.info("**Hasil pemeriksaan pada langkah ini**\n\n" + message)
        if event.get("event") == "payment_plan":
            st.write(f"Pembayaran direncanakan {rp(event['total'])}; cara bayar: {event['mode']}.")
        elif event.get("event") == "cek_batasan":
            st.write(f"Biaya rencana {rp(event['total'])}. Kas akhir bulan 1: {rp(event['cash'][0])}.")
        elif event.get("event") == "diagnosis":
            st.write(f"Dana tersedia {rp(event['available'])}; batas biaya minimum "
                     f"{rp(event['total'])}; kekurangan {rp(event['shortfall'])}.")
        st.caption("Maju/Mundur membaca jejak keputusan model yang sudah dijalankan; tidak menegosiasikan ulang vendor.")

with report_tab:
    if run_id is None:
        st.info("Laporan otomatis muncul setelah skenario dijalankan.")
    else:
        saved_run = load_run(db, run_id)
        report = json.loads(saved_run["report_json"])
        log = load_events(db, run_id)
        st.subheader(f"Laporan singkat #{run_id}: {report['status']}")
        model = report.get("model", {})
        if model.get("model_version", 0) != 7:
            st.warning("Laporan arsip ini memakai versi aturan berbeda; statusnya tidak dinilai ulang otomatis.")
        total_label = "Batas biaya minimum" if report.get("total_kind") == "batas_bawah" else "Biaya rencana"
        st.write(f"**Metode:** {report['policy']} · **Seed simulasi:** {report.get('seed', saved_run['seed'])} · "
                 f"**{total_label}:** {rp(report['total'])} dari anggaran {rp(report['budget'])} · "
                 f"**Siklus:** {report['rounds']}.")
        if model:
            st.caption(f"Model v{model.get('model_version', '?')} · dilatih {model.get('training_episodes', '?')} episode "
                       f"(seed {model.get('training_seed', '?')}) · SHA-256 {model.get('checkpoint_sha256', '')[:12]}…")
        if report["violations"]:
            st.write("**Kendala akhir:** " + "; ".join(VIOLATION.get(x, x) for x in report["violations"]))
        if report["status"] == "LAYAK" and report.get("cash") and min(report["cash"]) < 60_000_000:
            st.warning("Kas di bawah target Rp60 juta; target ini peringatan, bukan syarat wajib.")
        diagnosis = report.get("cash_diagnosis", {})
        if diagnosis:
            st.error(f"Bukti ketidaklayakan kas: tersedia {rp(diagnosis['available'])}, "
                     f"sedangkan biaya minimum {rp(diagnosis.get('lower_bound', diagnosis.get('total', 0)))}. "
                     f"Kekurangan {rp(diagnosis['shortfall'])}.")
        st.write("**Tindak lanjut:** " + report["next_action"])
        st.caption(STOP_REASON.get(report["stop_reason"], "Simulasi selesai."))

        st.subheader("Pembanding supervised learning")
        scenario = scenario_from_snapshot(json.loads(saved_run["scenario_json"]))
        baseline = report.get("baseline_ml")
        if not baseline:
            # Riwayat versi lama dapat dinilai tanpa mengubah record SQLite.
            baseline = classify_decision(scenario, {
                "log": log, "total": report["total"],
                "outcome": report["status"], "violations": report.get("violations", []),
            })
        if baseline.get("applicable"):
            probability = baseline["probability_optimal"]
            left, right = st.columns(2)
            left.metric(f"Klasifikasi {baseline['comparator']}", baseline["label"])
            right.metric("Probabilitas optimal", f"{probability:.1%}")
            st.caption(
                "Baseline menilai rencana setelah agen selesai. Hasil ini tidak mengganti pemeriksaan "
                "anggaran, kas, kapasitas, dan tenggat oleh environment."
            )
        else:
            st.info(f"Baseline ML: {baseline['label']}. {baseline['reason']}")

        if baseline.get("metadata"):
            with st.expander("Evaluasi Logistic Regression, SVM, Random Forest, dan XGBoost"):
                baseline_metrics = metrics_report()
                metric_rows = []
                for model_name, values in baseline_metrics["models"].items():
                    tn, fp = values["confusion_matrix"][0]
                    fn, tp = values["confusion_matrix"][1]
                    metric_rows.append({
                        "Model": model_name,
                        "Accuracy": values["accuracy"],
                        "Precision": values["precision"],
                        "Recall": values["recall"],
                        "F1-score": values["f1"],
                        "ROC-AUC": values["roc_auc"],
                        "TN / FP / FN / TP": f"{tn} / {fp} / {fn} / {tp}",
                    })
                st.dataframe(pd.DataFrame(metric_rows), hide_index=True, width="stretch",
                             column_config={name: st.column_config.NumberColumn(name, format="%.3f")
                                            for name in ("Accuracy", "Precision", "Recall", "F1-score", "ROC-AUC")})
                dataset_info = baseline_metrics["dataset"]
                st.write(f"**Sumber data:** {dataset_info['source']}.")
                st.write(f"**Pembagian:** {dataset_info['split']} · "
                         f"{dataset_info['train_rows']} baris train dan {dataset_info['test_rows']} baris test.")
                st.write(f"**Definisi label:** {dataset_info['label_rule']}.")
                st.warning("Belum ada dataset historis perusahaan pada proyek ini. Angka evaluasi di atas "
                           "mengukur generalisasi pada data simulasi, bukan performa produksi.")
        if report["cash"]:
            st.subheader("Kas akhir per bulan")
            cash = pd.DataFrame({"Bulan": range(1, len(report["cash"]) + 1),
                                 "Kas akhir": report["cash"]}).set_index("Bulan")
            st.bar_chart(cash)
        elif diagnosis:
            st.subheader("Dana tersedia dibanding biaya minimum")
            proof_chart = pd.DataFrame({
                "Nilai": [diagnosis["available"], diagnosis.get("lower_bound", diagnosis.get("total", 0))]
            }, index=["Dana tersedia", "Biaya minimum"])
            st.bar_chart(proof_chart)
        audit = pd.DataFrame(audit_rows(log, report, saved_run["seed"]))
        with st.expander("Jejak seluruh tahap"):
            st.dataframe(audit, hide_index=True, width="stretch")
        if (report["quantity"], report["urgent_quantity"], report["budget"]) == (1000, 700, 100_000_000):
            with st.expander("Pembanding angka BAB 6"):
                example = report_rule_trace(ReportScenario())
                st.write(f"Contoh laporan: seluruh unit B {rp(example.initial.total_cost)}, "
                         f"kas bulan 1 {rp(example.initial.cash_month_1)} — belum layak.")
                st.write(f"Usulan 700 B + 300 A {rp(example.staged.total_cost)}, "
                         f"kas bulan 2 {rp(example.staged.cash_month_2)} — masih belum layak.")
                st.caption("Ini rekonstruksi angka laporan, bukan tindakan yang dipilih model {0}.".format(report["policy"]))
        st.download_button("Unduh laporan singkat", json.dumps(report, ensure_ascii=False, indent=2),
                           file_name=f"laporan_{run_id}.json", mime="application/json")
        st.download_button("Unduh jejak audit (CSV)", audit.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"audit_skenario_{run_id}.csv", mime="text/csv")
        st.caption("Rencana dan laporan tersimpan di SQLite; pembelian serta pembayaran belum dieksekusi.")

with vendor_tab:
    st.subheader("Konfigurasi Vendor A, B, dan C")
    st.caption("Harga daftar menjadi titik pembuka, penawaran awal menjadi konsesi pertama, dan harga minimum "
               "tidak boleh ditembus agen vendor. Perubahan berlaku untuk skenario berikutnya.")
    vendor_notice = st.session_state.pop("vendor_notice", None)
    if vendor_notice:
        st.success(vendor_notice)
    editor_columns = {
        "name": st.column_config.TextColumn("Vendor", disabled=True),
        "list_price": st.column_config.NumberColumn("Harga daftar", min_value=1, step=500),
        "initial_offer": st.column_config.NumberColumn("Penawaran awal", min_value=1, step=500),
        "floor_price": st.column_config.NumberColumn("Harga minimum", min_value=1, step=500),
        "transport": st.column_config.NumberColumn("Transport/unit", min_value=0, step=500),
        "risk": st.column_config.NumberColumn("Risiko/unit", min_value=0, step=500),
        "quality": st.column_config.NumberColumn("Kualitas", min_value=0, max_value=10, step=1),
        "lead_time": st.column_config.NumberColumn("Kirim (hari)", min_value=1, step=1),
        "capacity": st.column_config.NumberColumn("Kapasitas", min_value=1, step=100),
        "discount_pct": st.column_config.NumberColumn("Diskon cepat (%)", min_value=0, max_value=100, step=1),
        "reputation": st.column_config.NumberColumn("Reputasi", min_value=0.0, max_value=10.0, step=0.1),
        "relation": st.column_config.NumberColumn("Relasi awal", min_value=0.0, max_value=1.0, step=0.05),
    }
    with st.form("vendor_settings_form"):
        edited_vendors = st.data_editor(pd.DataFrame(active_vendor_rows), hide_index=True,
                                        width="stretch", num_rows="fixed",
                                        column_config=editor_columns,
                                        column_order=("name", "list_price", "initial_offer", "floor_price",
                                                      "transport", "risk", "quality", "capacity", "lead_time",
                                                      "discount_pct", "reputation", "relation"),
                                        key="vendor_editor")
        apply_vendor, reset_vendor = st.columns(2)
        apply_clicked = apply_vendor.form_submit_button("Terapkan untuk skenario berikutnya", type="primary")
        reset_clicked = reset_vendor.form_submit_button("Kembalikan data BAB 6")
    if apply_clicked:
        try:
            normalized = validate_vendor_rows(edited_vendors.to_dict("records"))
            save_vendor_settings(db, [asdict(v) for v in normalized])
            st.session_state.pop("vendor_editor", None)
            st.session_state["vendor_notice"] = (
                "Konfigurasi vendor disimpan. Jalankan skenario baru untuk menggunakannya.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if reset_clicked:
        reset_vendor_settings(db)
        st.session_state.pop("vendor_editor", None)
        st.session_state["vendor_notice"] = "Konfigurasi Vendor A/B/C dikembalikan ke data BAB 6."
        st.rerun()

    try:
        preview_vendors = validate_vendor_rows(edited_vendors.to_dict("records"))
        preview = scenario_from_request(int(quantity), int(urgent), int(budget),
                                        [asdict(v) for v in preview_vendors])
        scores = composite_scores(preview)
        eligible = set(eligible_vendors(preview))
        st.markdown("**Pratinjau skor komposit**")
        st.dataframe(pd.DataFrame([
            {"Vendor": v.name, "Skor": round(scores[v.name], 2),
             "Status skor": "Lolos" if v.name in eligible else "Di bawah batas 6,0"}
            for v in preview.vendors
        ]), hide_index=True, width="stretch")
    except ValueError:
        st.caption("Perbaiki data yang tidak valid untuk melihat pratinjau skor.")
    st.info("Checkpoint tetap dapat digunakan karena pilihan vendor tetap A/B/C. Perubahan ekstrem di luar pola "
            "latihan perlu diperlakukan sebagai eksperimen.")
