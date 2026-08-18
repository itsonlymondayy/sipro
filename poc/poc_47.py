#!/usr/bin/env python3
"""poc_47.py — POC WAJIB Fase 47 (uang masuk & pekerjaan yang bisa dipertanggungjawabkan).

SATU berkas, empat inti yang paling mudah salah — dibuktikan SEBELUM satu piksel dibuat:

  1. IMPOR MUTASI BANK  : dry-run tidak menulis apa pun; impor ulang berkas yang sama =
                          `unchanged` (bukan mutasi kembar); keterangan/saldo berubah =
                          `updated` + `history`; baris cacat DITOLAK dengan alasan; format
                          angka Indonesia (1.500.000,00) dibaca benar.
  2. PENCOCOKAN         : mutasi yang BELUM dicocokkan TIDAK PERNAH mengurangi tagihan;
                          pencocokan memakai jalur resmi (`apply_receipt`) sehingga tidak ada
                          dua kebenaran; pembatalan mengembalikan tagihan PERSIS + jurnal
                          pembalik; arah mutasi yang tidak cocok ditolak.
  3. BUKTI TRANSFER     : klaim pelanggan dari portal TIDAK mengubah AR sebelum diverifikasi;
                          bukti kembar (sha256 sama) ditolak; penolakan wajib beralasan
                          panjang (alasan dibaca pelanggan); verifikasi mengubah AR sekali saja.
  4. PENAWARAN & UPAH   : termin penawaran TIE-OUT dengan `finance_engine.compute_scheme_items`;
                          simulasi KPR kosong = "belum ada data" (bukan 0); diskon di atas
                          kewenangan wajib disetujui; absensi dobel ditolak (index unik);
                          upah = hari x tarif + lembur, rekap TIE-OUT ke absensi, pembayaran
                          melahirkan jurnal seimbang + tautan realisasi anggaran.

Jalankan: `python3 poc/poc_47.py` (butuh Mongo hidup + DB seed). Exit != 0 bila ada FAIL.
SEMUA data uji dibuat & DIHAPUS kembali (bertanda `poc_47`), dan POC bisa dijalankan
BERULANG KALI — pelajaran Fase 46: perangkat uji yang menumpang data seed adalah sekali pakai.
"""
import asyncio
import pathlib
import sys
from datetime import date, timedelta

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

ROOT = pathlib.Path("/app")
load_dotenv(ROOT / "backend" / ".env")

import bank_import as bimp  # noqa: E402
import bank_match as bmatch  # noqa: E402
import finance_engine as fin  # noqa: E402
import labor_engine as labor  # noqa: E402
import payment_intake as intake  # noqa: E402
import quotation_engine as qe  # noqa: E402
import settings_store as cfg  # noqa: E402
from core_utils import new_id, now_iso, today_iso_date  # noqa: E402
from db import ORG_ID, db  # noqa: E402

fails = []
TAG = "poc_47"


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)
    return bool(cond)


def _day(offset: int) -> str:
    return (date.fromisoformat(today_iso_date()) + timedelta(days=offset)).isoformat()


# ============================================================ fixture
async def purge():
    """Bersihkan sisa run sebelumnya (POC harus bisa diulang kapan saja)."""
    units = [u["id"] for u in await db.units.find({TAG: True}, {"_id": 0, "id": 1}).to_list(50)]
    deals = [d["id"] for d in await db.deals.find({TAG: True}, {"_id": 0, "id": 1}).to_list(50)]
    workers = [w["id"] for w in await db.workers.find({TAG: True},
                                                     {"_id": 0, "id": 1}).to_list(50)]
    for coll, q in (
        ("bank_transactions", {TAG: True}), ("bank_statements", {TAG: True}),
        ("bank_accounts", {TAG: True}), ("bank_matches", {TAG: True}),
        ("payment_intakes", {TAG: True}), ("quotations", {TAG: True}),
        ("labor_attendance", {"worker_id": {"$in": workers}}),
        ("labor_payrolls", {TAG: True}), ("workers", {TAG: True}),
        ("addon_items", {TAG: True}), ("site_diaries", {TAG: True}),
        ("ar_invoices", {"deal_id": {"$in": deals}}),
        ("receipts", {"deal_id": {"$in": deals}}),
        ("contract_liabilities", {"deal_id": {"$in": deals}}),
        ("tax_records", {"deal_id": {"$in": deals}}),
        ("customers", {TAG: True}), ("leads", {TAG: True}),
        ("deals", {TAG: True}), ("units", {TAG: True}),
        ("journal_entries", {"source_type": {"$in": ["labor_payroll", "receipt_void",
                                                    "bank_txn", "bank_txn_void"]},
                             "posted_by": "poc47@sipro.co.id"}),
        ("activities", {"entity_id": {"$in": deals + units}}),
    ):
        await db[coll].delete_many(q)
    # jadwal bank_accounts milik POC dikenali lewat nomor rekening khusus
    await db.bank_accounts.delete_many({"account_no": "9999POC47"})
    # Absensi milik SEED yang sempat ikut masuk rekap POC harus dilepas kembali, kalau tidak
    # ia menunjuk rekap yang sudah dihapus (data menggantung = laporan yang tidak bisa dipercaya).
    live = [p["id"] for p in await db.labor_payrolls.find({}, {"_id": 0, "id": 1}).to_list(200)]
    await db.labor_attendance.update_many(
        {"payroll_id": {"$nin": live + [None]}}, {"$set": {"payroll_id": None}})


