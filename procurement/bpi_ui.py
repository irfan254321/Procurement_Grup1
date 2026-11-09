"""Inspect learned next-activity predictions on held-out BPI procurement cases."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import streamlit as st


def _setup_instructions() -> None:
    st.code(
        "python -m pip install -r requirements-bpi.txt\n"
        "python scripts/prepare_bpi.py\n"
        "# Hanya bila checkpoint belum ada atau ingin melatih ulang:\n"
        "python scripts/train_bpi.py",
        language="powershell",
    )
    st.caption("Jalankan dari folder proyek. Impor dan training dilakukan sekali, bukan setiap membuka halaman.")


def _fraction(value) -> str:
    return "—" if value is None else f"{float(value):.1%}"


def render_bpi_page(db_path: str | Path | None = None, model_dir: str | Path | None = None) -> None:
    """Use only a selected observed prefix for prediction; reveal the label separately."""
    from procurement import bpi

    db_path = Path(db_path) if db_path is not None else bpi.DEFAULT_DB
    model_dir = Path(model_dir) if model_dir is not None else bpi.MODEL_DIR
    st.title("CatBoost · Proses Pengadaan BPI 2019")
    st.caption("Belajar dari urutan aktivitas purchase order yang tercatat pada BPI Challenge 2019.")
    st.info(
        "Model memprediksi aktivitas berikutnya dari riwayat yang sudah diamati. "
        "Prediksi meniru perilaku historis; hasilnya bukan bukti keputusan paling optimal "
        "dan tidak mengeksekusi pembelian atau pembayaran."
    )
    with st.expander("Hubungan dengan empat agen procurement"):
        st.write(
            "BPI mencatat aktivitas proses, bukan label aksi IRE, VMI, DA, dan SLM pada simulator. "
            "CatBoost di halaman ini merupakan satu model aktivitas berikutnya. "
            "Vendor yang tercatat sudah dipilih; model ini tidak membandingkan tawaran vendor "
            "atau mempelajari pilihan bayar cepat, jatuh tempo, dan termin. "
            "Simulasi empat agen tetap dapat dibuka melalui pilihan Simulasi MARL."
        )

    if not db_path.exists():
        st.warning("Database BPI belum tersedia. Impor dataset yang disetujui terlebih dahulu.")
        _setup_instructions()
        return

    try:
        db = bpi.connect(db_path)
        try:
            summary = bpi.dataset_summary(db)
        finally:
            db.close()
    except (sqlite3.Error, ValueError, RuntimeError) as exc:
        st.error(f"Database BPI belum dapat dibaca: {exc}")
        _setup_instructions()
        return

    if not summary:
        st.warning("Database belum berisi dataset BPI yang selesai diimpor.")
        _setup_instructions()
        return

    left, right = st.columns(2)
    left.metric("Item PO di database", f"{summary.get('cases', 0):,}")
    right.metric("Aktivitas tercatat", f"{summary.get('events', 0):,}")
    with st.expander("Sumber dataset"):
        st.write("Sumber:", summary.get("source", "BPI Challenge 2019"))
        st.write("Lisensi:", summary.get("license", "Lihat metadata sumber dataset"))
        st.caption("Identitas berkas sumber (SHA-256)")
        st.code(str(summary.get("sha256", "Belum tersedia")))

    metadata_path = model_dir / "metrics.json"
    if not metadata_path.exists():
        st.warning("Dataset sudah tersedia, tetapi CatBoost belum dilatih pada database ini.")
        _setup_instructions()
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        db = bpi.connect(db_path)
        try:
            bpi.register_model(db, model_dir)
        finally:
            db.close()
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        st.error(f"Hasil training belum dapat dibaca: {exc}")
        _setup_instructions()
        return

    metrics = metadata.get("metrics", {})
    st.subheader("Hasil pada data uji")
    accuracy, macro_f1, top3 = st.columns(3)
    accuracy.metric("Accuracy", _fraction(metrics.get("accuracy")))
    macro_f1.metric("Macro-F1", _fraction(metrics.get("macro_f1")))
    top3.metric("Top-3 accuracy", _fraction(metrics.get("top3_accuracy")))
    st.caption(
        "Accuracy menghitung kecocokan aktivitas teratas. Macro-F1 memberi bobot yang sama "
        "kepada setiap kelas aktivitas. Top-3 menghitung apakah aktivitas aktual termasuk "
        "tiga prediksi tertinggi."
    )
    with st.expander("Pembanding, pembagian data, dan batasan"):
        st.write("Accuracy tebakan kelas mayoritas:", _fraction(metrics.get("baseline_accuracy")))
        st.write("Accuracy pembanding berdasarkan aktivitas terakhir:",
                 _fraction(metrics.get("conditional_baseline_accuracy")))
        st.write("Weighted-F1:", _fraction(metrics.get("weighted_f1")))
        st.write("Jumlah sampel uji:", metrics.get("test_samples", "—"))
        st.write("Label uji yang tidak dikenal saat training:", metrics.get("unseen_test_labels", "—"))
        st.write("Jumlah sampel per bagian:", metadata.get("samples", {}))
        st.write("Pembagian data:", metadata.get("split", {}))
        for limitation in metadata.get("limitations", []):
            st.write(f"• {limitation}")
        st.caption(f"Run training: {metadata.get('run_id', '—')}")

    with st.expander("Kinerja tiap aktivitas"):
        rows = [{"Aktivitas": name, "Precision": values["precision"],
                 "Recall": values["recall"], "F1": values["f1-score"],
                 "Sampel uji": int(values["support"])}
                for name, values in metrics.get("classification_report", {}).items()
                if isinstance(values, dict) and name not in ("macro avg", "weighted avg", "micro avg")]
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("Recall 0 berarti aktivitas tersebut belum berhasil dikenali pada data uji. "
                   "Accuracy keseluruhan tidak cukup untuk menilai setiap tugas procurement.")

    try:
        db = bpi.connect(db_path)
        try:
            cases = bpi.list_test_cases(db, limit=100)
        finally:
            db.close()
    except (sqlite3.Error, ValueError, RuntimeError) as exc:
        st.error(f"Kasus uji belum dapat dibaca: {exc}")
        return
    if not cases:
        st.warning("Belum ada kasus uji yang tersimpan untuk diperiksa. Jalankan training terlebih dahulu.")
        return

    st.subheader("Coba keputusan berikutnya")
    st.caption("Pilih kasus dari data uji dan batas riwayat yang boleh dilihat model.")
    cases_by_id = {case["case_id"]: case for case in cases}
    selected = st.selectbox(
        "Item purchase order", list(cases_by_id), key="bpi_case",
        format_func=lambda case_id: (
            f"{case_id} · vendor {cases_by_id[case_id].get('vendor', '—')}"
        ),
    )
    try:
        db = bpi.connect(db_path)
        try:
            events = bpi.get_case_events(db, selected)
        finally:
            db.close()
    except (sqlite3.Error, ValueError, RuntimeError) as exc:
        st.error(f"Riwayat kasus belum dapat dibaca: {exc}")
        return
    prefixes = bpi.eligible_prefixes(events)
    if not prefixes:
        st.info("Kasus ini tidak mempunyai pasangan aktivitas berurutan dengan waktu berbeda untuk diprediksi.")
        return
    prefix_length = st.selectbox(
        "Riwayat yang sudah diamati", prefixes, key=f"bpi_prefix_{selected}",
        format_func=lambda count: f"{count} aktivitas pertama",
    )
    st.dataframe([
        {"Urutan": index + 1, "Aktivitas": event["activity"], "Waktu": event["timestamp"],
         "Nilai tercatat": event.get("value")}
        for index, event in enumerate(events[:prefix_length])
    ], hide_index=True, width="stretch")
    st.caption("Hanya riwayat di tabel ini yang masuk sebagai urutan aktivitas model. Nilai BPI telah dianonimkan.")

    selection_key = (str(db_path), str(model_dir), metadata.get("run_id"), selected, prefix_length)
    if st.button("Prediksi dengan CatBoost", type="primary", key="bpi_predict"):
        try:
            with st.spinner("CatBoost membaca riwayat yang sudah diamati..."):
                result = bpi.predict_next(selected, prefix_length, db_path=db_path,
                                          model_dir=model_dir, persist=True)
            st.session_state["bpi_prediction"] = {"selection": selection_key, "result": result}
        except (OSError, ValueError, RuntimeError, sqlite3.Error, ImportError) as exc:
            st.error(f"Prediksi belum dapat dijalankan: {exc}")
            return

    saved = st.session_state.get("bpi_prediction")
    if not saved or saved["selection"] != selection_key:
        return
    result = saved["result"]
    st.write("**Aktivitas berikutnya yang diprediksi:**", result["prediction"])
    st.dataframe([
        {"Aktivitas": item["activity"], "Probabilitas model": _fraction(item["probability"])}
        for item in result["probabilities"][:3]
    ], hide_index=True, width="stretch")
    st.caption("Probabilitas model adalah perkiraan; bukan jaminan aktivitas akan terjadi.")
    with st.expander("Bandingkan dengan kejadian aktual"):
        actual = result.get("actual_next_activity")
        if actual is None:
            st.info("Aktivitas berikutnya belum tersedia untuk dibandingkan.")
        else:
            st.write("Aktivitas aktual berikutnya:", actual)
            if result["prediction"] == actual:
                st.success("Prediksi teratas cocok dengan kejadian yang tercatat.")
            else:
                st.info("Prediksi teratas berbeda dari kejadian yang tercatat.")
        st.caption("Aktivitas aktual ini merupakan label pembanding, tidak dimasukkan ke fitur prediksi.")
    st.caption(f"Prediksi tersimpan untuk audit · ID {result.get('prediction_id', '—')} · "
               f"run {result.get('run_id', '—')}")
