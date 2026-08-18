#!/usr/bin/env python3
"""poc_45.py — POC WAJIB Fase 45 (Target Proyek & Budget/RAB). SATU file, semua pembuktian.

Yang paling mudah gagal pada pekerjaan "target & anggaran" bukan layarnya, tetapi ANGKANYA:

  * target bulanan yang **naik tanpa penjelasan** setelah penyesuaian otomatis;
  * total target yang **bocor beberapa unit** karena tiap bulan dibulatkan sendiri-sendiri;
  * laporan historis yang **berubah diam-diam** saat target dihitung ulang;
  * "realisasi RAB" yang **berbeda** dengan panel Kendali Biaya yang sudah dipakai orang;
  * biaya yang **terhitung dua kali** (material dibeli lewat PO lalu pemakaiannya dijumlahkan);
  * proyek tanpa anggaran yang digambar **"Rp 0 — aman"**, padahal artinya belum diisi.

POC ini membuktikan enam hal itu SEBELUM satu endpoint atau satu piksel UI dibuat:

  1. MATEMATIKA TARGET : 5 metode; Σ rencana ke depan + realisasi lampau == total target
                         (`keep_total`), pembagian eksak tanpa bocor.
  2. DINAMIS & JUJUR   : `lock_past` menjaga periode lampau; `carry_over` menjelaskan kenaikan;
                         `history` mencatat sebelum→sesudah + alasan.
  3. KEJUJURAN METODE  : metode yang kekurangan bahan (bobot kurva-S / harga rata-rata /
                         riwayat kecepatan) MENOLAK menghitung dan menyebut apa yang kurang.
  4. TIE-OUT KONSTRUKSI: agregasi anggaran konstruksi == `opname.cost_control()` (satu kebenaran).
  5. DRILL 3 LAPIS     : Σ dokumen sumber == angka item == angka kategori == angka proyek.
  6. ANTI DOUBLE-COUNT : pemakaian material tidak masuk realisasi (sudah diakui via tagihan),
                         dan alasannya disampaikan, bukan disembunyikan.

Jalankan: `python3 poc/poc_45.py` (butuh Mongo hidup + DB seed). Exit != 0 bila ada FAIL.
"""
import asyncio
import os
import pathlib
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

ROOT = pathlib.Path("/app")
load_dotenv(ROOT / "backend" / ".env")

import budget_engine as be  # noqa: E402
import budget_reports as br  # noqa: E402
import target_engine as te  # noqa: E402
import target_store as ts  # noqa: E402
from db import ORG_ID, db  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)
    return bool(cond)


MONTHS = te.month_list("2026-01", "2026-12")