async def make_fixture() -> dict:
    """Unit + lead + customer + deal + AR + rekening bank khusus POC (semua bertanda poc_47)."""
    project = await db.projects.find_one({"org_id": ORG_ID}, {"_id": 0})
    src = await db.units.find_one({"org_id": ORG_ID, "block_id": {"$ne": None}}, {"_id": 0})
    ts = now_iso()
    unit = {"id": new_id(), "org_id": ORG_ID, "project_id": project["id"], "code": "POC47-01",
            "type": src.get("type"), "unit_type_code": src.get("unit_type_code"),
            "unit_type_id": src.get("unit_type_id"), "price": 500_000_000,
            "status": "available", "construction_status": "not_started",
            "construction_progress": 0, "payment_status": "none",
            "block": src.get("block"), "block_id": src.get("block_id"),
            "cluster_code": src.get("cluster_code"), "cluster_id": src.get("cluster_id"),
            TAG: True, "created_at": ts, "updated_at": ts}
    await db.units.insert_one(dict(unit))
    lead = {"id": new_id(), "org_id": ORG_ID, "name": "Calon Uji POC47",
            "phone": "+628119990047", "email": "poc47.lead@example.com", "status": "hot",
            "stage": "negotiation", "source": "walk_in", "assigned_to": "sales@sipro.co.id",
            TAG: True, "created_at": ts, "updated_at": ts}
    await db.leads.insert_one(dict(lead))
    cust = {"id": new_id(), "org_id": ORG_ID, "lead_id": lead["id"], "name": lead["name"],
            "phone": lead["phone"], "email": lead["email"], TAG: True,
            "created_at": ts, "updated_at": ts}
    await db.customers.insert_one(dict(cust))
    deal = {"id": new_id(), "org_id": ORG_ID, "lead_id": lead["id"], "lead_name": lead["name"],
            "unit_id": unit["id"], "unit_code": unit["code"], "project_id": project["id"],
            "stage": "booked", "status": "active", "price": 500_000_000,
            "assigned_to": "sales@sipro.co.id", TAG: True,
            "booked_at": ts, "created_at": ts, "updated_at": ts}
    await db.deals.insert_one(dict(deal))
    inv = await fin.create_ar_for_deal(deal, org_id=ORG_ID, actor=TAG)
    acc = {"id": new_id(), "org_id": ORG_ID, "name": "Rekening Uji POC47",
           "bank_name": "Bank Uji", "account_no": "9999POC47", "holder": "PT SIPRO Land",
           "gl_account_code": "1-1200", "gl_account_name": "Bank", "opening_balance": 0,
           "is_active": True, TAG: True, "created_at": ts, "updated_at": ts}
    await db.bank_accounts.insert_one(dict(acc))
    return {"project": project, "unit": unit, "lead": lead, "customer": cust,
            "deal": deal, "invoice": inv, "account": acc}


def first_unpaid(inv: dict) -> dict:
    items = [i for i in inv["items"] if i.get("status") != "paid"]
    return sorted(items, key=lambda x: x.get("due_date") or "")[0]


