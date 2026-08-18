#!/usr/bin/env python3
"""POC Fase 41 + 42 — SATU skrip, dua core workflow paling berisiko.

Dijalankan SEBELUM UI dibangun, supaya kalau intinya tidak bekerja kita tahu di sini
(bukan setelah 30 layar dibuat). Semua angka dibandingkan dengan hitungan tangan, dan
bagian end-to-end memakai ENDPOINT NYATA (reserve → book → PPJB) sehingga event bus,
lifecycle lead, jam tahap, dan mesin fee mitra diuji pada jalur yang dipakai pemakai.

A. FASE 41 — jam tahap sebagai FIELD
   A1  SLA dibaca dari Pusat Konfigurasi (bukan angka mati) & ikut berubah saat diubah
   A2  Matematika jam tahap (entered → due → due2) benar & murni
   A3  `reconcile()` mengisi jam tahap dokumen lama dari BUKTI yang tercatat (idempoten)
   A4  Transisi tahap NYATA menulis `stage_entered_at` + `stage_due_at` sesuai kebijakan
   A5  "Lewat SLA" bisa di-QUERY di database & hasilnya sama dengan hitungan Python
   A6  `resync()` memberlakukan kebijakan BARU ke baris yang sudah ada
   A7  Laporan umur tahap (agregasi DB) = hitungan langsung per tahap

B. FASE 42 — mesin aturan fee mitra
   B1  Aturan tidak sah DITOLAK sebelum tersimpan (split ≠ 100%, tier bolong/tumpang tindih, …)
   B2  Pemilihan aturan: paling spesifik menang; seri = DITOLAK dengan pesan jelas
   B3  Tujuh dasar fee dihitung sama dengan hitungan tangan
   B4  PPh 21/23 + gross-up menjaga persamaan beban = netto + PPh
   B5  Porsi pembayaran bertahap per pemicu
   B6  END-TO-END lewat API: reservasi → booking → PPJB menerbitkan fee yang benar
   B7  Idempoten: pemicu sama tidak menerbitkan tagihan kedua
   B8  Persetujuan finance menjaga invarian 2-1500 = Σ (netto − terbayar)
   B9  Pagar wajar fee (% harga) menandai butuh persetujuan owner
   B10 Atribusi lead: dua mitra mengklaim nomor yang sama → first-touch + sengketa tercatat

Jalankan: `python3 poc/poc_41_42.py` (butuh backend hidup di :8001).
"""
import asyncio
import sys
import time

sys.path.insert(0, "/app/backend")

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")

import listing as lst  # noqa: E402
import lead_lifecycle as lc  # noqa: E402
import marketing_fee as mfee  # noqa: E402
import partner_engine as pengine  # noqa: E402
import partner_fee as pfee  # noqa: E402
import settings_store as cfg  # noqa: E402
import stage_clock as clock  # noqa: E402
from core_utils import now_iso  # noqa: E402
from db import db, ORG_ID  # noqa: E402

BASE = "http://localhost:8001/api"
PW = "Sipro#2026"
MARKER = "POC Fase 41/42 — alur nyata mitra"
passed, failed = 0, 0


def check(name, cond, info=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}" + (f" — {info}" if info else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {info}" if info else ""))
    return bool(cond)


def head(title):
    print(f"\n{title}")


