"""Index unik untuk natural key (temuan audit: 23 natural key tanpa proteksi DB).

Sebelum ini duplikat hanya dicegah oleh pengecekan aplikasi (`find_one` lalu `insert`),
yang bocor saat dua request datang bersamaan (race condition) atau saat data masuk lewat
jalur lain. Index unik menutup celah tersebut di level MongoDB.

Dipisah dari seed.py karena seed.py sudah menyentuh batas ukuran file (gate compliance).
Dijalankan idempoten di lifespan; index yang gagal (karena data duplikat lama) dilaporkan
tanpa menggagalkan startup.
"""
import logging

from pymongo.errors import DuplicateKeyError, OperationFailure

from db import db

logger = logging.getLogger("sipro.indexes")

# (koleksi, keys, nama index)
UNIQUE_INDEXES = [
    ("orgs", [("id", 1)], "uq_orgs_id"),
    ("projects", [("org_id", 1), ("code", 1)], "uq_projects_code"),
    ("units", [("org_id", 1), ("project_id", 1), ("code", 1)], "uq_units_code"),
    ("materials", [("org_id", 1), ("project_id", 1), ("code", 1)], "uq_materials_code"),
    ("wa_templates", [("org_id", 1), ("code", 1)], "uq_wa_templates_code"),
    ("document_templates", [("org_id", 1), ("code", 1)], "uq_doc_templates_code"),
    ("channel_accounts", [("org_id", 1), ("code", 1)], "uq_channels_code"),
    ("spk", [("org_id", 1), ("spk_number", 1)], "uq_spk_number"),
    ("purchase_orders", [("org_id", 1), ("po_number", 1)], "uq_po_number"),
    ("grns", [("org_id", 1), ("grn_number", 1)], "uq_grn_number"),
    ("progress_claims", [("org_id", 1), ("claim_number", 1)], "uq_claim_number"),
    ("change_orders", [("org_id", 1), ("co_number", 1)], "uq_co_number"),
    ("inspections", [("org_id", 1), ("inspection_number", 1)], "uq_inspection_number"),
    ("material_requisitions", [("org_id", 1), ("req_number", 1)], "uq_req_number"),
    ("journal_entries", [("org_id", 1), ("entry_no", 1)], "uq_entry_no"),
    ("documents", [("org_id", 1), ("doc_number", 1)], "uq_doc_number"),
    ("leads", [("org_id", 1), ("phone", 1)], "uq_leads_phone"),
    ("boq_items", [("org_id", 1), ("project_id", 1), ("cost_code", 1)], "uq_boq_cost_code"),
    ("construction_phases", [("org_id", 1), ("project_id", 1), ("name", 1)], "uq_phase_name"),
    ("commission_schemes", [("org_id", 1), ("name", 1)], "uq_comm_scheme_name"),
    ("payment_schemes", [("org_id", 1), ("name", 1)], "uq_pay_scheme_name"),
    ("faktur_pajak", [("org_id", 1), ("number", 1)], "uq_faktur_number"),
    ("inspection_templates", [("org_id", 1), ("code", 1)], "uq_qc_template_code"),
    ("subcontractors", [("org_id", 1), ("code", 1)], "uq_subcon_code"),
    ("customers", [("org_id", 1), ("nik", 1)], "uq_customers_nik"),
    ("portal_users", [("org_id", 1), ("phone", 1)], "uq_portal_phone"),
    # ---------------- Fase 27 ----------------
    ("cash_advances", [("org_id", 1), ("no", 1)], "uq_cashbon_no"),
    ("fixed_assets", [("org_id", 1), ("code", 1)], "uq_asset_code"),
    # Kunci idempotensi penyusutan di level DB: satu aset hanya boleh punya SATU
    # entri penyusutan per periode (mencegah jurnal dobel bila tombol diklik dua kali).
    ("asset_depreciations", [("org_id", 1), ("asset_id", 1), ("period", 1)], "uq_asset_depr"),
    ("loans", [("org_id", 1), ("no", 1)], "uq_loan_no"),
    ("agents", [("org_id", 1), ("name", 1)], "uq_agent_name"),
    ("marketing_fees", [("org_id", 1), ("no", 1)], "uq_marketing_fee_no"),
    # ---------------- Fase 31: jadwal pembangunan per unit ----------------
    ("build_templates", [("org_id", 1), ("code", 1)], "uq_build_template_code"),
    # Satu unit hanya boleh punya SATU jadwal aktif (mencegah progres ganda).
    ("build_schedules", [("org_id", 1), ("unit_id", 1)], "uq_build_schedule_unit"),
    ("build_items", [("org_id", 1), ("schedule_id", 1), ("step_code", 1)], "uq_build_item_step"),
    # ---------------- Fase 47: uang masuk & upah harian ----------------
    # Satu rekening hanya sekali terdaftar (nomor rekening = kunci alami).
    ("bank_accounts", [("org_id", 1), ("account_no", 1)], "uq_bank_account_no"),
    # Kunci alami mutasi: impor ulang berkas yang sama TIDAK boleh melahirkan mutasi kembar
    # (mutasi kembar = pelunasan kembar = laporan kas yang salah).
    ("bank_transactions", [("org_id", 1), ("fingerprint", 1)], "uq_bank_txn_fingerprint"),
    # Satu orang hanya boleh punya SATU catatan absensi per proyek per hari; absensi ganda
    # langsung menjadi upah ganda, jadi dijaga di level database.
    ("labor_attendance", [("org_id", 1), ("project_id", 1), ("work_date", 1),
                          ("worker_id", 1)], "uq_labor_attendance"),
    ("workers", [("org_id", 1), ("name", 1)], "uq_worker_name"),
    ("labor_payrolls", [("org_id", 1), ("no", 1)], "uq_labor_payroll_no"),
    ("quotations", [("org_id", 1), ("no", 1), ("version", 1)], "uq_quotation_version"),
    # ---------------- Fase 39: hierarki proyek + master baru ----------------
    ("clusters", [("org_id", 1), ("project_id", 1), ("code", 1)], "uq_cluster_code"),
    ("blocks", [("org_id", 1), ("cluster_id", 1), ("code", 1)], "uq_block_code"),
    ("unit_types", [("org_id", 1), ("code", 1)], "uq_unit_type_code"),
    ("addon_items", [("org_id", 1), ("code", 1)], "uq_addon_code"),
    ("price_components", [("org_id", 1), ("code", 1)], "uq_price_component_code"),
    ("doc_requirements", [("org_id", 1), ("code", 1)], "uq_doc_requirement_code"),
    # Satu setting = satu nilai per scope (org/project/cluster).
    ("settings", [("org_id", 1), ("scope", 1), ("scope_id", 1), ("key", 1)], "uq_setting_scope"),
    # Satu berkas hanya boleh diserahkan sekali untuk syarat & entitas yang sama.
    ("doc_submissions", [("org_id", 1), ("entity_type", 1), ("entity_id", 1),
                         ("requirement_code", 1), ("file_id", 1)], "uq_doc_submission"),
    # ---------------- Fase 43: kampanye, biaya iklan, CAPI ----------------
    # Nama kampanye per platform unik supaya baris CSV bisa dicocokkan tanpa ambigu.
    ("campaigns", [("org_id", 1), ("platform", 1), ("name", 1)], "uq_campaign_name"),
    ("campaigns", [("org_id", 1), ("code", 1)], "uq_campaign_code"),
    # KUNCI IDEMPOTENSI BIAYA IKLAN. Laporan platform sering diunduh dengan rentang
    # tanggal bertumpuk; tanpa index ini impor kedua akan MELIPATGANDAKAN biaya dan
    # semua metrik (CPL/CAC/ROAS) menjadi salah tanpa ada yang sadar.
    ("ad_spend", [("org_id", 1), ("platform", 1), ("campaign_id", 1), ("adset_id", 1),
                  ("ad_id", 1), ("date", 1)], "uq_ad_spend_natural"),
    # Satu peristiwa konversi = satu event_id (platform juga men-dedup dengan field ini).
    ("conversion_events", [("org_id", 1), ("event_id", 1)], "uq_conversion_event_id"),
    # ---------------- Fase 44: snapshot metrik BI ----------------
    # Satu metrik = satu baris per periode. Tanpa index ini, job harian yang berjalan dua kali
    # (atau tombol "hitung ulang") akan menumpuk baris snapshot dan grafik tren menampilkan
    # titik ganda untuk hari yang sama.
    ("metric_snapshots", [("org_id", 1), ("code", 1), ("period_key", 1)], "uq_metric_snapshot"),
    # ---------------- Fase 45: target & master anggaran ----------------
    # Satu kode anggaran hanya boleh muncul SEKALI per proyek. Tanpa index ini, dua orang yang
    # menambah item "OPS-GAJI" bersamaan akan membuat anggaran yang sama terhitung dua kali di
    # laporan overbudget (pengecekan aplikasi saja bocor saat request datang serentak).
    ("budget_items", [("org_id", 1), ("project_id", 1), ("code", 1)], "uq_budget_item_code"),
    # Satu nama target per proyek+cakupan: mencegah "Target 2026" kembar yang membuat dua
    # rencana resmi berbeda untuk proyek yang sama.
    ("project_targets", [("org_id", 1), ("project_id", 1), ("name", 1)], "uq_project_target_name"),
]