# ============================================================ 1. IMPOR MUTASI
async def test_import(fx) -> dict:
    print("\n[1] IMPOR MUTASI BANK (dry-run, idempoten, baris cacat ditolak)")
    check("format angka Indonesia dibaca benar",
          bimp.parse_money("1.500.000,00") == 1500000
          and bimp.parse_money("1,500,000.00") == 1500000
          and bimp.parse_money("2500000") == 2500000,
          f"{bimp.parse_money('1.500.000,00')}/{bimp.parse_money('1,500,000.00')}")
    check("tanggal dd/mm/yyyy & ISO dibaca benar",
          bimp.parse_date("05/03/2026") == "2026-03-05"
          and bimp.parse_date("2026-03-05") == "2026-03-05"
          and bimp.parse_date("bukan tanggal") is None)
    term = first_unpaid(fx["invoice"])
    amount = int(term["amount"])
    csv_ok = "\n".join([
        "Tanggal;Keterangan;Referensi;Debit;Kredit;Saldo",
        f"{_day(-3)};TRANSFER MASUK POC47 {fx['unit']['code']};TRF/POC47/001;;{amount};900.000.000",
        f"{_day(-3)};BIAYA ADM;ADM;15.000;;899.985.000",
        f"{_day(-2)};;;;5.000.000;",                        # keterangan kosong -> ditolak
        f"tanggal-ngawur;TRANSFER;X;;1.000.000;",           # tanggal cacat -> ditolak
        f"{_day(-2)};SETORAN NOL;Y;;0;",                    # nominal nol -> ditolak
    ])
    dry = await bimp.import_csv(ORG_ID, fx["account"]["id"], "poc47.csv", csv_ok, TAG,
                               dry_run=True)
    written = await db.bank_transactions.count_documents(
        {"org_id": ORG_ID, "account_id": fx["account"]["id"]})
    check("dry-run TIDAK menulis apa pun", written == 0, f"{written} baris di database")
    check("dry-run melaporkan 2 baru & 3 ditolak",
          dry["counts"]["new"] == 2 and dry["counts"]["rejected"] == 3,
          str(dry["counts"]))
    check("setiap baris ditolak menyebut ALASANNYA",
          all(r.get("error") for r in dry["rejected"]),
          "; ".join(r["error"][:28] for r in dry["rejected"]))
    live = await bimp.import_csv(ORG_ID, fx["account"]["id"], "poc47.csv", csv_ok, TAG,
                                dry_run=False)
    check("commit menulis tepat yang dilihat pemakai saat dry-run",
          live["counts"]["new"] == dry["counts"]["new"]
          and await db.bank_transactions.count_documents(
              {"org_id": ORG_ID, "account_id": fx["account"]["id"]}) == 2,
          str(live["counts"]))
    again = await bimp.import_csv(ORG_ID, fx["account"]["id"], "poc47.csv", csv_ok, TAG,
                                 dry_run=False)
    check("impor ulang berkas SAMA = unchanged (bukan mutasi kembar)",
          again["counts"]["new"] == 0 and again["counts"]["unchanged"] == 2
          and await db.bank_transactions.count_documents(
              {"org_id": ORG_ID, "account_id": fx["account"]["id"]}) == 2,
          str(again["counts"]))
    changed = csv_ok.replace(f"TRANSFER MASUK POC47 {fx['unit']['code']}",
                             f"TRANSFER MASUK POC47 {fx['unit']['code']} (koreksi bank)")
    upd = await bimp.import_csv(ORG_ID, fx["account"]["id"], "poc47.csv", changed, TAG,
                               dry_run=False)
    txn = await db.bank_transactions.find_one(
        {"org_id": ORG_ID, "account_id": fx["account"]["id"], "direction": "in"}, {"_id": 0})
    check("keterangan berubah = updated + tercatat di history",
          upd["counts"]["updated"] == 1 and "koreksi bank" in (txn.get("description") or "")
          and len(txn.get("history") or []) >= 1, str(upd["counts"]))
    await db.bank_transactions.update_many({"account_id": fx["account"]["id"]},
                                          {"$set": {TAG: True}})
    await db.bank_statements.update_many({"account_id": fx["account"]["id"]},
                                         {"$set": {TAG: True}})
    # index unik: insert langsung dengan fingerprint sama harus GAGAL di level database
    from pymongo.errors import DuplicateKeyError
    dup_ok = False
    try:
        await db.bank_transactions.insert_one({**{k: v for k, v in txn.items()},
                                              "id": new_id()})
    except DuplicateKeyError:
        dup_ok = True
    check("index unik menolak mutasi berkunci sama (bukan hanya cek aplikasi)", dup_ok)
    inv_now = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("mutasi yang belum dicocokkan TIDAK mengurangi tagihan",
          int(inv_now["outstanding"]) == int(fx["invoice"]["outstanding"]),
          f"outstanding {inv_now['outstanding']}")
    return {"txn_in": txn,
            "txn_out": await db.bank_transactions.find_one(
                {"account_id": fx["account"]["id"], "direction": "out"}, {"_id": 0})}