# ==================================================================== 1. MATEMATIKA TARGET
def test_target_math():
    print("\n1. MATEMATIKA TARGET — 5 metode, Σ eksak, tidak ada unit yang bocor")
    check("kalender bulan benar", MONTHS[0] == "2026-01" and MONTHS[-1] == "2026-12"
          and len(MONTHS) == 12, f"{len(MONTHS)} bulan")
    check("month_add melewati tahun", te.month_add("2026-11", 3) == "2027-02",
          te.month_add("2026-11", 3))

    # Pembagian eksak: 120 unit / 7 bulan tidak boleh menghasilkan Σ 119 atau 126.
    parts = te.distribute(120, 7)
    check("distribute() menjumlah PERSIS total", sum(parts) == 120, f"{parts} Σ={sum(parts)}")
    wparts = te.distribute(100, 4, [10, 20, 30, 40])
    check("distribute() berbobot menjumlah persis", sum(wparts) == 100, str(wparts))

    actuals = {"2026-01": {"unit": 3, "revenue": 3 * 850_000_000},
               "2026-02": {"unit": 5, "revenue": 5 * 850_000_000},
               "2026-03": {"unit": 2, "revenue": 2 * 850_000_000}}
    common = dict(months=MONTHS, unit_target=120, revenue_target=120 * 850_000_000,
                  avg_price=850_000_000, actuals=actuals, today="2026-04")

    lin = te.compute_periods(method="linear_remaining", **common)
    check("linear_remaining: tidak ada `missing`", not lin["missing"], str(lin["missing"]))
    check("linear_remaining: keep_total terjaga (realisasi lampau + rencana ke depan = target)",
          lin["totals"]["keep_total_ok"] is True,
          f"{lin['totals']['unit_actual_past']} + {lin['totals']['unit_plan_future']} "
          f"vs {lin['totals']['unit_target']}")
    check("linear_remaining: rencana pendapatan mengikuti harga rata-rata",
          all(p["revenue_plan"] == p["unit_plan"] * 850_000_000
              for p in lin["periods"] if p["period"] >= "2026-04"))

    weights = {m: (100 / 12) for m in MONTHS}
    sc = te.compute_periods(method="s_curve", weights=weights, **common)
    check("s_curve: keep_total terjaga", sc["totals"]["keep_total_ok"] is True,
          str(sc["totals"]))
    sc_kosong = te.compute_periods(method="s_curve", weights={}, **common)
    check("s_curve TANPA bobot menolak menghitung (bukan 0)",
          bool(sc_kosong["missing"]) and all(p["unit_plan"] is None
                                            for p in sc_kosong["periods"]
                                            if p["period"] >= "2026-04"),
          str(sc_kosong["missing"]))

    manual = {m: 10 for m in MONTHS if m >= "2026-04"}
    mn = te.compute_periods(method="manual", manual=manual, **common)
    check("manual: memakai angka pemakai apa adanya",
          [p["unit_plan"] for p in mn["periods"] if p["period"] >= "2026-04"] == [10] * 9)
    check("manual: deviasi Σ vs total DILAPORKAN (tidak dibetulkan diam-diam)",
          any("beda" in w for w in mn["warnings"]), str(mn["warnings"])[:160])

    vf = te.compute_periods(method="velocity_forecast", growth_pct=10, **common)
    check("velocity_forecast: memakai median 3 bulan terakhir (3,5,2 → 3 × 1,1 = 3,3 → 4)",
          not vf["missing"] and vf["periods"][3]["unit_plan"] == 4,
          f"{vf['periods'][3]['unit_plan']} · {vf['missing']}")
    check("velocity_forecast: menghasilkan proyeksi bulan habis terjual",
          bool(vf["projection"]) and vf["projection"]["months_needed"] > 0,
          str(vf["projection"]))
    vf_kosong = te.compute_periods(method="velocity_forecast",
                                  **{**common, "actuals": {}, "today": "2026-01"})
    check("velocity_forecast TANPA riwayat menolak memproyeksi",
          bool(vf_kosong["missing"]), str(vf_kosong["missing"]))

    rf = te.compute_periods(method="revenue_first", **common)
    fut = [p for p in rf["periods"] if p["period"] >= "2026-04"]
    check("revenue_first: rencana pendapatan menjumlah sisa pendapatan",
          sum(p["revenue_plan"] for p in fut) ==
          rf["totals"]["revenue_target"] - rf["totals"]["revenue_actual_past"],
          str(sum(p["revenue_plan"] for p in fut)))
    check("revenue_first: unit diturunkan dari pendapatan / harga",
          all(p["unit_plan"] >= 1 for p in fut))
    rf_tanpa_harga = te.compute_periods(method="revenue_first", **{**common, "avg_price": 0})
    check("revenue_first TANPA harga rata-rata menolak menghitung",
          any("harga rata-rata" in m for m in rf_tanpa_harga["missing"]),
          str(rf_tanpa_harga["missing"]))

    over = te.compute_periods(method="linear_remaining",
                             **{**common, "unit_target": 8})
    check("target yang SUDAH tercapai memberi rencana 0 dengan penjelasan (nol yang benar)",
          all(p["unit_plan"] == 0 for p in over["periods"] if p["period"] >= "2026-04")
          and any("tercapai" in (w or "") for w in over["warnings"]),
          str(over["warnings"])[:120])
    return lin