# Natural key yang boleh kosong (partial index: hanya baris yang punya nilai dijaga).
PARTIAL = {
    "uq_boq_cost_code": "cost_code",
    # Fase 43: baris `conversion_events` warisan (sebelum ada `event_id`) tidak punya field
    # itu; index unik biasa akan menolak baris kedua yang `event_id`-nya null. Partial index
    # menjaga keunikan HANYA untuk event yang benar-benar punya ID dedup.
    "uq_conversion_event_id": "event_id",
    "uq_doc_number": "doc_number",
    "uq_leads_phone": "phone",
    "uq_faktur_number": "number",
    "uq_spk_number": "spk_number",
    "uq_po_number": "po_number",
    "uq_grn_number": "grn_number",
    "uq_claim_number": "claim_number",
    "uq_co_number": "co_number",
    "uq_inspection_number": "inspection_number",
    "uq_req_number": "req_number",
    "uq_entry_no": "entry_no",
    "uq_customers_nik": "nik",
    "uq_portal_phone": "phone",
    "uq_cashbon_no": "no",
    "uq_asset_code": "code",
    "uq_loan_no": "no",
    "uq_marketing_fee_no": "no",
}


async def ensure_unique_indexes() -> dict:
    """Buat semua index unik. Kembalikan {created: [...], conflicts: [...]}

    Fase 43 menambah satu penanganan yang sebelumnya hilang: bila index dengan NAMA SAMA
    sudah ada tetapi OPSInya berbeda (mis. dulu unik biasa, sekarang harus partial karena
    ada baris lama tanpa field kunci), MongoDB menolak dengan `IndexKeySpecsConflict` dan
    dulu itu hanya dicatat sebagai "sudah terlindungi". Akibatnya index versi lama tetap
    dipakai selamanya \u2014 perbaikan tidak pernah benar-benar berlaku pada database yang sudah
    jalan. Sekarang index lama dibuang lalu dibuat ulang; bila pembuatan ulang gagal karena
    DATA memang duplikat, itu dilaporkan sebagai conflict (bukan disembunyikan).
    """
    created, already, conflicts = [], [], []
    for coll, keys, name in UNIQUE_INDEXES:
        kwargs = {"unique": True, "name": name}
        field = PARTIAL.get(name)
        if field:
            kwargs["partialFilterExpression"] = {field: {"$type": "string"}}
        try:
            await db[coll].create_index(keys, **kwargs)
            created.append(name)
            continue
        except (DuplicateKeyError, OperationFailure) as e:
            msg = str(e)
        if "already exists with a different name" in msg:
            already.append(name)  # sudah terlindungi index unik lain (nama berbeda)
            continue
        if "same name as the requested index" in msg or "IndexKeySpecsConflict" in msg \
                or "IndexOptionsConflict" in msg:
            try:
                await db[coll].drop_index(name)
                await db[coll].create_index(keys, **kwargs)
                created.append(name)
                logger.info("Index %s.%s dibuat ulang dengan opsi baru", coll, name)
                continue
            except (DuplicateKeyError, OperationFailure) as e2:
                msg = str(e2)
        conflicts.append({"index": name, "collection": coll, "error": msg[:200]})
    if conflicts:
        logger.warning("Index unik gagal dibuat (ada data duplikat lama): %s",
                       [c["index"] for c in conflicts])
    return {"created": created, "already_protected": already, "conflicts": conflicts}