# ============================================================ 2. PENCOCOKAN
async def test_match(fx, txns):
    print("\n[2] PENCOCOKAN: satu kebenaran, bisa dibatalkan, beralasan")
    txn = txns["txn_in"]
    sug = await bmatch.suggest(ORG_ID, txn["id"])
    cand = next((c for c in sug["candidates"]
                 if c["kind"] == "ar_deal" and c["target_id"] == fx["deal"]["id"]), None)
    check("usulan menemukan termin pembeli yang cocok + alasan skornya",
          cand is not None and cand["score"] >= 60 and cand["reasons"],
          f"skor {(cand or {}).get('score')} {(cand or {}).get('reasons')}")
    bad_dir = False
    try:
        await bmatch.match(ORG_ID, txn["id"], "ap_bill", "x", TAG)
    except ValueError as e:
        bad_dir = "Arah mutasi tidak cocok" in str(e)
    check("arah mutasi yang tidak cocok DITOLAK", bad_dir)
    before = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    res = await bmatch.match(ORG_ID, txn["id"], "ar_deal", fx["deal"]["id"],
                             "poc47@sipro.co.id", "Uji POC 47")
    after = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("pencocokan mengurangi tagihan PERSIS sebesar mutasi",
          int(before["outstanding"]) - int(after["outstanding"]) == int(txn["amount"]),
          f"{before['outstanding']} -> {after['outstanding']}")
    receipt_id = res["match"]["result"]["receipt_id"]
    rec = await db.receipts.find_one({"id": receipt_id}, {"_id": 0})
    check("kuitansi resmi lahir (bukan tulisan sendiri di mutasi)",
          rec is not None and int(rec["amount"]) == int(txn["amount"]))
    twice = False
    try:
        await bmatch.match(ORG_ID, txn["id"], "ar_deal", fx["deal"]["id"], TAG)
    except ValueError as e:
        twice = "sudah dicocokkan" in str(e)
    check("mutasi yang sudah dicocokkan tidak bisa dipakai dua kali", twice)
    no_reason = False
    try:
        await bmatch.unmatch(ORG_ID, txn["id"], TAG, "ok")
    except ValueError as e:
        no_reason = "minimal" in str(e)
    check("pembatalan tanpa alasan layak DITOLAK", no_reason)
    out = await bmatch.unmatch(ORG_ID, txn["id"], "poc47@sipro.co.id",
                               "Ternyata transfer milik pembeli lain, salah cocok.")
    back = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("pembatalan mengembalikan tagihan ke keadaan semula",
          int(back["outstanding"]) == int(before["outstanding"]),
          f"{after['outstanding']} -> {back['outstanding']}")
    voided = await db.receipts.find_one({"id": receipt_id}, {"_id": 0})
    check("kuitansi ditandai BATAL beserta alasannya (bukan dihapus)",
          voided.get("status") == "void" and voided.get("void_reason"),
          str(voided.get("void_reason"))[:40])
    rev = await db.journal_entries.find_one({"source_event": f"receipt.void:{receipt_id}"},
                                            {"_id": 0})
    check("jurnal PEMBALIK terbentuk & seimbang",
          rev is not None and rev["total_debit"] == rev["total_credit"] == int(txn["amount"]),
          f"{(rev or {}).get('entry_no')}")
    fresh = await db.bank_transactions.find_one({"id": txn["id"]}, {"_id": 0})
    check("mutasi kembali berstatus 'belum dicocokkan' + jejak pembatalan",
          fresh["match_state"] == "unmatched" and fresh.get("history"),
          fresh["match_state"])
    recon = await bmatch.reconciliation(ORG_ID, fx["account"]["id"])
    check("ringkasan rekonsiliasi menyebut selisih & penyebabnya",
          recon["unmatched_count"] >= 1 and recon["causes"]
          and recon["statement_balance"] is not None,
          f"belum cocok {recon['unmatched_count']}, saldo rekening {recon['statement_balance']}")
    return out


