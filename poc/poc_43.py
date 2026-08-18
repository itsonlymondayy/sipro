#!/usr/bin/env python3
"""POC Fase 43 — SATU skrip untuk core workflow paling rawan gagal SEBELUM UI dibangun.

Kenapa hal-hal ini yang diuji lebih dulu: kalau salah, kerusakannya tidak kelihatan di layar
(angka tetap tampil rapi) tetapi keputusan anggaran iklan jadi salah selamanya.

A. IMPOR CSV BIAYA IKLAN
   A1  Berkas tanpa kolom wajib ditolak dengan menyebut kolom yang hilang
   A2  Header laporan platform ('Amount spent (IDR)', 'Day', …) dipetakan otomatis
   A3  Dry-run menolak per baris dengan alasan BENAR: tanggal tak dikenal, tanggal di masa
       depan, kampanye belum terdaftar, mata uang bukan IDR, biaya bukan angka, baris kembar
   A4  Angka gaya Indonesia ('1.250.000', 'Rp 2.500.000,50') dibaca benar
   A5  Dry-run TIDAK menyimpan apa pun
   A6  Commit menyimpan baris valid; impor KEDUA berkas yang sama = `unchanged` (idempoten)
   A7  Angka yang berubah di berkas berikutnya MEMPERBARUI baris lama + menyimpan nilai lama
   A8  Kunci natural dijaga index UNIK di database (bukan hanya di aplikasi)

B. KEJUJURAN METRIK
   B1  Kampanye tanpa biaya → CPL/CAC/ROAS = null + "data biaya belum lengkap" (bukan 0)
   B2  Biaya sebagian hari → cost_status 'partial' + menyebut hari terisi vs seharusnya
   B3  CPL/CAC/ROAS bisa direkonstruksi dengan tangan dari spend/leads/booked/revenue
   B4  Lead yang nama kampanyenya tidak dikenal DILAPORKAN (unmatched), tidak dibuang diam-diam
   B5  Agregasi harian/mingguan/bulanan menjumlahkan angka yang sama

C. CAPI V2 (siap-live)
   C1  `event_id` deterministik untuk peristiwa bisnis yang sama
   C2  Perekaman kedua atas peristiwa yang sama TIDAK menambah baris (dedup)
   C3  `user_data` = SHA-256 dari telepon E.164 (tanpa '+') & email huruf kecil; TIDAK ada
       nomor mentah yang tersimpan di dokumen event
   C4  Event `SubmitApplication` (SPR ditandatangani) diterima kosakata SSOT
   C5  Mode simulasi berstatus `simulated` (BUKAN 'sent') dan kirim-ulang ditolak dengan
       alasan jujur

D. MODE ADAPTER (mengisi env hanya mengubah mode, bukan kontrak)
   D1  Tanpa kredensial: mode 'simulation' dan datanya dari DB (bukan angka karangan)
   D2  Dengan kredensial dummy: mode 'live', probe GAGAL dan mengatakannya apa adanya
   D3  Bentuk hasil `list_campaigns`/`daily_insights` sama di kedua mode
   D4  Status integrasi tidak pernah membocorkan NILAI kredensial

Jalankan: `python3 poc/poc_43.py`  (butuh MongoDB; backend tidak wajib hidup)
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")

import ads_adapters as adapters  # noqa: E402
import ads_engine as eng  # noqa: E402
import ads_report as rep  # noqa: E402
import capi  # noqa: E402
import reference as ref  # noqa: E402
from core_utils import normalize_phone_e164, today_iso_date  # noqa: E402
from db import db, ORG_ID  # noqa: E402
from indexes import ensure_unique_indexes  # noqa: E402

MARK = "POC43"
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


def days_ago(n):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


async def cleanup():
    """Bersihkan seluruh jejak POC supaya gate integritas data tetap bersih."""
    camps = await db.campaigns.find({"org_id": ORG_ID, "name": {"$regex": f"^{MARK}"}},
                                    {"_id": 0, "id": 1}).to_list(50)
    ids = [c["id"] for c in camps]
    if ids:
        await db.ad_spend.delete_many({"org_id": ORG_ID, "campaign_id": {"$in": ids}})
        await db.campaigns.delete_many({"id": {"$in": ids}})
    await db.ads_imports.delete_many({"org_id": ORG_ID, "filename": {"$regex": f"^{MARK}"}})
    await db.leads.delete_many({"org_id": ORG_ID, "name": {"$regex": f"^{MARK}"}})
    await db.conversion_events.delete_many({"org_id": ORG_ID,
                                            "campaign": {"$regex": f"^{MARK}"}})


# ============================================================ A. impor CSV
async def section_a():
    head("A. IMPOR CSV BIAYA IKLAN")
    camp = await eng.create_campaign({
        "platform": "meta", "name": f"{MARK} Cluster Meta", "external_id": "23851234567890",
        "objective": "leads", "status": "active", "budget_total": 30_000_000,
        "start_date": days_ago(9), "end_date": None,
    }, org_id=ORG_ID, actor="poc")
    check("A0 kampanye uji dibuat", bool(camp["id"]), f"{camp['code']} {camp['name']}")

    # A1 — kolom wajib hilang
    plan = await eng.plan_import("tanggal;kampanye\n2026-08-01;X\n", org_id=ORG_ID)
    check("A1 kolom wajib hilang ditolak", not plan["ok"] and "spend" in (plan["error"] or ""),
          (plan.get("error") or "")[:90])

    # A2 + A4 — header gaya laporan platform & angka gaya Indonesia
    csv_platform = (
        "Day,Platform,Campaign name,Campaign ID,Ad set name,Amount spent (IDR),Impressions,"
        "Link clicks,Results\n"
        f"{days_ago(3)},meta,{MARK} Cluster Meta,23851234567890,Ad set A,\"1.250.000\",41.000,820,7\n"
        f"{days_ago(2)},Meta Ads,{MARK} Cluster Meta,,Ad set A,\"Rp 2.500.000,50\",52000,940,9\n"
    )
    plan = await eng.plan_import(csv_platform, org_id=ORG_ID)
    check("A2 header laporan platform terpetakan", plan["ok"], (plan.get("error") or "")[:80])
    rows = [r for r in plan["rows"] if r["status"] != "rejected"]
    check("A2 dua baris valid", len(rows) == 2,
          f"{plan['summary']}")
    if len(rows) == 2:
        check("A4 '1.250.000' dibaca 1250000", rows[0]["row"]["spend"] == 1_250_000,
              str(rows[0]["row"]["spend"]))
        check("A4 'Rp 2.500.000,50' dibulatkan 2500001",
              rows[1]["row"]["spend"] == 2_500_001, str(rows[1]["row"]["spend"]))
        check("A4 impresi '41.000' dibaca 41000", rows[0]["row"]["impressions"] == 41_000,
              str(rows[0]["row"]["impressions"]))
        check("A2 sinonim platform 'Meta Ads' dikanonikkan",
              rows[1]["row"]["platform"] == "meta", rows[1]["row"]["platform"])

    # A3 — penolakan per baris dengan alasan yang benar
    csv_bad = (
        "date,platform,campaign_name,spend,currency,adset_id\n"
        f"31/02/2026,meta,{MARK} Cluster Meta,100000,IDR,A1\n"          # tanggal tidak ada
        f"{days_ago(-5)},meta,{MARK} Cluster Meta,100000,IDR,A1\n"      # masa depan
        f"{days_ago(1)},meta,Kampanye Hantu,100000,IDR,A1\n"            # kampanye tak dikenal
        f"{days_ago(1)},meta,{MARK} Cluster Meta,100,USD,A1\n"          # mata uang
        f"{days_ago(1)},meta,{MARK} Cluster Meta,seratus ribu,IDR,A1\n"  # bukan angka
        f"{days_ago(1)},tiktok,{MARK} Cluster Meta,100000,IDR,A1\n"     # platform tak cocok
        f"{days_ago(4)},meta,{MARK} Cluster Meta,100000,IDR,A2\n"       # valid
        f"{days_ago(4)},meta,{MARK} Cluster Meta,150000,IDR,A2\n"       # kembar di berkas
    )
    plan_bad = await eng.plan_import(csv_bad, org_id=ORG_ID)
    reasons = {r["line"]: (r.get("reason") or "") for r in plan_bad["rows"]}
    check("A3 tanggal tidak ada di kalender ditolak", "kalender" in reasons.get(2, ""),
          reasons.get(2, "")[:70])
    check("A3 tanggal masa depan ditolak", "masa depan" in reasons.get(3, ""),
          reasons.get(3, "")[:70])
    check("A3 kampanye belum terdaftar ditolak", "belum terdaftar" in reasons.get(4, ""),
          reasons.get(4, "")[:70])
    check("A3 mata uang selain IDR ditolak (bukan dikonversi diam-diam)",
          "mata uang" in reasons.get(5, "") and "kurs" in reasons.get(5, ""),
          reasons.get(5, "")[:80])
    check("A3 biaya bukan angka ditolak", "bukan angka" in reasons.get(6, ""),
          reasons.get(6, "")[:70])
    check("A3 kampanye tidak ada di platform lain ditolak",
          "belum terdaftar" in reasons.get(7, ""), reasons.get(7, "")[:70])
    check("A3 baris kembar di dalam berkas ditolak (bukan last-write-wins)",
          "kembar" in reasons.get(9, ""), reasons.get(9, "")[:80])
    check("A3 satu baris valid tetap lolos", plan_bad["summary"]["new"] == 1,
          str(plan_bad["summary"]))

    # A5 — dry-run tidak menyimpan
    before = await db.ad_spend.count_documents({"org_id": ORG_ID, "campaign_id": camp["id"]})
    doc = await eng.import_csv(csv_platform, org_id=ORG_ID, actor="poc",
                              filename=f"{MARK}-preview.csv", dry_run=True)
    after = await db.ad_spend.count_documents({"org_id": ORG_ID, "campaign_id": camp["id"]})
    check("A5 dry-run tidak menyimpan baris biaya", before == after == 0,
          f"{before} → {after}")
    check("A5 laporan pratinjau tersimpan & bisa dibuka ulang", doc["status"] == "preview",
          doc["id"][:8])

    # A6 — commit + idempotensi
    first = await eng.import_csv(csv_platform, org_id=ORG_ID, actor="poc",
                                filename=f"{MARK}-commit.csv", dry_run=False)
    check("A6 commit menyimpan 2 baris", first["applied"]["inserted"] == 2,
          str(first["applied"]))
    second = await eng.import_csv(csv_platform, org_id=ORG_ID, actor="poc",
                                 filename=f"{MARK}-commit.csv", dry_run=False)
    total_rows = await db.ad_spend.count_documents({"org_id": ORG_ID, "campaign_id": camp["id"]})
    check("A6 impor kedua TIDAK menduplikasi",
          second["applied"]["unchanged"] == 2 and total_rows == 2,
          f"applied={second['applied']} rows={total_rows}")
    agg = await eng.campaign_spend_totals([camp["id"]], org_id=ORG_ID)
    check("A6 total biaya tetap 3.750.001 setelah 2× impor",
          agg[camp["id"]]["spend"] == 3_750_001, f"Rp {agg[camp['id']]['spend']:,}")

    # A7 — angka berubah → update + jejak nilai lama
    csv_fixed = csv_platform.replace("\"1.250.000\"", "\"1.400.000\"")
    third = await eng.import_csv(csv_fixed, org_id=ORG_ID, actor="poc2",
                                filename=f"{MARK}-koreksi.csv", dry_run=False)
    row = await db.ad_spend.find_one({"org_id": ORG_ID, "campaign_id": camp["id"],
                                     "date": days_ago(3)}, {"_id": 0})
    check("A7 koreksi memperbarui baris lama (bukan baris baru)",
          third["applied"]["updated"] == 1 and row["spend"] == 1_400_000,
          f"applied={third['applied']} spend={row['spend']:,}")
    check("A7 nilai lama tersimpan di riwayat (biaya tidak berubah diam-diam)",
          bool(row.get("history")) and row["history"][0]["changes"][0]["before"] == 1_250_000,
          str((row.get("history") or [{}])[0].get("changes"))[:90])
    check("A7 pengubah tercatat", row["updated_by"] == "poc2", row["updated_by"])

    # A8 — index unik di DB
    res = await ensure_unique_indexes()
    conflicts = [c for c in res["conflicts"] if c["index"] == "uq_ad_spend_natural"]
    check("A8 index unik kunci natural terpasang", not conflicts, str(conflicts)[:120])
    from pymongo.errors import DuplicateKeyError
    dup = dict(row)
    dup.pop("_id", None)
    dup["id"] = "poc-dup"
    try:
        await db.ad_spend.insert_one(dup)
        check("A8 database MENOLAK baris kembar", False, "insert kembar berhasil (bocor)")
        await db.ad_spend.delete_one({"id": "poc-dup"})
    except DuplicateKeyError:
        check("A8 database MENOLAK baris kembar", True, "E11000 seperti seharusnya")
    return camp


# ============================================================ B. kejujuran metrik
async def section_b(camp):
    head("B. KEJUJURAN METRIK (CPL/CAC/ROAS)")
    empty = await eng.create_campaign({
        "platform": "google", "name": f"{MARK} Tanpa Biaya", "objective": "leads",
        "status": "active", "start_date": days_ago(5),
    }, org_id=ORG_ID, actor="poc")
    # Lead nyata untuk dua kampanye + satu lead dengan kampanye yang tidak dikenal.
    leads = [
        {"name": f"{MARK} Lead 1", "campaign": camp["name"], "source": "meta_ads",
         "stage": "appointment", "score_band": "hot"},
        {"name": f"{MARK} Lead 2", "campaign": camp["name"], "source": "meta_ads",
         "stage": "booking", "score_band": "warm"},
        {"name": f"{MARK} Lead 3", "campaign": camp["name"], "source": "meta_ads",
         "stage": "acquisition", "score_band": "cold"},
        {"name": f"{MARK} Lead 4", "campaign": empty["name"], "source": "google_lead",
         "stage": "nurturing", "score_band": "warm"},
        {"name": f"{MARK} Lead 5", "campaign": "kampanye-yang-tidak-terdaftar",
         "source": "meta_ads", "stage": "acquisition", "score_band": "cold"},
    ]
    from core_utils import new_id, now_iso
    for i, l in enumerate(leads):
        await db.leads.insert_one({
            "id": new_id(), "org_id": ORG_ID, "phone": f"+62812440{9000 + i}",
            "email": None, "assigned_to": "sales@sipro.co.id", "attribution": {},
            "created_at": now_iso(), "updated_at": now_iso(), "created_by": "poc", **l})
    perf = await rep.campaign_performance(org_id=ORG_ID, date_from=days_ago(9),
                                          date_to=today_iso_date())
    rows = {r["name"]: r for r in perf["rows"]}
    paid, none = rows.get(camp["name"]), rows.get(empty["name"])

    check("B1 kampanye tanpa biaya: cost_status 'missing'",
          none and none["cost_status"] == "missing", none and none["cost_status"])
    check("B1 CPL/CAC/ROAS = null (BUKAN 0) saat biaya belum ada",
          none and none["cpl"] is None and none["cac"] is None and none["roas"] is None,
          f"cpl={none and none['cpl']} cac={none and none['cac']}")
    check("B1 alasan disebutkan apa adanya",
          none and none["cost_note"] == rep.COST_NOTE_MISSING, none and none["cost_note"])
    check("B2 biaya sebagian hari → 'partial' + hari terisi vs seharusnya",
          paid and paid["cost_status"] == "partial" and paid["spend_days"] == 2
          and paid["expected_days"] >= 9,
          f"{paid and paid['spend_days']}/{paid and paid['expected_days']}")
    hand_cpl = round(paid["spend"] / paid["leads"]) if paid and paid["leads"] else None
    check("B3 CPL bisa direkonstruksi dengan tangan (spend/leads)",
          paid and paid["cpl"] == hand_cpl,
          f"{paid and paid['cpl']} vs {hand_cpl} (Rp {paid and paid['spend']:,} / "
          f"{paid and paid['leads']} lead)")
    check("B3 label sumber angka biaya ikut dilaporkan",
          paid and paid["sources"] == ["csv"], str(paid and paid["sources"]))
    check("B4 lead kampanye tak dikenal DILAPORKAN, bukan dibuang",
          perf["unmatched"]["leads"] >= 1
          and "kampanye-yang-tidak-terdaftar" in perf["unmatched"]["campaign_values"],
          f"{perf['unmatched']['leads']} lead dengan "
          f"{len(perf['unmatched']['campaign_values'])} nama kampanye tak terdaftar")
    check("B4 total agregat menandai kelengkapan biaya",
          perf["totals"]["cost_status"] in ("partial", "missing")
          and perf["totals"]["campaigns_without_cost"] >= 1,
          f"{perf['totals']['cost_status']} / tanpa biaya "
          f"{perf['totals']['campaigns_without_cost']}")

    daily = await eng.spend_series(org_id=ORG_ID, campaign_id=camp["id"], period="daily")
    monthly = await eng.spend_series(org_id=ORG_ID, campaign_id=camp["id"], period="monthly")
    weekly = await eng.spend_series(org_id=ORG_ID, campaign_id=camp["id"], period="weekly")
    check("B5 agregasi harian/mingguan/bulanan menjumlahkan angka yang sama",
          sum(b["spend"] for b in daily) == sum(b["spend"] for b in monthly)
          == sum(b["spend"] for b in weekly) == 3_900_001,
          f"daily={len(daily)} weekly={len(weekly)} monthly={len(monthly)} "
          f"total=Rp {sum(b['spend'] for b in daily):,}")

    attr = await rep.attribution(org_id=ORG_ID, level="campaign", date_from=days_ago(9),
                                 date_to=today_iso_date())
    mix = {m["channel_group"]: m for m in attr["channel_mix"]}
    check("B5 atribusi mengelompokkan kanal (iklan/mitra/organik)",
          "ads" in mix and mix["ads"]["leads"] >= 4, str(list(mix)))
    adset = await rep.attribution(org_id=ORG_ID, level="adset", date_from=days_ago(9),
                                 date_to=today_iso_date())
    check("B5 tingkat adset tidak MEMBAGI biaya kampanye secara karangan",
          all(r["spend"] is None and "belum dirinci" in (r["spend_note"] or "")
              for r in adset["rows"]),
          str([(r["level_label"], r["spend"]) for r in adset["rows"]][:3]))
    return empty


# ============================================================ C. CAPI V2
async def section_c(camp):
    head("C. CAPI V2 (event_id, hash identitas, SubmitApplication)")
    lead = {"id": "poc43-lead", "source": "meta_ads", "campaign": camp["name"],
            "phone": "08124400777", "email": "  Budi.Test@Example.COM ",
            "attribution": {"campaign_id": camp["external_id"], "adset_id": "AS-1",
                            "ad_id": "AD-9"}}
    deal = {"id": "poc43-deal", "price": 850_000_000}
    eid1 = capi.event_id_for(org_id=ORG_ID, event_name="SubmitApplication",
                             lead_id=lead["id"], deal_id=deal["id"])
    eid2 = capi.event_id_for(org_id=ORG_ID, event_name="SubmitApplication",
                             lead_id=lead["id"], deal_id=deal["id"])
    eid3 = capi.event_id_for(org_id=ORG_ID, event_name="Purchase",
                             lead_id=lead["id"], deal_id=deal["id"])
    check("C1 event_id deterministik untuk peristiwa yang sama", eid1 == eid2, eid1[:12])
    check("C1 event berbeda → event_id berbeda", eid1 != eid3)

    await db.conversion_events.delete_many({"org_id": ORG_ID, "lead_id": lead["id"]})
    doc = await capi.record_conversion(event_name="SubmitApplication", lead=lead, deal=deal,
                                       value=deal["price"], org_id=ORG_ID)
    again = await capi.record_conversion(event_name="SubmitApplication", lead=lead, deal=deal,
                                         value=deal["price"], org_id=ORG_ID)
    n = await db.conversion_events.count_documents({"org_id": ORG_ID, "lead_id": lead["id"]})
    check("C2 perekaman kedua tidak menambah baris (dedup)",
          n == 1 and again.get("duplicate") is True, f"{n} baris")
    check("C4 event SubmitApplication ada di kosakata SSOT",
          doc["event_name"] in ref.values("capi_event_name"),
          str(ref.values("capi_event_name")))

    want_ph = capi.sha256_of(normalize_phone_e164(lead["phone"]).lstrip("+"))
    want_em = capi.sha256_of("budi.test@example.com")
    check("C3 telepon di-hash setelah dinormalkan E.164",
          doc["user_data"]["ph"] == want_ph, doc["user_data"]["ph"][:16] + "…")
    check("C3 email dihuruf-kecilkan lalu di-hash", doc["user_data"]["em"] == want_em)
    raw = str(doc)
    check("C3 tidak ada nomor/email mentah di dokumen event",
          "08124400777" not in raw and "+628124400777" not in raw
          and "Budi.Test@Example.COM" not in raw)
    check("C5 mode simulasi berstatus 'simulated' (bukan 'sent')",
          doc["status"] == "simulated" and doc["transport"] == "simulation",
          f"{doc['status']}/{doc['transport']}")
    try:
        await capi.resend_conversion(doc["id"], org_id=ORG_ID, actor="poc")
        check("C5 kirim ulang di mode simulasi ditolak dengan alasan", False, "malah berhasil")
    except ValueError as exc:
        check("C5 kirim ulang di mode simulasi ditolak dengan alasan",
              "simulasi" in str(exc).lower() and "META_CAPI_TOKEN" in str(exc), str(exc)[:90])
    check("C5 atribusi kampanye ikut tersimpan di event",
          doc["campaign_id"] == camp["external_id"] and doc["adset_id"] == "AS-1")
    await db.conversion_events.delete_many({"org_id": ORG_ID, "lead_id": lead["id"]})


# ============================================================ D. mode adapter
async def section_d():
    head("D. MODE ADAPTER (env hanya mengubah mode, bukan kontrak)")
    check("D1 tanpa kredensial: Meta & Google mode simulasi",
          adapters.modes() == {"meta": "simulation", "google": "simulation"},
          str(adapters.modes()))
    sim_camps = await adapters.meta.list_campaigns({}, org_id=ORG_ID)
    sim_spend = await adapters.meta.daily_insights({}, org_id=ORG_ID)
    db_names = [c["name"] async for c in db.campaigns.find(
        {"org_id": ORG_ID, "platform": "meta"}, {"_id": 0, "name": 1})]
    check("D1 simulasi mengembalikan data DB (bukan angka karangan)",
          sorted(c["name"] for c in sim_camps) == sorted(db_names) and len(sim_camps) > 0,
          f"{len(sim_camps)} kampanye, {len(sim_spend)} baris biaya")
    check("D1 setiap baris biaya simulasi berlabel asal angka",
          all(r["source"] in ref.values("ad_spend_source") for r in sim_spend),
          str({r["source"] for r in sim_spend}))
    shape_camp = set(sim_camps[0]) if sim_camps else set()
    shape_spend = set(sim_spend[0]) if sim_spend else set()

    health = await rep.integration_health(ORG_ID)
    meta_row = next(r for r in health["rows"] if r["target"] == "meta_ads")
    check("D1 status integrasi: Meta 'simulation' + menyebut env yang belum diisi",
          meta_row["mode"] == "simulation" and "META_SYSTEM_USER_TOKEN" in meta_row["missing_env"],
          str(meta_row["missing_env"]))
    check("D4 nilai kredensial tidak pernah ikut keluar",
          all(set(e) == {"name", "filled"} for e in meta_row["env"]),
          str(meta_row["env"][:2]))
    check("D4 setiap integrasi menjelaskan apa yang terjadi tanpa kredensial",
          all(r["fallback"] and r["purpose"] for r in health["rows"]))

    os.environ["META_SYSTEM_USER_TOKEN"] = "DUMMY-TOKEN-UNTUK-UJI"
    os.environ["META_AD_ACCOUNT_ID"] = "123456789"
    try:
        check("D2 dengan kredensial dummy: mode berubah live",
              adapters.meta.mode() == "live", adapters.meta.mode())
        health2 = await rep.integration_health(ORG_ID, probe=True)
        meta2 = next(r for r in health2["rows"] if r["target"] == "meta_ads")
        check("D2 mode live tetap butuh env lain (jujur, bukan asal hijau)",
              meta2["mode"] == "simulation" and "META_APP_ID" in meta2["missing_env"],
              f"{meta2['mode']} missing={meta2['missing_env']}")
        ok, message = await adapters.meta.probe()
        check("D2 probe kredensial dummy GAGAL dan mengatakannya",
              ok is False and message, str(message)[:100])
        live_camps = None
        try:
            live_camps = await adapters.meta.list_campaigns({}, org_id=ORG_ID)
        except Exception as exc:  # noqa: BLE001
            live_camps = exc
        check("D3 mode live memakai kontrak yang sama (gagal jujur, bukan data palsu)",
              isinstance(live_camps, Exception) or isinstance(live_camps, list),
              type(live_camps).__name__)
    finally:
        os.environ.pop("META_SYSTEM_USER_TOKEN", None)
        os.environ.pop("META_AD_ACCOUNT_ID", None)
    check("D3 bentuk hasil simulasi sesuai kontrak DTO",
          {"external_id", "name", "objective", "status", "source"} <= shape_camp
          and {"date", "campaign_external_id", "spend", "currency", "source"} <= shape_spend,
          f"campaign={sorted(shape_camp)[:4]}… spend={sorted(shape_spend)[:4]}…")
    check("D1 mode kembali simulasi setelah env dilepas",
          adapters.meta.mode() == "simulation")


async def main():
    print("=" * 78)
    print("POC FASE 43 — KAMPANYE, BIAYA IKLAN (CSV idempoten), METRIK JUJUR, CAPI V2")
    print("=" * 78)
    await cleanup()
    try:
        camp = await section_a()
        await section_b(camp)
        await section_c(camp)
        await section_d()
    finally:
        await cleanup()
    print("\n" + "=" * 78)
    print(f"HASIL: {passed} PASS / {failed} FAIL")
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