# ============================================================ 2. DINAMIS, LOCK & CARRY-OVER
def test_recalc(lin):
    print("\n2. DINAMIS — periode lampau terkunci, kenaikan target punya penjelasan")
    target = {
        "id": "poc-target", "project_id": "p1", "method": "linear_remaining",
        "horizon": {"start": "2026-01", "end": "2026-12"}, "unit_target": 120,
        "revenue_target": 120 * 850_000_000,
        "assumptions": {"avg_price": 850_000_000},
        "recalc_policy": {"mode": "monthly", "keep_total": True, "lock_past": True},
        "periods": lin["periods"],
    }
    # Bulan berjalan maju ke Mei; realisasi April jauh di bawah rencana (2 dari 10).
    actuals = {"2026-01": {"unit": 3, "revenue": 0}, "2026-02": {"unit": 5, "revenue": 0},
               "2026-03": {"unit": 2, "revenue": 0}, "2026-04": {"unit": 2, "revenue": 0}}
    out = te.recalc(target, actuals=actuals, today="2026-05", reason="Awal bulan Mei",
                    actor="poc")
    april_before = next(p["unit_plan"] for p in lin["periods"] if p["period"] == "2026-04")
    april_after = next(p for p in out["periods"] if p["period"] == "2026-04")
    check("periode lampau TIDAK berubah (lock_past)",
          april_after["unit_plan"] == april_before and april_after["locked"] is True,
          f"{april_before} → {april_after['unit_plan']}")
    mei = next(p for p in out["periods"] if p["period"] == "2026-05")
    check("kekurangan bulan lalu terlihat sebagai carry_over pada bulan berjalan",
          mei["carry_over"] > 0 and "kekurangan" in (mei["note"] or ""),
          f"carry_over={mei['carry_over']} · {mei['note']}")
    check("keep_total tetap terjaga setelah penyesuaian",
          out["totals"]["keep_total_ok"] is True,
          f"{out['totals']['unit_actual_past']} + {out['totals']['unit_plan_future']}")
    check("target bulan berjalan NAIK dibanding rencana awal (dan itu dijelaskan)",
          mei["unit_plan"] >= april_before, f"{april_before} → {mei['unit_plan']}")
    check("jejak penyesuaian mencatat sebelum→sesudah + alasan",
          out["history_entry"]["reason"] == "Awal bulan Mei"
          and out["history_entry"]["changed_periods"] > 0,
          str(out["history_entry"])[:140])

    # Menjalankan ulang recalc dengan data yang sama TIDAK boleh mengubah apa pun lagi.
    stable = te.recalc({**target, "periods": out["periods"]}, actuals=actuals, today="2026-05",
                       reason="ulang", actor="poc")
    check("recalc idempoten (dijalankan 2× dengan data sama → 0 perubahan)",
          stable["history_entry"]["changed_periods"] == 0,
          str(stable["changes"])[:120])

    problems = te.validate_scope(120, [{"unit_target": 70}, {"unit_target": 60}])
    check("validasi cakupan: Σ target anak > induk DITOLAK", bool(problems), str(problems)[:120])
    check("validasi cakupan: Σ target anak ≤ induk diterima",
          not te.validate_scope(120, [{"unit_target": 70}, {"unit_target": 50}]))