# ============================================================ 3. BUKTI TRANSFER PORTAL
async def test_intake(fx):
    print("\n[3] BUKTI TRANSFER PORTAL: klaim bukan pelunasan")
    ts = now_iso()
    files = []
    for i in range(2):
        f = {"id": new_id(), "org_id": ORG_ID, "filename": f"bukti{i}.jpg",
             "content_type": "image/jpeg", "sha256": f"poc47sha{i}", "size": 1024,
             TAG: True, "created_at": ts}
        await db.files.insert_one(dict(f))
        files.append(f)
    term = first_unpaid(await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0}))
    amount = int(term["amount"])
    before = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    row = await intake.create_from_portal(
        ORG_ID, customer=fx["customer"], deal=fx["deal"], amount=amount,
        transfer_date=_day(-1), file_ids=[files[0]["id"]], bank_name="BCA",
        note="Transfer dari rekening pribadi.", actor=fx["customer"]["email"])
    await db.payment_intakes.update_one({"id": row["id"]}, {"$set": {TAG: True}})
    mid = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("klaim pelanggan TIDAK mengubah tagihan (uji negatif inti)",
          row["state"] == "pending"
          and int(mid["outstanding"]) == int(before["outstanding"]),
          f"state={row['state']} outstanding {mid['outstanding']}")
    dup = False
    try:
        await intake.create_from_portal(
            ORG_ID, customer=fx["customer"], deal=fx["deal"], amount=amount,
            transfer_date=_day(-1), file_ids=[files[0]["id"]])
    except ValueError as e:
        dup = "sudah pernah dikirim" in str(e)
    check("bukti dengan berkas SAMA (sha256) ditolak sopan", dup)
    short = False
    try:
        await intake.reject(ORG_ID, row["id"], "finance@sipro.co.id", "salah")
    except ValueError as e:
        short = "minimal" in str(e)
    check("penolakan dengan alasan terlalu pendek DITOLAK", short)
    ver = await intake.verify(ORG_ID, row["id"], "finance@sipro.co.id",
                             note="Cocok dengan rekening koran.")
    post = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("verifikasi finance mengurangi tagihan tepat sekali",
          ver["intake"]["state"] == "verified"
          and int(before["outstanding"]) - int(post["outstanding"]) == amount,
          f"{before['outstanding']} -> {post['outstanding']}")
    twice = False
    try:
        await intake.verify(ORG_ID, row["id"], "finance@sipro.co.id")
    except ValueError as e:
        twice = "tidak bisa diverifikasi lagi" in str(e)
    check("bukti yang sudah diverifikasi tidak bisa diverifikasi ulang", twice)
    await bmatch.void_receipt(ORG_ID, ver["receipt"]["id"], "poc47@sipro.co.id",
                              "Uji pembatalan verifikasi bukti portal.")
    await intake.revert_verification(ORG_ID, row["id"], "poc47@sipro.co.id",
                                     "Kuitansi dibatalkan.")
    reverted = await intake.intake_or_error(ORG_ID, row["id"])
    restored = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("verifikasi bisa dibatalkan: bukti kembali 'menunggu' & tagihan kembali",
          reverted["state"] == "pending"
          and int(restored["outstanding"]) == int(before["outstanding"]),
          f"state={reverted['state']} outstanding {restored['outstanding']}")
    rej = await intake.reject(ORG_ID, row["id"], "finance@sipro.co.id",
                             "Nominal pada bukti tidak sama dengan mutasi rekening kami.")
    final = await db.ar_invoices.find_one({"id": fx["invoice"]["id"]}, {"_id": 0})
    check("penolakan beralasan tidak menyentuh tagihan + alasannya tersimpan",
          rej["state"] == "rejected" and rej["reject_reason"]
          and int(final["outstanding"]) == int(before["outstanding"]),
          str(rej["reject_reason"])[:40])