def login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW}, timeout=20)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------ A. Fase 41
async def section_a():
    head("A1. SLA lead dibaca dari Pusat Konfigurasi (bukan angka mati di komponen)")
    pol = await clock.policy("lead")
    check("kebijakan SLA lead terbaca", bool(pol), f"{pol}")
    check("tahap 'nurturing' punya ambang", clock.sla_for(pol, "nurturing") == 48,
          f"{clock.sla_for(pol, 'nurturing')} jam")
    check("tahap akhir 'won' TANPA janji waktu", clock.sla_for(pol, "won") is None)
    await cfg.set_value("lead.sla_hours", {**pol, "nurturing": 12}, actor="poc",
                        reason="POC 41: bukti SLA bisa diubah")
    pol2 = await clock.policy("lead")
    check("ubah setting → kebijakan ikut berubah", clock.sla_for(pol2, "nurturing") == 12,
          f"{clock.sla_for(pol2, 'nurturing')} jam")

    head("A2. Matematika jam tahap (murni, tanpa database)")
    patch = clock.clock_patch("nurturing", "2026-08-17T00:00:00+00:00", 48)
    check("due = masuk + SLA", patch[clock.DUE] == "2026-08-19T00:00:00+00:00", patch[clock.DUE])
    check("due2 = masuk + 2×SLA", patch[clock.DUE2] == "2026-08-21T00:00:00+00:00",
          patch[clock.DUE2])
    none_patch = clock.clock_patch("won", "2026-08-17T00:00:00+00:00", None)
    check("tahap tanpa SLA tidak punya jatuh tempo",
          none_patch[clock.DUE] is None and none_patch[clock.DUE2] is None)
    check("keadaan SLA tahap tanpa SLA = 'none'",
          clock.state_of({clock.SLA: None}) == "none")
    check("lewat 2× SLA terdeteksi",
          clock.state_of({clock.SLA: 48, clock.DUE: "2020-01-01T00:00:00+00:00",
                          clock.DUE2: "2020-01-02T00:00:00+00:00"}) == "over2")

    head("A3. reconcile() mengisi jam tahap dari bukti tercatat (idempoten)")
    victims = await db.leads.find({"org_id": ORG_ID}, {"_id": 0, "id": 1}).limit(3).to_list(3)
    await db.leads.update_many({"id": {"$in": [v["id"] for v in victims]}},
                              {"$unset": {f: "" for f in clock.CLOCK_FIELDS}})
    first = await clock.reconcile("lead", org_id=ORG_ID)
    again = await clock.reconcile("lead", org_id=ORG_ID)
    check("baris tanpa jam tahap terisi", first["lead"] >= 3, f"{first['lead']} baris")
    check("jalan kedua tidak menyentuh apa pun (idempoten)", again["lead"] == 0,
          f"{again['lead']} baris")
    sample = await db.leads.find_one({"id": victims[0]["id"]}, {"_id": 0})
    check("jam tahap = tahap sekarang", sample.get(clock.CLOCK_STAGE) == sample.get("stage"))
    check("asal bukti dicatat terus terang", bool(sample.get(clock.CLOCK_SRC)),
          sample.get(clock.CLOCK_SRC))
    missing = await db.leads.count_documents({"org_id": ORG_ID, clock.ENTERED: None})
    check("tidak ada lead tanpa stage_entered_at", missing == 0, f"{missing} lead")

    head("A4. Transisi tahap NYATA menulis jam tahap sesuai kebijakan")
    lead = await db.leads.find_one({"org_id": ORG_ID, "stage": "acquisition"}, {"_id": 0})
    if not lead:
        lead = await db.leads.find_one({"org_id": ORG_ID}, {"_id": 0})
    before = lead.get(clock.ENTERED)
    moved = await lc.record(lead, "nurturing", actor="poc@sipro.co.id",
                            reason="POC 41 transisi", source="poc")
    check("stage_entered_at berubah saat pindah tahap",
          moved.get(clock.ENTERED) and moved[clock.ENTERED] != before,
          f"{before} → {moved.get(clock.ENTERED)}")
    check("SLA efektif ikut tersimpan pada baris", moved.get(clock.SLA) == 12,
          f"{moved.get(clock.SLA)} jam (kebijakan diubah di A1)")
    want_due = clock.clock_patch("nurturing", moved[clock.ENTERED], 12)[clock.DUE]
    check("stage_due_at = masuk + SLA kebijakan", moved.get(clock.DUE) == want_due,
          moved.get(clock.DUE))

    head("A5. 'Lewat SLA' bisa di-QUERY (bukan loop Python di setiap request)")
    query = clock.apply_sla_filter({"org_id": ORG_ID}, "lead", "over")
    db_ids = {d["id"] for d in await db.leads.find(query, {"_id": 0, "id": 1}).to_list(5000)}
    rows = await db.leads.find({"org_id": ORG_ID}, {"_id": 0}).to_list(5000)
    await clock.attach(rows, "lead")
    truth = {r["id"] for r in rows if r["sla_state"] in ("over", "over2")}
    check("hasil query = hitungan Python", db_ids == truth,
          f"query {len(db_ids)} vs hitung {len(truth)}")
    bad = clock.apply_sla_filter({"org_id": ORG_ID}, "lead", "ngawur")
    check("filter tak dikenal → hasil kosong (tidak diabaikan diam-diam)",
          bad.get("id") == {"$in": []})

    head("A6. resync() memberlakukan kebijakan BARU ke baris yang sudah ada")
    await cfg.set_value("lead.sla_hours", {**pol, "nurturing": 6}, actor="poc",
                        reason="POC 41: bukti resync")
    res = await clock.resync("lead", org_id=ORG_ID)
    fresh = await db.leads.find_one({"id": moved["id"]}, {"_id": 0})
    check("baris ikut disegarkan", res["lead"]["resynced"] >= 1, f"{res['lead']}")
    check("SLA pada baris = kebijakan terbaru", fresh.get(clock.SLA) == 6,
          f"{fresh.get(clock.SLA)} jam")
    check("jatuh tempo dihitung ulang",
          fresh.get(clock.DUE) == clock.clock_patch("nurturing", fresh[clock.ENTERED], 6)[clock.DUE])
    await cfg.reset("lead.sla_hours", actor="poc", org_id=ORG_ID)
    await clock.resync("lead", org_id=ORG_ID)
    back = await clock.policy("lead")
    check("kebijakan kembali ke bawaan setelah reset", clock.sla_for(back, "nurturing") == 48,
          f"{clock.sla_for(back, 'nurturing')} jam")

    head("A7. Laporan umur tahap = agregasi database (bukan hitung ulang per baris)")
    report = await clock.aging_report("lead", org_id=ORG_ID)
    total_db = await db.leads.count_documents({"org_id": ORG_ID})
    check("total laporan = jumlah lead", report["totals"]["count"] == total_db,
          f"{report['totals']['count']} vs {total_db}")
    for row in report["rows"][:3]:
        n = await db.leads.count_documents({"org_id": ORG_ID, "stage": row["stage"]})
        check(f"jumlah tahap '{row['stage']}' cocok", row["count"] == n, f"{row['count']} vs {n}")
        check(f"tautan drill tahap '{row['stage']}' terbentuk backend",
              row["drill"].startswith("/leads?stage="), row["drill"])
    over_q = clock.apply_sla_filter({"org_id": ORG_ID}, "lead", "over")
    check("angka 'lewat SLA' laporan = hasil filter daftar",
          report["totals"]["over_sla"] == await db.leads.count_documents(over_q),
          f"{report['totals']['over_sla']}")
    other = await clock.aging_report("task", org_id=ORG_ID)
    check("laporan entitas lain (tugas) juga jalan",
          other["totals"]["count"] == await db.tasks.count_documents({"org_id": ORG_ID}),
          f"{other['totals']['count']} tugas")


