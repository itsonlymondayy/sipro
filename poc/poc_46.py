#!/usr/bin/env python3
"""poc_46.py — POC WAJIB Fase 46 (Konsolidasi Proyek & Konstruksi). SATU file.

Yang paling mudah gagal pada pekerjaan "konsolidasi konstruksi" bukan tabnya, melainkan
ANGKA dan GERBANGNYA:

  * papan unit yang **menghilangkan unit belum dijadwalkan** (padahal itu yang paling perlu
    perhatian), atau menampilkannya sebagai **0% "aman"** — dua-duanya menyesatkan;
  * dua kebenaran progres: papan baru menghitung sendiri lalu **berbeda** dengan
    `build_engine`/`build_monitor` yang sudah dipakai orang;
  * "umur telat" & "langkah aktif" yang tidak bisa direkonstruksi dari item pekerjaan;
  * gerbang **Mulai Bangun** yang hanya ada di setting tetapi tidak pernah dibaca kode —
    atau sebaliknya, memblokir diam-diam tanpa alasan yang bisa dibaca manusia;
  * izin yang **menempel di proyek saja** sehingga Unit 360 tidak bisa menjawab "izin unit
    ini apa saja, ada yang kedaluwarsa?";
  * izin `approved` yang **sudah kedaluwarsa** tetap tampak aman.

POC ini membuktikan enam hal itu SEBELUM satu endpoint/piksel dibuat:

  1. MATEMATIKA PAPAN UNIT : baris per UNIT; Σ bobot item terverifikasi ÷ Σ bobot == progres
                             engine (tie-out, satu kebenaran) + tie-out ke `build_monitor`.
  2. KEJUJURAN             : unit tanpa jadwal → planned/deviation/days_late = None +
                             `missing[]`, BUKAN 0; DP tak diketahui → None, bukan "belum bayar".
  3. KESIAPAN (evaluate)   : alasan berkode + tingkat (blocker/warning/info) + cara perbaikan;
                             hint kesiapan di tabel SAMA dengan hasil evaluator (tidak ada
                             dua rumus).
  4. MODE PERINGATAN       : bawaan `build.require_dp_before_start=False` → DP hanya
                             peringatan; dinyalakan → alasan yang sama menjadi blocker.
  5. TIDAK BOLEH DIAM-DIAM : mulai bangun saat ada peringatan WAJIB ack + alasan ≥5 huruf,
                             tercatat pada jadwal (`start_gate_log`) + aktivitas.
  6. IZIN BERTINGKAT       : rantai proyek→cluster→blok→unit ter-resolve; kedaluwarsa &
                             menjelang kedaluwarsa terklasifikasi; izin wajib yang hilang
                             memblokir HANYA bila kodenya didaftarkan admin.

Jalankan: `python3 poc/poc_46.py` (butuh Mongo hidup + DB seed). Exit != 0 bila ada FAIL.
Data uji sementara dibuat & DIHAPUS kembali (unit/jadwal/izin bertanda `poc_46`), sehingga
POC tidak meninggalkan sampah maupun mengubah data seed.

CATATAN PENTING (cacat yang ditutup pada penutupan Fase 46): POC ini dulu MENUMPANG pada
data seed untuk dua bahan uji — "unit calon mulai bangun" (terjadwal tapi belum berjalan)
dan "jadwal berstatus not_started" untuk uji izin wajib. Bahan itu SEKALI PAKAI: begitu ada
yang benar-benar menekan mulai bangun (mis. uji-mutasi yang mematikan syarat `ack`), unit
seed berubah menjadi "berjalan" dan POC/gate berikutnya MERAH karena datanya habis — bukan
karena kode salah. Sejak sekarang POC MEMBUAT SENDIRI dua unit sementara (POC46-01 &
POC46-02) dan membuangnya kembali, sehingga bisa dijalankan berulang kali tanpa merusak seed.
"""
import asyncio
import pathlib
import sys
from datetime import date, timedelta

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