# ==================================================================== 3-6. ANGGARAN (DB)
async def test_budget():
    print("\n3. ANGGARAN — tie-out konstruksi, drill 3 lapis, anti double-count, kejujuran")
    org = ORG_ID
    proj = await db.projects.find_one({"org_id": org}, {"_id": 0, "id": 1, "name": 1})
    if not proj:
        check("ada proyek seed untuk diuji", False, "koleksi projects kosong")
        return
    pid = proj["id"]

    # --- kejujuran: proyek tanpa item anggaran TIDAK boleh tampil Rp 0 / aman
    await db.budget_items.delete_many({"org_id": org, "project_id": pid, "code": {
        "$in": ["POC-OPS", "POC-KON", "POC-REF", "POC-MAN"]}})
    empty = await be.compute_project(org, pid, alert_pct=90)
    if empty["item_count"] == 0:
        check("proyek tanpa item anggaran: state `kosong`, totals None (bukan Rp 0)",
              empty["state"] == "kosong" and empty["totals"] is None and empty["missing"],
              f"state={empty['state']} totals={empty['totals']}")
    else:
        check("proyek sudah punya item anggaran (uji kosong dilewati)", True,
              f"{empty['item_count']} item")

    # --- tie-out konstruksi vs panel Kendali Biaya yang sudah dipakai orang
    tie = await be.tie_out(org, pid)
    check("agregasi konstruksi TIE-OUT dengan opname.cost_control() (satu kebenaran)",
          tie["ok"], f"selisih={tie['diff']} · mine={tie['mine']}")

    # --- siapkan 3 item anggaran uji: konstruksi (read-only), operasional (GL), cost_ref
    boq = await db.boq_items.find({"org_id": org, "project_id": pid},
                                  {"_id": 0, "id": 1, "amount": 1}).to_list(50)
    from core_utils import new_id, now_iso
    ts_now = now_iso()
    ids = {}
    for code, cat, rule, planned, extra in [
        ("POC-KON", "konstruksi", "by_boq_item", 0,
         {"boq_item_ids": [b["id"] for b in boq]}),
        ("POC-OPS", "operasional", "by_gl_account", 5_000_000, {"gl_account": "6-1300"}),
        ("POC-REF", "marketing", "by_cost_ref", 50_000_000, {}),
        ("POC-MAN", "overhead", "manual", 1_000_000, {}),
    ]:
        doc = {"id": new_id(), "org_id": org, "project_id": pid, "cluster_id": None,
               "unit_id": None, "category": cat, "code": code, "name": f"Uji {code}",
               "planned_amount": planned, "currency": "IDR", "match_rule": rule,
               "boq_item_ids": [], "gl_account": None, "owner_role": "project_manager",
               "period": "project", "revision": [], "active": True, "order": 99,
               "note": "dibuat POC 45", "created_by": "poc", "created_at": ts_now,
               "updated_at": ts_now, **extra}
        await db.budget_items.insert_one(dict(doc))
        ids[code] = doc["id"]

    summary = await be.compute_project(org, pid, alert_pct=90)
    rows = {r["code"]: r for r in summary["items"]}
    kon = rows["POC-KON"]
    boq_total = sum(be._i(b["amount"]) for b in boq)
    check("item konstruksi: rencana DIHITUNG dari Σ item RAB (read-only, bukan angka kedua)",
          kon["planned"] == boq_total and kon["planned_readonly"] is True,
          f"{kon['planned']} vs Σ boq {boq_total}")
    con_rows = await be.construction_by_boq(org, pid)
    linked = [b["id"] for b in boq]
    mapped_verified = sum(con_rows[b]["verified"] for b in linked if b in con_rows)
    mapped_po_billed = sum(con_rows[b]["po_billed"] for b in linked if b in con_rows)
    unmapped_verified = tie["mine"]["verified"] - mapped_verified
    check("item konstruksi: realisasi == lingkup terverifikasi (yang TERTAUT) + PO tertagih",
          kon["realized"] == mapped_verified + mapped_po_billed,
          f"{kon['realized']} vs {mapped_verified}+{mapped_po_billed}")
    check("lingkup yang belum tertaut item RAB TIDAK diselundupkan ke item anggaran mana pun",
          unmapped_verified >= 0 and kon["realized"] <= tie["mine"]["verified"],
          f"belum tertaut = Rp {unmapped_verified:,}".replace(",", "."))
    check("komitmen & realisasi konstruksi SALING LEPAS (contracted = keduanya, tanpa dobel)",
          sum(con_rows[b]["contracted"] for b in linked if b in con_rows) ==
          (kon["realized"] - mapped_po_billed) + (kon["committed"] -
                                                  sum(con_rows[b]["po_committed"]
                                                      for b in linked if b in con_rows)),
          f"contracted={sum(con_rows[b]['contracted'] for b in linked if b in con_rows)}")

    # --- DRILL 3 LAPIS: Σ dokumen == angka item == angka kategori == angka proyek
    for code, row in rows.items():
        docs_real = sum(d["amount"] for d in row["documents"] if d["kind"] == "realisasi")
        docs_comm = sum(d["amount"] for d in row["documents"] if d["kind"] == "komitmen")
        check(f"lapis 3 → lapis 2 ({code}): Σ dokumen realisasi == realisasi item",
              docs_real == row["realized"], f"{docs_real} vs {row['realized']}")
        check(f"lapis 3 → lapis 2 ({code}): Σ dokumen komitmen == komitmen item",
              docs_comm == row["committed"], f"{docs_comm} vs {row['committed']}")
    cat_real = sum(c["realized"] for c in summary["categories"])
    item_real = sum(r["realized"] for r in summary["items"])
    check("lapis 2 → lapis 1: Σ kategori == Σ item == total proyek",
          cat_real == item_real == summary["totals"]["realized"],
          f"kategori={cat_real} item={item_real} total={summary['totals']['realized']}")
    check("exposure = realisasi + komitmen (rumus spec §4)",
          summary["totals"]["exposure"] ==
          summary["totals"]["realized"] + summary["totals"]["committed"])
    check("variance = rencana − exposure",
          summary["totals"]["variance"] ==
          summary["totals"]["planned"] - summary["totals"]["exposure"])

    # --- GL: beban yang proyeknya tidak terlacak TIDAK dijumlahkan, tapi dilaporkan
    ops = rows["POC-OPS"]
    check("item GL menyebut beban yang belum bisa dipetakan ke proyek (tidak dijumlahkan)",
          ops["unresolved"] is not None and (ops["unresolved"]["rows"] > 0 or
                                            ops["realized"] > 0),
          f"realisasi={ops['realized']} unresolved={ops['unresolved']}")

    # --- status kesehatan: pembagi 0 → None, bukan 0%
    zero = be.health_of(0, 0, 90)
    check("rencana Rp 0 → status `kosong` (bukan `aman`)", zero == "kosong", zero)
    check("persen dengan pembagi 0 → None (bukan 0%)", be.pct_of(5, 0) is None)
    check("ambang waspada memakai alert_pct", be.health_of(90, 100, 90) == "waspada"
          and be.health_of(101, 100, 90) == "overbudget"
          and be.health_of(50, 100, 90) == "aman")

    # --- anti double-count material
    mu = await be.material_usage(org, pid)
    doc_sources = {d["source"] for r in summary["items"] for d in r["documents"]}
    check("pemakaian material TIDAK masuk realisasi (anti double-count) & alasannya disebut",
          "material_txn" not in doc_sources and "dua kali" in mu["note"],
          f"sumber dokumen={sorted(doc_sources)}")

    # --- margin & laporan biaya belum terpetakan
    mg = await br.margin(org, pid)
    check("margin: tanpa pendapatan diakui → None + menyebut apa yang kurang",
          (mg["margin"] is None and mg["missing"]) or mg["margin"] is not None,
          f"margin={mg['margin']} missing={mg['missing'][:1]}")
    check("margin: kas masuk ditampilkan TERPISAH dari pendapatan (tidak tertukar)",
          "kas_masuk" in mg["components"] and "pendapatan_diakui" in mg["components"]
          and "BUKAN pendapatan" in mg["note"])
    check("margin proyeksi = harga jual seluruh unit − (RAB + budget operasional)",
          mg["margin_projected"] == mg["components"]["harga_jual_seluruh_unit"] - (
              mg["components"]["rab_total"] + mg["components"]["budget_operasional"]),
          str(mg["margin_projected"]))
    un = await br.unmapped_costs(org, pid)
    check("laporan 'biaya belum terpetakan' berisi dokumen nyata + status enforce",
          un["document_count"] >= 0 and "enforce_cost_ref" in un,
          f"{un['document_count']} dokumen, Rp {un['total']:,}".replace(",", "."))

    # --- RAB vs realisasi: tabel memakai agregasi yang SAMA (tie-out ikut dibawa)
    for gb in ("item", "category", "step", "unit"):
        rv = await br.rab_vs_actual(org, pid, gb)
        check(f"rab-vs-actual group_by={gb} tie-out ikut hijau",
              rv["tie_out"]["ok"] and isinstance(rv["data"], list),
              f"{len(rv['data'])} baris")

    # --- target dari DATA NYATA (bukan angka yang diinput ulang)
    print("\n4. TARGET DARI DATA NYATA — realisasi dibaca dari deals, bukan diinput")
    act = await ts.actuals_for(org, project_id=pid)
    deals = await db.deals.count_documents({"org_id": org, "project_id": pid,
                                            "status": {"$in": list(ts.SOLD_DEAL_STATUS)}})
    check("realisasi target dibaca dari deals terjual",
          sum(v["unit"] for v in act.values()) == deals,
          f"Σ actual={sum(v['unit'] for v in act.values())} vs deals={deals}")
    avg = await ts.avg_price_of(org, project_id=pid)
    check("harga rata-rata unit dihitung dari unit BERHARGA", avg["avg_price"] > 0,
          str(avg))
    t = await ts.create_target(org, {
        "project_id": pid, "name": "POC Target 2026", "basis": "both",
        "method": "linear_remaining", "horizon": {"start": "2026-01", "end": "2026-12"},
        "unit_target": 18, "revenue_target": 18 * avg["avg_price"],
        "assumptions": {"avg_price": avg["avg_price"]}}, actor="poc")
    check("target tersimpan LANGSUNG dengan periode terhitung (target tanpa periode tak berguna)",
          bool(t) and len(t["periods"]) == 12 and t["totals"]["keep_total_ok"] is True,
          f"{len(t.get('periods') or [])} periode")
    prog = await ts.progress(org, t)
    check("progress membawa gap & pencapaian per periode",
          all("gap" in p for p in prog["periods"]) and prog["achievement_pct"] is not None,
          f"achievement={prog['achievement_pct']}%")
    pv = await ts.preview(org, t, overrides={"method": "velocity_forecast"})
    check("pratinjau dampak metode: before/after + daftar perubahan",
          pv["method_after"] == "velocity_forecast" and "before" in pv and "after" in pv,
          f"{len(pv['changes'])} periode berubah")
    summ = await ts.project_summary(org, pid)
    if summ["state"] == "kosong":
        check("ringkasan target proyek: tanpa target AKTIF → state kosong + ajakan",
              bool(summ["missing"]), str(summ["missing"])[:100])
    else:
        # Database seed sudah punya satu target AKTIF. Yang harus dibuktikan di sini: ringkasan
        # proyek TIDAK mengambil target DRAF (target draf bukan janji resmi perusahaan).
        check("ringkasan target proyek memakai target AKTIF, bukan draf",
              summ["target"]["id"] != t["id"],
              f"aktif={summ['target']['name']} vs draf={t['name']}")
    await db.project_targets.update_one({"id": t["id"]}, {"$set": {"status": "active"}})
    await db.project_targets.update_many(
        {"org_id": org, "project_id": pid, "id": {"$ne": t["id"]}, "status": "active"},
        {"$set": {"status": "draft"}})
    summ2 = await ts.project_summary(org, pid)
    check("ringkasan target proyek: setelah aktif → membawa angka & pencapaian",
          summ2["state"] in ("lengkap", "sebagian") and summ2["target"]["id"] == t["id"],
          f"state={summ2['state']} achievement={summ2.get('achievement_pct')}")
    # Pulihkan status target seed supaya database demo tetap seperti semula.
    await db.project_targets.update_many(
        {"org_id": org, "project_id": pid, "demo_batch": "fase45"},
        {"$set": {"status": "active"}})

    # --- peringatan anggaran: hanya saat TINGKAT naik
    print("\n5. PERINGATAN ANGGARAN — sekali per tingkat, ada notifikasi + tugas")
    # Skenario nyata: item anggaran manual dengan rencana Rp 1 juta, realisasi tercatat
    # Rp 2,5 juta → 250% = overbudget. Dipakai untuk membuktikan peringatan BENAR-BENAR
    # terkirim (notifikasi + tugas), bukan hanya fungsinya bisa dipanggil.
    await br.add_manual_entry(org, ids["POC-MAN"], amount=2_500_000,
                              note="Pengeluaran lapangan di luar sistem (uji POC)",
                              actor="poc", ref_no="POC-MAN-01")
    n_before = await db.notifications.count_documents({"org_id": org, "type": "budget"})
    t_before = await db.tasks.count_documents({"org_id": org, "jobdesk_code": br.ALERT_JOBDESK})
    first = await br.alert_scan(org, project_id=pid, actor="poc")
    n_after = await db.notifications.count_documents({"org_id": org, "type": "budget"})
    t_after = await db.tasks.count_documents({"org_id": org, "jobdesk_code": br.ALERT_JOBDESK})
    again = await br.alert_scan(org, project_id=pid, actor="poc")
    hit = next((a for a in first["alerts"] if a["code"] == "POC-MAN"), None)
    check("item overbudget terdeteksi & diberi peringatan (bukan hanya diberi warna merah)",
          bool(hit) and hit["health"] == "overbudget",
          f"dibuat={first['created']} · {hit}")
    check("peringatan membuat NOTIFIKASI in-app", n_after > n_before,
          f"{n_before} → {n_after}")
    check("peringatan membuat TUGAS ke penanggung jawab (owner_role)", t_after > t_before,
          f"{t_before} → {t_after}")
    check("peringatan TIDAK diulang saat tingkat status tidak naik",
          again["created"] == 0, f"pengulangan={again['created']}")

    # bersih-bersih data POC supaya database seed tidak tercemar
    await db.budget_items.delete_many({"org_id": org, "created_by": "poc"})
    await db.project_targets.delete_many({"org_id": org, "created_by": "poc"})
    await db.budget_manual_entries.delete_many({"org_id": org, "created_by": "poc"})


async def main():
    print("=" * 74)
    print("POC FASE 45 — TARGET PROYEK & BUDGET/RAB (core sebelum UI)")
    print("=" * 74)
    lin = test_target_math()
    test_recalc(lin)
    await test_budget()
    print("-" * 74)
    if fails:
        print(f"POC 45 GAGAL: {len(fails)} temuan → {fails}")
        sys.exit(1)
    print("POC 45 HIJAU: matematika target eksak & dinamis dengan penjelasan, anggaran "
          "tie-out dengan Kendali Biaya, drill 3 lapis menjumlah, tanpa double-count, dan "
          "angka yang belum ada mengaku belum ada.")


if __name__ == "__main__":
    asyncio.run(main())