# ------------------------------------------------------------------ B. Fase 42
BAD_RULES = [
    ("split tidak 100%", {"basis": "percent_price", "value": 2,
                          "splits": [{"trigger": "ppjb_signed", "pct": 40}]}),
    ("tier tumpang tindih", {"basis": "tier_volume", "trigger": "ppjb_signed",
                             "tiers": [{"min": 0, "max": 3, "value": 1, "mode": "percent"},
                                       {"min": 2, "max": None, "value": 2, "mode": "percent"}]}),
    ("tier bolong", {"basis": "tier_volume", "trigger": "ppjb_signed",
                     "tiers": [{"min": 0, "max": 2, "value": 1, "mode": "percent"},
                               {"min": 5, "max": None, "value": 2, "mode": "percent"}]}),
    ("persen di luar 0–100", {"basis": "percent_price", "value": 140,
                              "trigger": "ppjb_signed"}),
    ("tipe unit tanpa nominal", {"basis": "fixed_per_unit_type", "by_unit_type": {},
                                "trigger": "ppjb_signed"}),
    ("pemicu tidak dikenal", {"basis": "fixed_per_deal", "value": 1000,
                             "trigger": "tanda_tangan_kepala_desa"}),
    ("tarif PPh liar", {"basis": "fixed_per_deal", "value": 1000, "trigger": "ppjb_signed",
                       "tax": {"pph_type": "pph23", "rate": 250}}),
    ("cakupan tidak dikenal", {"basis": "fixed_per_deal", "value": 1000,
                              "trigger": "ppjb_signed", "scope": {"kelurahan": "X"}}),
    ("tanpa pemicu", {"basis": "fixed_per_deal", "value": 1000}),
]