ROOT = pathlib.Path("/app")
load_dotenv(ROOT / "backend" / ".env")

import build_engine as be  # noqa: E402
import build_monitor as bm  # noqa: E402
import build_readiness as br  # noqa: E402
import build_unit_board as bub  # noqa: E402
import permit_scope as ps  # noqa: E402
import settings_store as cfg  # noqa: E402
from core_utils import new_id, now_iso, today_iso_date  # noqa: E402
from db import ORG_ID, db  # noqa: E402

fails = []
TAG = "poc_46"


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)
    return bool(cond)


def _plus(days: int) -> str:
    return (date.fromisoformat(today_iso_date()) + timedelta(days=days)).isoformat()


# ============================================================ 1. MATEMATIKA PAPAN UNIT
async def test_board_math():
    print("\n[1] MATEMATIKA PAPAN UNIT (baris per unit + tie-out engine)")
    project = await db.projects.find_one({"org_id": ORG_ID}, {"_id": 0})
    out = await bub.unit_rows(ORG_ID, project_id=project["id"], limit=0)
    rows = out["data"]
    units_total = await db.units.count_documents({"org_id": ORG_ID, "project_id": project["id"]})
    check("semua unit muncul (termasuk yang belum dijadwalkan)",
          len(rows) == units_total, f"{len(rows)} baris / {units_total} unit")

    # tie-out: progres papan == Σ bobot item done ÷ Σ bobot (rumus build_engine)
    bad = []
    for r in [x for x in rows if x["schedule_id"]]:
        items = await db.build_items.find({"org_id": ORG_ID, "schedule_id": r["schedule_id"]},
                                          {"_id": 0, "weight": 1, "status": 1}).to_list(500)
        total_w = sum(float(i.get("weight") or 0) for i in items) or 1
        done_w = sum(float(i.get("weight") or 0) for i in items if i["status"] == "done")
        expect = round(done_w / total_w * 100, 1)
        if abs(expect - float(r["actual_progress"])) > 0.05:
            bad.append(f"{r['code']}: papan {r['actual_progress']} vs Σbobot {expect}")
    check("progres papan unit == Σ bobot item terverifikasi (satu kebenaran)",
          not bad, "; ".join(bad))

    board = await bm.board(ORG_ID, project_id=project["id"], limit=200)
    by_unit = {b["unit_id"]: b for b in board["data"]}
    diff = [f"{r['code']}" for r in rows if r["schedule_id"]
            and abs(float(by_unit[r["unit_id"]].get("progress") or 0)
                    - float(r["actual_progress"])) > 0.05]
    check("tie-out dengan build_monitor.board() (tidak ada dua kebenaran)",
          not diff, "; ".join(diff))

    scheduled = [r for r in rows if r["schedule_id"]]
    check("jumlah unit terjadwal = jumlah build_schedules",
          len(scheduled) == await db.build_schedules.count_documents(
              {"org_id": ORG_ID, "project_id": project["id"]}),
          f"{len(scheduled)} terjadwal")

    # kolom yang diminta dok 29 §4 harus benar-benar terisi untuk unit yang berjalan
    late = [r for r in scheduled if (r["days_late"] or 0) > 0]
    check("ada unit telat dengan umur telat > 0 hari (bisa direkonstruksi)",
          bool(late), f"{len(late)} unit telat")
    if late:
        r = late[0]
        items = await db.build_items.find(
            {"org_id": ORG_ID, "schedule_id": r["schedule_id"], "status": {"$ne": "done"}},
            {"_id": 0, "planned_finish": 1}).to_list(500)
        ref = today_iso_date()
        expect = max([(date.fromisoformat(ref)
                       - date.fromisoformat(str(i["planned_finish"])[:10])).days
                      for i in items if str(i.get("planned_finish") or "")[:10] < ref],
                     default=0)
        check(f"umur telat unit {r['code']} == hitungan dari item pekerjaan",
              expect == r["days_late"], f"{r['days_late']} vs {expect}")
        check(f"unit {r['code']} punya langkah aktif + PIC + bukti terakhir",
              bool(r["active_step"] and r["pic"] and r["last_evidence"]),
              f"step={bool(r['active_step'])} pic={r['pic']} bukti={bool(r['last_evidence'])}")

    s = out["summary"]
    check("ringkasan memisahkan terjadwal vs belum dijadwalkan",
          s["scheduled"] + s["unscheduled"] == s["units_total"] and s["unscheduled"] > 0,
          f"{s['scheduled']} terjadwal / {s['unscheduled']} belum")
    return out