# ============================================================ 4a. PENAWARAN
async def test_quotation(fx):
    print("\n[4a] PENAWARAN: tie-out harga, simulasi KPR jujur, diskon berjenjang")
    ts = now_iso()
    addon = {"id": new_id(), "org_id": ORG_ID, "code": "POC47-TANAH", TAG: True,
             "name": "Kelebihan tanah (uji)", "category": "kelebihan_tanah",
             "pricing_mode": "per_m2", "unit_price": 3_000_000, "uom": "m2",
             "finance_treatment": "revenue", "active": True,
             "created_at": ts, "updated_at": ts}
    await db.addon_items.insert_one(dict(addon))
    unit = await db.units.find_one({"id": fx["unit"]["id"]}, {"_id": 0})
    sim = await qe.simulate(ORG_ID, unit_id=unit["id"],
                            addons=[{"code": "POC47-TANAH", "qty": 12}],
                            discount_amount=0, kpr=None)
    check("add-on dihitung dari master (per m2) + rumusnya dijelaskan",
          sim["addon_total"] == 36_000_000 and sim["addons"][0]["formula"],
          f"{sim['addon_total']} · {sim['addons'][0]['formula']}")
    scheme = await fin.get_default_payment_scheme(ORG_ID)
    expect = fin.compute_scheme_items(scheme, sim["net_price"], today_iso_date())
    check("termin penawaran TIE-OUT dengan mesin AR (tidak ada rumus kedua)",
          [int(t["amount"]) for t in sim["terms"]] == [int(e["amount"]) for e in expect]
          and sim["terms_total"] == sum(int(e["amount"]) for e in expect),
          f"total termin {sim['terms_total']} vs harga {sim['net_price']}")
    check("simulasi KPR tanpa data = 'belum ada data' (bukan 0)",
          sim["kpr"]["state"] == "missing_data"
          and sim["kpr"]["monthly_installment"] is None
          and set(sim["kpr"]["missing"]) >= {"tenor_bulan", "bunga_tahunan"},
          str(sim["kpr"]["missing"]))
    with_kpr = await qe.simulate(ORG_ID, unit_id=unit["id"], addons=[],
                                 kpr={"tenor_months": 180, "annual_rate_pct": 9.0,
                                      "dp_pct": 20})
    loan = int(unit["price"]) - int(round(int(unit["price"]) * 0.2))
    i = 0.09 / 12
    manual = int(round(loan * i / (1 - (1 + i) ** -180)))
    check("angsuran KPR = rumus anuitas yang bisa dihitung ulang tangan",
          with_kpr["kpr"]["monthly_installment"] == manual,
          f"{with_kpr['kpr']['monthly_installment']} vs {manual}")
    over = False
    try:
        await qe.simulate(ORG_ID, unit_id=unit["id"], addons=[],
                          discount_amount=int(unit["price"]) * 2)
    except ValueError as e:
        over = "melebihi total harga" in str(e)
    check("diskon melebihi harga DITOLAK", over)
    limit = float(await cfg.get("quotation.discount_max_pct_sales", org_id=ORG_ID) or 0)
    big = int(int(unit["price"]) * (limit + 3) / 100)
    need_reason = False
    try:
        await qe.create(ORG_ID, lead_id=fx["lead"]["id"], unit_id=unit["id"], addons=[],
                        discount_amount=big, actor="sales@sipro.co.id")
    except ValueError as e:
        need_reason = "tulis alasan" in str(e)
    check("diskon di atas kewenangan wajib beralasan sebelum diajukan", need_reason)
    q = await qe.create(ORG_ID, lead_id=fx["lead"]["id"], unit_id=unit["id"],
                        addons=[{"code": "POC47-TANAH", "qty": 12}], discount_amount=big,
                        kpr={"tenor_months": 180, "annual_rate_pct": 9.0, "dp_pct": 20},
                        discount_reason="Pembeli menawar keras & siap bayar DP hari ini.",
                        actor="sales@sipro.co.id")
    await db.quotations.update_many({"lead_id": fx["lead"]["id"]}, {"$set": {TAG: True}})
    check("penawaran berdiskon besar berstatus MENUNGGU PERSETUJUAN",
          q["state"] == "awaiting_approval" and q["needs_discount_approval"],
          f"{q['no']} v{q['version']} state={q['state']}")
    blocked = False
    try:
        await qe.convert(ORG_ID, q["id"], "sales@sipro.co.id")
    except ValueError as e:
        blocked = "belum disetujui" in str(e)
    check("konversi sebelum diskon disetujui DITOLAK (uji negatif)", blocked)
    approved = await qe.decide_discount(ORG_ID, q["id"], "manager@sipro.co.id", True,
                                        "Disetujui: unit slow moving, margin masih sehat.")
    check("manajer menyetujui diskon + alasan tersimpan",
          approved["state"] == "approved" and approved["decision_reason"],
          str(approved["decision_reason"])[:40])
    rev = await qe.create(ORG_ID, lead_id=fx["lead"]["id"], unit_id=unit["id"], addons=[],
                          discount_amount=0, actor="sales@sipro.co.id", version_of=approved)
    await db.quotations.update_many({"lead_id": fx["lead"]["id"]}, {"$set": {TAG: True}})
    old = await qe.get(ORG_ID, q["id"])
    check("revisi = versi baru; versi lama tetap terbaca sebagai 'diganti'",
          rev["version"] == approved["version"] + 1 and old["state"] == "superseded",
          f"v{rev['version']} · lama={old['state']}")
    conv = await qe.convert(ORG_ID, rev["id"], "sales@sipro.co.id")
    unit_after = await db.units.find_one({"id": unit["id"]}, {"_id": 0})
    check("konversi membuat reservasi & unit menjadi 'reserved' + jejak penawaran",
          conv["deal"]["quotation_id"] == rev["id"]
          and unit_after["status"] == "reserved"
          and unit_after["reserved_by_deal"] == conv["deal"]["id"],
          f"unit {unit_after['status']}")
    await db.deals.update_one({"id": conv["deal"]["id"]}, {"$set": {TAG: True}})
    again = False
    try:
        await qe.convert(ORG_ID, rev["id"], "sales@sipro.co.id")
    except ValueError as e:
        again = "sudah menjadi reservasi" in str(e)
    check("penawaran yang sudah dikonversi tidak bisa dikonversi lagi", again)