def section_b_pure():
    head("B1. Aturan tidak sah DITOLAK sebelum tersimpan")
    for name, rule in BAD_RULES:
        try:
            pfee.validate_rule(rule)
            check(f"tolak: {name}", False, "aturan cacat malah diterima")
        except ValueError as exc:
            check(f"tolak: {name}", True, str(exc)[:60])
    ok_rule = {"basis": "percent_price", "value": 2, "trigger": "ppjb_signed",
               "tax": {"pph_type": "pph23", "rate": 2}}
    check("aturan sah diterima", pfee.validate_rule(ok_rule) is not None)

    head("B2. Pemilihan aturan: paling spesifik menang, seri DITOLAK")
    generic = {"code": "PFR-GEN", "basis": "percent_price", "value": 2,
               "trigger": "ppjb_signed", "status": "active"}
    per_partner = {**generic, "code": "PFR-MITRA", "partner_id": "P1", "value": 3}
    per_type = {**generic, "code": "PFR-TIPE", "scope": {"unit_type": "TIPE-45-90"}, "value": 4}
    ctx = {"partner_id": "P1", "trigger": "ppjb_signed", "unit_type": "TIPE-45-90"}
    chosen, why = pfee.select([generic, per_partner, per_type], ctx)
    check("aturan khusus mitra menang atas umum", chosen and chosen["code"] == "PFR-MITRA",
          (chosen or {}).get("code") or why)
    chosen, why = pfee.select([generic, per_type], ctx)
    check("aturan per tipe unit menang atas umum", chosen and chosen["code"] == "PFR-TIPE",
          (chosen or {}).get("code") or why)
    twin = {**per_partner, "code": "PFR-KEMBAR"}
    chosen, why = pfee.select([per_partner, twin], ctx)
    check("dua aturan sama spesifik → ditolak dengan pesan", chosen is None and "bentrok" in (why or ""),
          why)
    chosen, why = pfee.select([{**generic, "valid_to": "2020-01-01"}], ctx)
    check("aturan kedaluwarsa tidak dipakai", chosen is None, why)
    chosen, why = pfee.select([], ctx)
    check("tanpa aturan → fee ditolak (INV-09)", chosen is None and "Tidak ada aturan" in (why or ""),
          (why or "")[:60])

    head("B3. Tujuh dasar fee = hitungan tangan")
    deal = {"price": 850_000_000, "discount": 50_000_000}
    unit = {"unit_type_code": "TIPE-45-90"}
    cases = [
        ("persen harga bruto", {"basis": "percent_price", "value": 2}, {}, 17_000_000),
        ("persen setelah diskon", {"basis": "percent_price", "value": 2,
                                  "price_base": "after_discount"}, {}, 16_000_000),
        ("nominal per transaksi", {"basis": "fixed_per_deal", "value": 3_000_000}, {},
         3_000_000),
        ("nominal per tipe unit", {"basis": "fixed_per_unit_type",
                                  "by_unit_type": {"TIPE-45-90": 2_500_000}}, {}, 2_500_000),
        ("berjenjang per jumlah (tier 2)", {"basis": "tier_volume", "tiers": [
            {"min": 0, "max": 2, "value": 1.5, "mode": "percent"},
            {"min": 3, "max": None, "value": 2.5, "mode": "percent"}]},
         {"closings_count": 4}, 21_250_000),
        ("berjenjang per nilai (nominal)", {"basis": "tier_value", "tiers": [
            {"min": 0, "max": 1_000_000_000, "value": 5_000_000, "mode": "fixed"},
            {"min": 1_000_000_001, "max": None, "value": 9_000_000, "mode": "fixed"}]},
         {"closings_value": 2_500_000_000}, 9_000_000),
        ("per lead terkualifikasi", {"basis": "per_lead_qualified", "value": 150_000},
         {"qualified_leads": 7}, 1_050_000),
        ("gabungan (per lead + persen)", {"basis": "hybrid", "components": [
            {"basis": "per_lead_qualified", "value": 150_000},
            {"basis": "percent_price", "value": 1}]},
         {"qualified_leads": 2}, 300_000 + 8_500_000),
    ]
    for name, rule, extra, want in cases:
        got = pfee.evaluate(rule, {"deal": deal, "unit": unit, **extra})
        check(f"{name}", got["gross"] == want, f"{got['gross']:,} (harap {want:,})")
    try:
        pfee.evaluate({"basis": "fixed_per_unit_type", "by_unit_type": {"TIPE-36-60": 1}},
                      {"deal": deal, "unit": unit})
        check("tipe unit di luar tabel ditolak", False)
    except ValueError as exc:
        check("tipe unit di luar tabel ditolak", True, str(exc)[:60])
    try:
        pfee.evaluate({"basis": "tier_volume", "tiers": [{"min": 5, "max": None, "value": 1,
                                                        "mode": "fixed"}]},
                      {"deal": deal, "closings_count": 1})
        check("nilai di luar semua tier ditolak", False)
    except ValueError as exc:
        check("nilai di luar semua tier ditolak", True, str(exc)[:60])

    head("B4. PPh 21/23 + gross-up")
    rates = {"pph21": 2.5, "pph23": 2}
    ind = pfee.tax_of(10_000_000, {"tax": {}}, {"entity_type": "individual"}, rates)
    check("perorangan → PPh 21 2,5%", ind["pph_type"] == "pph21" and ind["pph_amount"] == 250_000,
          f"{ind}")
    comp = pfee.tax_of(10_000_000, {"tax": {}}, {"entity_type": "company"}, rates)
    check("badan usaha → PPh 23 2%", comp["pph_type"] == "pph23" and comp["pph_amount"] == 200_000)
    check("beban = netto + PPh", comp["expense"] == comp["payout"] + comp["pph_amount"])
    gup = pfee.tax_of(10_000_000, {"tax": {"pph_type": "pph23", "rate": 2, "gross_up": True}},
                      {}, rates)
    check("gross-up: mitra terima utuh", gup["payout"] == 10_000_000, f"{gup}")
    check("gross-up: beban naik & tetap seimbang",
          gup["expense"] == gup["payout"] + gup["pph_amount"] and gup["expense"] > 10_000_000,
          f"beban {gup['expense']:,}")
    none_tax = pfee.tax_of(5_000_000, {"tax": {"pph_type": "none"}}, {}, rates)
    check("tanpa PPh → tidak ada potongan", none_tax["pph_amount"] == 0)

    head("B5. Porsi pembayaran bertahap per pemicu")
    staged = {"basis": "percent_price", "value": 2,
              "splits": [{"trigger": "ppjb_signed", "pct": 50},
                         {"trigger": "ajb_signed", "pct": 50}]}
    check("porsi PPJB 50%", pfee.split_pct(staged, "ppjb_signed") == 50)
    check("porsi AJB 50%", pfee.split_pct(staged, "ajb_signed") == 50)
    check("pemicu di luar daftar = 0%", pfee.split_pct(staged, "full_payment") == 0)
    single = {"basis": "fixed_per_deal", "value": 1, "trigger": "ppjb_signed"}
    check("tanpa daftar bertahap = 100% di pemicu utama",
          pfee.split_pct(single, "ppjb_signed") == 100 and pfee.split_pct(single, "ajb_signed") == 0)