# ============================================================ 2. KEJUJURAN ANGKA
async def test_honesty(out):
    print("\n[2] KEJUJURAN (0 ≠ belum ada data)")
    rows = out["data"]
    no_sched = [r for r in rows if not r["schedule_id"]]
    check("ada unit belum dijadwalkan untuk diuji", bool(no_sched), f"{len(no_sched)} unit")
    zeros = [r["code"] for r in no_sched
             if r["planned_progress"] == 0 or r["deviation"] == 0 or r["days_late"] == 0]
    check("unit tanpa jadwal TIDAK menampilkan 0 (planned/deviasi/telat)",
          not zeros, "; ".join(zeros[:5]))
    nulls = all(r["planned_progress"] is None and r["deviation"] is None
                and r["days_late"] is None for r in no_sched)
    check("unit tanpa jadwal → None + missing[]", nulls and all(
        "jadwal_pembangunan" in r["missing"] for r in no_sched))
    unknown_dp = [r for r in rows if not r["dp_known"]]
    check("DP tanpa rencana bayar → dp_paid None + missing 'rencana_bayar'",
          bool(unknown_dp) and all(r["dp_paid"] is None and "rencana_bayar" in r["missing"]
                                   for r in unknown_dp), f"{len(unknown_dp)} unit")
    check("rata-rata progres hanya dari unit terjadwal (bukan dibagi semua unit)",
          out["summary"]["avg_progress"] is not None
          and abs(out["summary"]["avg_progress"]
                  - round(sum(r["actual_progress"] for r in rows if r["schedule_id"])
                          / max(1, out["summary"]["scheduled"]), 1)) < 0.06,
          str(out["summary"]["avg_progress"]))
    legacy = await db.permits.find_one({"org_id": ORG_ID, "status": "approved",
                                        "expiry_at": {"$in": [None, ""]}}, {"_id": 0})
    if legacy is None:
        legacy = await db.permits.find_one({"org_id": ORG_ID, "expiry_at": {"$exists": False}},
                                           {"_id": 0})
    check("izin tanpa tanggal berlaku tidak diklaim 'aman selamanya' (expiry_known False)",
          legacy is not None and ps.health(legacy)["expiry_known"] is False,
          str((legacy or {}).get("type")))