async def ensure_optional_unique(coll: str, keys: list, name: str, field: str) -> None:
    """Index unik untuk kunci yang BOLEH kosong (mis. `client_ref` antrean offline).

    Jebakan nyata yang ditutup di sini: pada index GABUNGAN, `sparse=True` hanya melewati
    dokumen yang tidak punya SELURUH field terindeks. Karena `org_id` selalu ada, dokumen
    tanpa `client_ref` tetap terindeks sebagai `null`, sehingga baris KEDUA tanpa penanda
    langsung bentrok (E11000 → HTTP 500). Ini sempat membuat pengajuan hasil kerja dari
    layar biasa (tanpa antrean) gagal pada percobaan kedua. Yang benar adalah PARTIAL
    index: hanya baris yang benar-benar punya nilai string yang dijaga keunikannya.

    Index lama dengan pola kunci sama tapi opsi berbeda dibuang lebih dulu, supaya
    perbaikan ini juga berlaku pada database yang sudah jalan.
    """
    want = {field: {"$type": "string"}}
    pattern = [k[0] for k in keys]
    try:
        info = await db[coll].index_information()
    except OperationFailure:
        info = {}
    for iname, spec in (info or {}).items():
        if iname == "_id_":
            continue
        if [k[0] for k in spec.get("key", [])] == pattern \
                and spec.get("partialFilterExpression") != want:
            try:
                await db[coll].drop_index(iname)
                logger.info("Index %s.%s dibuat ulang sebagai partial index", coll, iname)
            except OperationFailure as e:
                logger.warning("Gagal membuang index lama %s.%s: %s", coll, iname, str(e)[:120])
    await db[coll].create_index(keys, unique=True, name=name, partialFilterExpression=want)