# ============================================================ 4b. ABSENSI & UPAH
async def test_labor(fx):
    print("\n[4b] ABSENSI & UPAH: dobel ditolak, upah bisa direkonstruksi, masuk pembukuan")
    project = fx["project"]
    ids = []
    for name, role, wage in (("POC47 Mandor", "mandor", 200_000),
                             ("POC47 Tukang A", "tukang", 150_000),
                             ("POC47 Tukang B", "tukang", 150_000)):
        w = await labor.create_worker(ORG_ID, {
            "name": name, "role": role, "daily_wage": wage,
            "project_ids": [project["id"]], "is_active": True}, TAG)
        await db.workers.update_one({"id": w["id"]}, {"$set": {TAG: True}})
        ids.append(w["id"])
    dup_payload = False
    try:
        await labor.record_attendance(ORG_ID, project_id=project["id"], work_date=_day(-1),
                                      entries=[{"worker_id": ids[0], "status": "full"},
                                               {"worker_id": ids[0], "status": "half"}],
                                      actor=TAG)
    except ValueError as e:
        dup_payload = "dua kali" in str(e)
    check("satu orang dua kali dalam satu kiriman DITOLAK", dup_payload)
    future = False
    try:
        await labor.record_attendance(ORG_ID, project_id=project["id"], work_date=_day(3),
                                      entries=[{"worker_id": ids[0], "status": "full"}],
                                      actor=TAG)
    except ValueError as e:
        future = "belum terjadi" in str(e)
    check("absensi untuk tanggal yang belum terjadi DITOLAK", future)
    day1 = await labor.record_attendance(
        ORG_ID, project_id=project["id"], work_date=_day(-2),
        entries=[{"worker_id": ids[0], "status": "full", "overtime_hours": 2},
                 {"worker_id": ids[1], "status": "full"},
                 {"worker_id": ids[2], "status": "half"}], actor=TAG)
    rate = await labor.rates(ORG_ID)
    mandor = next(e for e in day1["entries"] if e["worker_id"] == ids[0])
    manual = 200_000 + int(round(2 * (200_000 / rate["normal_hours"])
                                 * rate["overtime_multiplier"]))
    check("upah 1 hari + lembur = rumus yang bisa dihitung ulang tangan",
          mandor["total"] == manual, f"{mandor['total']} vs {manual} ({mandor['formula']})")
    half = next(e for e in day1["entries"] if e["worker_id"] == ids[2])
    check("setengah hari = 0,5 x upah harian (bukan penuh, bukan nol)",
          half["total"] == 75_000, str(half["total"]))
    same = await labor.record_attendance(
        ORG_ID, project_id=project["id"], work_date=_day(-2),
        entries=[{"worker_id": ids[2], "status": "full"}], actor=TAG)
    rows = await db.labor_attendance.count_documents(
        {"org_id": ORG_ID, "project_id": project["id"], "work_date": _day(-2),
         "worker_id": {"$in": ids}})
    check("koreksi absensi hari sama = DIPERBARUI (bukan baris kembar) + berjejak",
          rows == 3 and same["entries"][0]["action"] == "updated"
          and same["entries"][0]["total"] == 150_000, f"{rows} baris")
    from pymongo.errors import DuplicateKeyError
    hard = False
    try:
        doc = await db.labor_attendance.find_one(
            {"project_id": project["id"], "work_date": _day(-2), "worker_id": ids[0]},
            {"_id": 0})
        await db.labor_attendance.insert_one({**doc, "id": new_id()})
    except DuplicateKeyError:
        hard = True
    check("index unik database menolak absensi kembar", hard)
    diary = {"id": new_id(), "org_id": ORG_ID, "project_id": project["id"], TAG: True,
             "log_date": _day(-2) + "T08:00:00+00:00", "weather": "cerah", "workforce": 8,
             "work_description": "Uji POC 47", "created_at": now_iso()}
    await db.site_diaries.insert_one(dict(diary))
    chk = await labor.diary_check(ORG_ID, project["id"], _day(-2))
    check("selisih dengan buku harian DILAPORKAN (tidak menimpa salah satu)",
          chk["state"] == "mismatch" and chk["diary_workforce"] == 8
          and chk["difference"] == chk["present"] - 8 and chk["detail"],
          f"hadir {chk['present']} vs buku harian {chk['diary_workforce']}")
    day2 = await labor.record_attendance(
        ORG_ID, project_id=project["id"], work_date=_day(-1),
        entries=[{"worker_id": w, "status": "full"} for w in ids], actor=TAG)
    att = await labor.attendance(ORG_ID, project_id=project["id"], date_from=_day(-2),
                                 date_to=_day(-1), worker_id=None)
    mine = [r for r in att["data"] if r["worker_id"] in ids]
    payroll = await labor.build_payroll(ORG_ID, project_id=project["id"],
                                        period_start=_day(-2), period_end=_day(-1),
                                        actor=TAG, note="Uji POC 47")
    await db.labor_payrolls.update_one({"id": payroll["id"]}, {"$set": {TAG: True}})
    mine_total = sum(int(r["total"]) for r in mine)
    check("rekap upah TIE-OUT dengan absensi (angka bisa dilacak per orang per hari)",
          payroll["total"] >= mine_total and payroll["worker_count"] >= 3
          and sum(int(x["total"]) for x in payroll["lines"]) == payroll["total"],
          f"rekap {payroll['total']} · absensi POC {mine_total} · {day2['present']} hadir")
    overlap = False
    try:
        await labor.build_payroll(ORG_ID, project_id=project["id"], period_start=_day(-2),
                                  period_end=_day(-1), actor=TAG)
    except ValueError as e:
        overlap = "bertumpang" in str(e)
    check("periode rekap yang bertumpang DITOLAK (upah tidak boleh dibayar dua kali)",
          overlap)
    await labor.submit_payroll(ORG_ID, payroll["id"], TAG)
    locked = False
    try:
        await labor.record_attendance(ORG_ID, project_id=project["id"], work_date=_day(-1),
                                      entries=[{"worker_id": ids[0], "status": "half"}],
                                      actor=TAG)
    except ValueError as e:
        locked = "sudah masuk rekap upah" in str(e)
    check("absensi pada periode yang sudah direkap TERKUNCI", locked)
    early = False
    try:
        await labor.pay_payroll(ORG_ID, payroll["id"], "finance@sipro.co.id")
    except ValueError as e:
        early = "harus DISETUJUI" in str(e)
    check("upah tidak bisa dibayar sebelum disetujui (uji negatif)", early)
    no_reason = False
    try:
        await labor.decide_payroll(ORG_ID, payroll["id"], "finance@sipro.co.id", False, "x")
    except ValueError as e:
        no_reason = "beralasan" in str(e)
    check("penolakan rekap upah wajib beralasan", no_reason)
    await labor.decide_payroll(ORG_ID, payroll["id"], "finance@sipro.co.id", True,
                              "Cocok dengan absensi lapangan.")
    paid = await labor.pay_payroll(ORG_ID, payroll["id"], "poc47@sipro.co.id",
                                  note="Uji POC 47")
    je = await db.journal_entries.find_one({"source_event": f"labor.paid:{payroll['id']}"},
                                           {"_id": 0})
    codes = {ln["account_code"]: ln for ln in (je or {}).get("lines", [])}
    check("pembayaran upah melahirkan jurnal seimbang (Dr WIP / Cr Bank)",
          je is not None and je["total_debit"] == je["total_credit"] == payroll["total"]
          and codes.get("1-1600", {}).get("debit") == payroll["total"]
          and codes.get("1-1200", {}).get("credit") == payroll["total"],
          f"{(je or {}).get('entry_no')}")
    check("status rekap menjadi 'sudah dibayar' + nomor jurnal tercatat",
          paid["state"] == "paid" and paid.get("journal_no"), paid.get("journal_no"))
    dup_pay = False
    try:
        await labor.pay_payroll(ORG_ID, payroll["id"], "poc47@sipro.co.id")
    except ValueError as e:
        dup_pay = "harus DISETUJUI" in str(e)
    check("rekap yang sudah dibayar tidak bisa dibayar lagi", dup_pay)
    import budget_engine as be
    check("upah terdaftar sebagai sumber realisasi anggaran (cost_ref)",
          any(src[0] == "labor_payrolls" for src in be.COST_REF_SOURCES))


async def main():
    print("=" * 78)
    print("POC FASE 47 — Rekonsiliasi Bank, Bukti Transfer Portal, Penawaran, Upah Harian")
    print("=" * 78)
    await purge()
    fx = None
    try:
        fx = await make_fixture()
        txns = await test_import(fx)
        await test_match(fx, txns)
        await test_intake(fx)
        await test_quotation(fx)
        await test_labor(fx)
    finally:
        await purge()
        left = await db.units.count_documents({TAG: True})
        print(f"\n  bersih-bersih: sisa data POC = {left} unit (harus 0), "
              f"mutasi = {await db.bank_transactions.count_documents({TAG: True})}, "
              f"pekerja = {await db.workers.count_documents({TAG: True})}")
    print("\n" + "=" * 78)
    if fails:
        print(f"HASIL: FAIL ({len(fails)}) → " + "; ".join(fails))
        return 1
    print("HASIL: PASS — inti Fase 47 terbukti (bank, portal, penawaran, upah).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