# ============================================================ 3. KESIAPAN + 4. MODE
async def test_readiness(out, cand_unit):
    print("\n[3] KESIAPAN MULAI BANGUN (alasan berkode) & [4] MODE PERINGATAN vs TEGAS")
    rows = out["data"]
    started = next((r for r in rows if r["readiness"] == "started"), None)
    blocked = next((r for r in rows if not r["schedule_id"]), None)
    # calon "mulai bangun" = unit SEMENTARA milik POC (terjadwal, belum berjalan). Dulu
    # dicari di antara unit seed; itu membuat POC sekali pakai (lihat catatan di docstring).
    candidate = next((r for r in rows if r["unit_id"] == cand_unit["id"]), None)
    check("papan menemukan unit sudah berjalan / belum dijadwalkan / calon mulai",
          all([started, blocked, candidate]),
          f"{(started or {}).get('code')}, {(blocked or {}).get('code')}, "
          f"{(candidate or {}).get('code')}")

    for row in [x for x in (started, blocked, candidate) if x]:
        ev = await br.evaluate(ORG_ID, row["unit_id"])
        check(f"hint tabel == evaluator untuk unit {row['code']} ({ev['state']})",
              ev["state"] == row["readiness"], f"{row['readiness']} vs {ev['state']}")

    ev_blocked = await br.evaluate(ORG_ID, blocked["unit_id"])
    check("unit tanpa jadwal → blocked dengan kode no_schedule + saran perbaikan",
          ev_blocked["state"] == "blocked" and not ev_blocked["can_start"]
          and any(r["code"] == "no_schedule" and r["fix"] for r in ev_blocked["blockers"]))

    ev_c = await br.evaluate(ORG_ID, candidate["unit_id"])
    check("bawaan: DP/rencana bayar hanya PERINGATAN (bisa mulai dengan konfirmasi)",
          ev_c["can_start"] and ev_c["needs_ack"] and ev_c["state"] == "warning"
          and any(r["code"] in ("no_payment_plan", "dp_unpaid") for r in ev_c["warnings"]),
          f"state={ev_c['state']} warnings={[w['code'] for w in ev_c['warnings']]}")
    check("mode bawaan tercatat MATI (peringatan, bukan blokir)",
          ev_c["mode"] == {"require_dp_before_start": False, "block_build_without": [],
                           "enforced": False}, str(ev_c["mode"]))

    # ---- uji negatif: admin menyalakan kebijakan → alasan yang sama menjadi blocker ----
    await cfg.set_value("build.require_dp_before_start", True, actor="poc_46",
                        reason="Uji POC Fase 46: mode tegas harus benar-benar memblokir.")
    try:
        ev_on = await br.evaluate(ORG_ID, candidate["unit_id"])
        check("mode TEGAS: DP belum terbukti → blocked (uji negatif)",
              ev_on["state"] == "blocked" and not ev_on["can_start"]
              and any(r["code"] in ("no_payment_plan", "dp_unpaid")
                      for r in ev_on["blockers"]),
              f"state={ev_on['state']}")
        try:
            await br.start_build(ORG_ID, candidate["unit_id"], "poc@sipro.co.id",
                                 ack=True, reason="tetap mulai walau DP belum")
            check("mode TEGAS menolak start", False, "TIDAK ditolak")
        except ValueError as e:
            check("mode TEGAS menolak start dengan alasan yang bisa dibaca",
                  "Belum bisa dimulai" in str(e), str(e)[:90])
    finally:
        await cfg.reset("build.require_dp_before_start", actor="poc_46")
    ev_back = await br.evaluate(ORG_ID, candidate["unit_id"])
    check("setelah kebijakan dikembalikan, kembali PERINGATAN",
          ev_back["state"] == "warning" and ev_back["can_start"])
    return candidate