async def section_b_live():
    head("B6. END-TO-END lewat API: reservasi → booking → PPJB menerbitkan fee dari aturan")
    manager = login("manager@sipro.co.id")
    finance = login("finance@sipro.co.id")
    partner = await db.agents.find_one({"org_id": ORG_ID, "partner_kind": "referral_pembeli"},
                                      {"_id": 0})
    if not partner:
        partner = await db.agents.find_one({"org_id": ORG_ID, "status": "active"}, {"_id": 0})
    if not check("ada mitra aktif untuk diuji", bool(partner)):
        return
    rule = await db.partner_fee_rules.find_one({"org_id": ORG_ID, "poc": True}, {"_id": 0})
    if not rule:
        rule = await pfee.create_rule({
            "name": "POC 41/42 — 2% harga, bayar 30% SPR + 70% PPJB",
            "partner_id": partner["id"], "basis": "percent_price", "value": 2,
            "price_base": "gross", "tax": {"pph_type": "pph23", "gross_up": False},
            "splits": [{"trigger": "spr_signed", "pct": 30},
                       {"trigger": "ppjb_signed", "pct": 70}],
        }, actor="poc", org_id=ORG_ID)
        await db.partner_fee_rules.update_one({"id": rule["id"]}, {"$set": {"poc": True}})
    lead = await db.leads.find_one(
        {"org_id": ORG_ID, "stage": {"$in": ["acquisition", "nurturing", "appointment"]}},
        {"_id": 0})
    await db.leads.update_one({"id": lead["id"]}, {"$set": {
        "source": "partner", "partner_id": partner["id"], "partner_attributed_at": now_iso(),
        "updated_at": now_iso()}})
    # Bisa dijalankan berulang: transaksi POC sebelumnya DIPAKAI ULANG (tidak menumpuk
    # reservasi baru setiap kali skrip dijalankan).
    reused = await db.deals.find_one({"org_id": ORG_ID, "notes": MARKER,
                                      "legal_stage": "ppjb"}, {"_id": 0})
    if reused:
        deal = reused
        lead = await db.leads.find_one({"id": deal["lead_id"]}, {"_id": 0})
        partner = await db.agents.find_one({"id": lead.get("partner_id")}, {"_id": 0}) or partner
        print("  [INFO] memakai ulang transaksi POC sebelumnya "
              f"(deal {deal['id'][:8]}, unit {deal.get('unit_id', '')[:8]}) — "
              "bukti alur tetap diperiksa")
    else:
        unit = await db.units.find_one({"org_id": ORG_ID, "status": "available"}, {"_id": 0})
        if not check("ada unit tersedia untuk reservasi", bool(unit)):
            return
        r = requests.post(f"{BASE}/deals/reserve", headers=manager, timeout=30, json={
            "lead_id": lead["id"], "unit_id": unit["id"], "booking_fee": 1_000_000,
            "notes": MARKER})
        if not check("POST /deals/reserve = 200", r.status_code == 200, r.text[:200]):
            return
        deal = r.json()["data"]
    price = int(deal["price"])
    gross_full = round(price * 2 / 100)
    want_spr = round(gross_full * 30 / 100)
    want_ppjb = round(gross_full * 70 / 100)

    async def wait_fee(trigger, timeout=30):
        for _ in range(timeout):
            fee = await db.marketing_fees.find_one(
                {"org_id": ORG_ID, "deal_id": deal["id"], "trigger": trigger}, {"_id": 0})
            if fee:
                return fee
            await asyncio.sleep(1)
        return None

    spr_fee = await wait_fee("spr_signed")
    if check("event deal.reserved menerbitkan fee SPR otomatis", bool(spr_fee)):
        check("nominal fee SPR = 30% dari 2% harga", spr_fee["amount_gross"] == want_spr,
              f"{spr_fee['amount_gross']:,} (harap {want_spr:,})")
        check("PPh 23 dipotong dari fee", spr_fee["pph_amount"] > 0
              and spr_fee["amount_net"] == spr_fee["amount_gross"] - spr_fee["pph_amount"],
              f"PPh {spr_fee['pph_amount']:,}")
        check("fee menyimpan aturan penerbitnya", spr_fee.get("rule_id") == rule["id"]
              and spr_fee.get("rule_basis") == "percent_price", spr_fee.get("rule_code"))
        check("fee menunggu persetujuan finance",
              spr_fee["status"] == "submitted" if not reused
              else spr_fee["status"] in ("submitted", "approved", "paid"),
              f"status {spr_fee['status']}" + (" (sudah disetujui pada jalan sebelumnya)"
                                              if reused else ""))

    head("A4b. Jam tahap lead ikut terisi oleh alur nyata (reservasi → tahap booking)")
    fresh_lead = await db.leads.find_one({"id": lead["id"]}, {"_id": 0})
    pol = await clock.policy("lead")
    check("lead pindah ke tahap booking", fresh_lead.get("stage") == "booking",
          fresh_lead.get("stage"))
    check("stage_entered_at tersimpan oleh transisi nyata",
          bool(fresh_lead.get(clock.ENTERED)) and fresh_lead.get(clock.CLOCK_STAGE) == "booking")
    check("SLA booking dari Pusat Konfigurasi menempel di baris",
          fresh_lead.get(clock.SLA) == clock.sla_for(pol, "booking"),
          f"{fresh_lead.get(clock.SLA)} jam")

    if not reused:
        r = requests.post(f"{BASE}/deals/{deal['id']}/book", headers=manager,
                          json={"note": MARKER}, timeout=30)
        check("POST /deals/{id}/book = 200", r.status_code == 200, r.text[:150])
        await asyncio.sleep(2)
    bf_fee = await db.marketing_fees.find_one(
        {"org_id": ORG_ID, "deal_id": deal["id"], "trigger": "booking_fee_verified"}, {"_id": 0})
    check("pemicu berporsi 0% TIDAK menerbitkan fee", bf_fee is None,
          "tidak ada tagihan booking_fee_verified (benar: aturan hanya SPR & PPJB)")

    if not reused:
        r = requests.post(f"{BASE}/deals/{deal['id']}/ppjb", headers=manager, timeout=30,
                          json={"note": MARKER})
        check("POST /deals/{id}/ppjb = 200", r.status_code == 200, r.text[:150])
    ppjb_fee = await wait_fee("ppjb_signed")
    if check("event deal.ppjb menerbitkan fee tahap kedua", bool(ppjb_fee)):
        check("nominal fee PPJB = 70% dari 2% harga", ppjb_fee["amount_gross"] == want_ppjb,
              f"{ppjb_fee['amount_gross']:,} (harap {want_ppjb:,})")

    head("B7. Idempoten: pemicu yang sama tidak menerbitkan tagihan kedua")
    deal_doc = await db.deals.find_one({"id": deal["id"]}, {"_id": 0})
    again = await pengine.create_fee_for_trigger(deal_doc, "ppjb_signed", actor="poc",
                                                org_id=ORG_ID)
    count = await db.marketing_fees.count_documents(
        {"org_id": ORG_ID, "deal_id": deal["id"], "trigger": "ppjb_signed"})
    check("panggilan kedua ditolak dengan alasan", not again["created"], again.get("reason"))
    check("tetap satu tagihan untuk pemicu itu", count == 1, f"{count} tagihan")

    head("B8. Persetujuan finance menjaga invarian 2-1500 = Σ (netto − terbayar)")
    if spr_fee and spr_fee.get("status") == "submitted":
        r = requests.post(f"{BASE}/marketing/fees/{spr_fee['id']}/approve", headers=finance,
                          json={"note": "POC 42"}, timeout=30)
        check("approve fee = 200", r.status_code == 200, r.text[:200])
    fees = await db.marketing_fees.find({"org_id": ORG_ID}, {"_id": 0}).to_list(2000)
    payable = sum(int(f["amount_net"]) - int(f.get("paid_amount", 0)) for f in fees
                  if f["status"] in ("approved", "paid"))
    balance = 0
    async for je in db.journal_entries.find({}, {"_id": 0, "lines": 1}):
        for line in je.get("lines") or []:
            if line.get("account_code") == "2-1500":
                balance += int(line.get("credit", 0) or 0) - int(line.get("debit", 0) or 0)
    check("saldo GL 2-1500 = Σ fee disetujui belum dibayar", balance == payable,
          f"GL {balance:,} vs fee {payable:,}")

    head("B9. Pagar wajar fee (% harga) menandai butuh persetujuan owner")
    greedy = await pfee.create_rule({
        "name": "POC — fee 12% (uji pagar wajar)", "partner_id": partner["id"],
        "basis": "percent_price", "value": 12, "trigger": "full_payment",
        "tax": {"pph_type": "pph23", "gross_up": False}}, actor="poc", org_id=ORG_ID)
    calc = await pengine.compute(deal_doc, "full_payment", org_id=ORG_ID, partner=partner)
    check("fee di atas pagar ditandai butuh persetujuan owner",
          calc.get("ok") and calc["needs_owner_approval"],
          f"{calc.get('fee_pct_of_price')}% vs pagar {calc.get('guard_pct')}%")
    await db.partner_fee_rules.delete_one({"id": greedy["id"]})

    head("B10. Atribusi lead: dua mitra mengklaim nomor yang sama")
    other_partner = await db.agents.find_one(
        {"org_id": ORG_ID, "status": "active", "id": {"$ne": partner["id"]}}, {"_id": 0})
    got = await pengine.attribute(partner_id=other_partner["id"], phone=fresh_lead["phone"],
                                 org_id=ORG_ID)
    check("first-touch: mitra pertama tetap pemilik lead", got["partner_id"] == partner["id"],
          f"{got['model']}")
    check("sengketa atribusi tercatat untuk ditinjau", bool(got["conflict"]),
          (got.get("conflict") or {}).get("status"))
    same = await pengine.attribute(partner_id=partner["id"], phone=fresh_lead["phone"],
                                  org_id=ORG_ID)
    check("klaim oleh mitra yang sama bukan sengketa", same["conflict"] is None)

    head("B11. Statistik mitra dihitung dari data (bukan diketik)")
    stats = await pengine.refresh_stats(partner["id"], org_id=ORG_ID)
    leads_n = await db.leads.count_documents({"org_id": ORG_ID, "partner_id": partner["id"]})
    check("jumlah lead mitra = isi database", stats["leads"] == leads_n,
          f"{stats['leads']} lead")
    check("fee outstanding = total − terbayar",
          stats["fee_outstanding"] == stats["fee_total"] - stats["fee_paid"],
          f"Rp {stats['fee_outstanding']:,}")
    # Aturan POC dimatikan supaya kebijakan demo (aturan seed) yang berlaku setelah ini.
    await db.partner_fee_rules.update_one({"id": rule["id"]},
                                         {"$set": {"status": "inactive"}})


async def main():
    print("=" * 78)
    print("POC FASE 41 (jam tahap) + FASE 42 (mesin aturan fee mitra)")
    print("=" * 78)
    await section_a()
    section_b_pure()
    await section_b_live()
    print("\n" + "=" * 78)
    print(f"HASIL: {passed} PASS / {failed} FAIL")
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