# ============================================================ 5. GERBANG START (ack)
async def _make_temp_unit(project, block, code="POC46-01"):
    """Unit + jadwal sementara: menguji START tanpa menyentuh data seed."""
    src = await db.units.find_one({"org_id": ORG_ID, "type": {"$ne": None}},
                                  {"_id": 0, "type": 1, "unit_type_code": 1,
                                   "unit_type_id": 1, "price": 1})
    unit = {
        "id": new_id(), "org_id": ORG_ID, "project_id": project["id"], "code": code,
        "type": src["type"], "unit_type_code": src.get("unit_type_code"),
        "unit_type_id": src.get("unit_type_id"), "price": src.get("price") or 100000000,
        "status": "available", "construction_status": "not_started",
        "construction_progress": 0, "payment_status": "unpaid",
        "block": block.get("code"), "block_id": block["id"],
        "cluster_code": block.get("cluster_code"), "cluster_id": block.get("cluster_id"),
        "no": "01", "poc_46": True, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.units.insert_one(dict(unit))
    tpl = await be.template_for_unit(ORG_ID, unit)
    sched = await be.generate_schedule(ORG_ID, unit, tpl, today_iso_date(), "poc_46")
    return unit, sched


async def _cleanup_temp(unit_id):
    scheds = await db.build_schedules.find({"unit_id": unit_id}, {"_id": 0, "id": 1}).to_list(5)
    ids = [s["id"] for s in scheds]
    items = await db.build_items.find({"schedule_id": {"$in": ids}},
                                      {"_id": 0, "id": 1}).to_list(500)
    await db.tasks.delete_many({"meta.build_item_id": {"$in": [i["id"] for i in items]}})
    await db.build_items.delete_many({"schedule_id": {"$in": ids}})
    await db.build_schedules.delete_many({"unit_id": unit_id})
    await db.units.delete_one({"id": unit_id})
    await db.activities.delete_many({"entity_type": "unit", "entity_id": unit_id})
    await db.events.delete_many({"entity_type": "unit", "entity_id": unit_id})
    await db.notifications.delete_many({"related_entity_id": unit_id})


async def test_start_gate(unit, sched):
    """Unit/jadwal sudah disiapkan pemanggil (fixture POC), jadi POC bisa diulang."""
    print("\n[5] MULAI BANGUN: peringatan tidak boleh diabaikan diam-diam")
    ev = await br.evaluate(ORG_ID, unit["id"])
    check("unit baru: siap dimulai dengan peringatan (belum ada rencana bayar)",
          ev["state"] == "warning" and ev["needs_ack"],
          f"state={ev['state']} warn={[w['code'] for w in ev['warnings']]}")
    try:
        await br.start_build(ORG_ID, unit["id"], "pm@sipro.co.id")
        check("start tanpa konfirmasi ditolak", False, "TIDAK ditolak")
    except ValueError as e:
        check("start tanpa konfirmasi ditolak + menyebut peringatannya",
              "peringatan" in str(e).lower(), str(e)[:80])
    try:
        await br.start_build(ORG_ID, unit["id"], "pm@sipro.co.id", ack=True, reason="ok")
        check("alasan terlalu pendek ditolak", False, "TIDAK ditolak")
    except ValueError as e:
        check("alasan terlalu pendek ditolak", "minimal" in str(e).lower(), str(e)[:80])

    res = await br.start_build(ORG_ID, unit["id"], "pm@sipro.co.id", ack=True,
                               reason="Disetujui direksi: pondasi didahulukan musim kering.")
    check("start dengan konfirmasi + alasan berhasil", res["started"] is True)
    check("langkah pertama benar-benar dijalankan (bukan status ditimpa)",
          res["item"]["status"] == "in_progress", res["item"]["name"][:40])
    fresh_sched = await db.build_schedules.find_one({"id": sched["id"]}, {"_id": 0})
    log = (fresh_sched.get("start_gate_log") or [])
    check("jejak gerbang tercatat (siapa, kapan, alasan, peringatan)",
          bool(log) and log[-1]["reason"].startswith("Disetujui")
          and log[-1]["acknowledged"] is True and log[-1]["warnings"],
          str(log[-1].get("warnings"))[:70] if log else "kosong")
    fresh_unit = await db.units.find_one({"id": unit["id"]}, {"_id": 0})
    check("status unit menjadi berjalan lewat recompute engine (bukan ditulis manual)",
          fresh_unit["construction_status"] == "in_progress",
          fresh_unit["construction_status"])
    acts = await db.activities.count_documents({"entity_type": "unit",
                                                "entity_id": unit["id"]})
    check("aktivitas unit mencatat keputusan mulai bangun", acts >= 1, f"{acts} aktivitas")
    try:
        await br.start_build(ORG_ID, unit["id"], "pm@sipro.co.id", ack=True,
                             reason="mencoba mulai dua kali")
        check("start kedua ditolak", False, "TIDAK ditolak")
    except ValueError as e:
        check("start kedua ditolak (sudah berjalan)", "sudah berjalan" in str(e),
              str(e)[:70])
    ev2 = await br.evaluate(ORG_ID, unit["id"])
    check("kesiapan berubah menjadi 'started'", ev2["state"] == "started")
    return unit


# ============================================================ 6. IZIN BERTINGKAT
async def test_permit_chain(unit, project, block, other_unit):
    print("\n[6] IZIN MENEMPEL OBJEK (proyek → cluster → blok → unit) + kedaluwarsa")
    docs = [
        {"type": "PBG", "name": "PBG Cluster Utama", "scope": "cluster",
         "scope_id": block["cluster_id"], "status": "approved", "expiry_at": _plus(400),
         "reminder_days": 30},
        {"type": "SLF", "name": "SLF Blok A", "scope": "block", "scope_id": block["id"],
         "status": "approved", "expiry_at": _plus(10), "reminder_days": 30},
        {"type": "ADDENDUM", "name": "Addendum unit POC", "scope": "unit",
         "scope_id": unit["id"], "status": "approved", "expiry_at": _plus(-3),
         "reminder_days": 14},
    ]
    ids = []
    for d in docs:
        row = {"id": new_id(), "org_id": ORG_ID, "project_id": project["id"],
               "project_name": project.get("name"), "poc_46": True,
               "created_at": now_iso(), "updated_at": now_iso(), **d}
        await db.permits.insert_one(dict(row))
        ids.append(row["id"])
    try:
        cov = await ps.coverage(ORG_ID, unit_id=unit["id"])
        by_type = {p["type"]: p for p in cov["permits"]}
        check("rantai objek ter-resolve lengkap",
              all(cov["chain"][k] for k in ("unit_id", "block_id", "cluster_id", "project_id")),
              str(cov["chain"]["labels"]))
        check("izin cluster & blok & unit semuanya berlaku untuk unit ini",
              all(t in by_type for t in ("PBG", "SLF", "ADDENDUM")),
              ",".join(sorted(by_type)))
        check("izin tingkat proyek (data lama tanpa scope) tetap terbaca sebagai warisan",
              any(p["scope"] == "project" for p in cov["permits"]),
              str([p["type"] for p in cov["permits"] if p["scope"] == "project"]))
        check("PBG aktif → sehat 'ok'", by_type["PBG"]["health"] == "ok",
              by_type["PBG"]["health"])
        check("SLF berakhir 10 hari lagi → 'expiring' + sisa hari benar",
              by_type["SLF"]["health"] == "expiring"
              and by_type["SLF"]["days_to_expiry"] == 10,
              f"{by_type['SLF']['health']}/{by_type['SLF']['days_to_expiry']}")
        check("ADDENDUM lewat tanggal → 'expired' meski status approved",
              by_type["ADDENDUM"]["health"] == "expired", by_type["ADDENDUM"]["health"])
        check("peringatan izin dijelaskan (kedaluwarsa & menjelang) — bukan angka saja",
              {w["code"] for w in cov["warnings"]} >= {"permit_expired", "permit_expiring"},
              str([w["code"] for w in cov["warnings"]]))

        cov_ok = await ps.coverage(ORG_ID, unit_id=unit["id"], required_codes=["PBG"])
        # dua keadaan berbeda yang WAJIB dibedakan: izin tidak ada sama sekali vs izin ada
        # tetapi masih diproses. Keduanya TIDAK memenuhi syarat, tetapi ceritanya berbeda.
        cov_none = await ps.coverage(ORG_ID, unit_id=unit["id"], required_codes=["LAINNYA"])
        cov_proc = await ps.coverage(ORG_ID, unit_id=unit["id"], required_codes=["ANDALALIN"])
        check("izin wajib yang ADA dinyatakan terpenuhi + menunjuk izinnya",
              cov_ok["required"][0]["satisfied"] and cov_ok["required"][0]["scope"] == "cluster"
              and not cov_ok["missing_codes"], str(cov_ok["required"][0]["scope_label"]))
        check("izin wajib yang TIDAK ADA → missing (bukan diam-diam lolos)",
              cov_none["missing_codes"] == ["LAINNYA"]
              and cov_none["required"][0]["health"] == "missing",
              str(cov_none["required"][0]["health"]))
        check("izin wajib yang MASIH DIPROSES tetap tidak memenuhi (dan diakui apa adanya)",
              cov_proc["missing_codes"] == ["ANDALALIN"]
              and cov_proc["required"][0]["health"] == "in_process",
              str(cov_proc["required"][0]["health"]))

        # uji negatif: izin wajib memblokir HANYA bila admin mendaftarkan kodenya.
        # Sengaja memakai unit yang SUDAH dijadwalkan tetapi BELUM berjalan (kesiapan
        # "warning") agar perubahan status terlihat jelas: warning → blocked → warning.
        # Unit itu fixture POC (POC46-02), bukan unit seed: dulu POC memungut jadwal
        # seed berstatus `not_started` dan itu habis begitu ada yang menekan mulai bangun.
        other = {"id": other_unit["id"], "code": other_unit["code"]}
        ev_before = await br.evaluate(ORG_ID, other["id"])
        await cfg.set_value("permit.block_build_without", ["ANDALALIN"], actor="poc_46",
                            reason=None)
        try:
            ev_after = await br.evaluate(ORG_ID, other["id"])
            check("daftar izin wajib kosong = tidak memblokir; diisi = memblokir",
                  ev_before["state"] != "blocked" and ev_after["state"] == "blocked"
                  and "permit_missing" not in [r["code"] for r in ev_before["reasons"]]
                  and any(r["code"] == "permit_missing" and r["severity"] == "blocker"
                          for r in ev_after["reasons"]),
                  f"unit {other['code']}: {ev_before['state']} → {ev_after['state']}")
        finally:
            await cfg.reset("permit.block_build_without", actor="poc_46")
        ev_reset = await br.evaluate(ORG_ID, other["id"])
        check("kebijakan izin dikembalikan → tidak lagi memblokir",
              ev_reset["state"] != "blocked"
              and "permit_missing" not in [r["code"] for r in ev_reset["reasons"]],
              ev_reset["state"])
    finally:
        await db.permits.delete_many({"id": {"$in": ids}})


async def main():
    print("=" * 78)
    print("POC FASE 46 — Papan Unit, Gerbang Mulai Bangun, Izin Bertingkat")
    print("=" * 78)
    project = await db.projects.find_one({"org_id": ORG_ID}, {"_id": 0})
    block = await db.blocks.find_one({"org_id": ORG_ID, "project_id": project["id"]},
                                     {"_id": 0})
    # sisa run yang mati di tengah tidak boleh menjadi unit kembar
    for leftover in await db.units.find({"org_id": ORG_ID, TAG: True},
                                        {"_id": 0, "id": 1}).to_list(50):
        await _cleanup_temp(leftover["id"])
    temp_ids = []
    try:
        # dua fixture: (1) calon mulai bangun yang akan DITEKAN, (2) unit terjadwal yang
        # tetap belum berjalan untuk uji "izin wajib memblokir" — keduanya milik POC,
        # sehingga POC bisa dijalankan berkali-kali tanpa menghabiskan data seed.
        cand, cand_sched = await _make_temp_unit(project, block, "POC46-01")
        other, _other_sched = await _make_temp_unit(project, block, "POC46-02")
        temp_ids = [cand["id"], other["id"]]
        out = await test_board_math()
        await test_honesty(out)
        await test_readiness(out, cand)
        await test_start_gate(cand, cand_sched)
        await test_permit_chain(cand, project, block, other)
    finally:
        for uid in temp_ids:
            await _cleanup_temp(uid)
        left = await db.units.count_documents({TAG: True})
        print(f"\n  bersih-bersih: sisa data POC = {left} unit "
              f"(harus 0), izin POC = {await db.permits.count_documents({TAG: True})}")
    print("\n" + "=" * 78)
    if fails:
        print(f"HASIL: FAIL ({len(fails)}) → " + "; ".join(fails))
        return 1
    print("HASIL: PASS — inti Fase 46 terbukti (papan unit, kejujuran, gerbang, izin).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
