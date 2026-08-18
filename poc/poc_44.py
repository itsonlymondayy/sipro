#!/usr/bin/env python3
"""poc_44.py — POC WAJIB Fase 44 (Analitik & BI): membuktikan lapisan metrik JUJUR & COCOK.

Yang paling rawan gagal pada pekerjaan BI bukan grafiknya, tetapi ANGKANYA: begitu dashboard
menghitung ulang dengan rumusnya sendiri, angka di BI mulai berbeda dengan angka di halaman
operasional — dan sejak itu tidak ada yang percaya keduanya. POC ini membuktikan lima hal
sebelum satu piksel UI dibangun:

  1. KONTRAK  : setiap metrik mengembalikan bentuk baku (value/complete/missing/coverage/
                inputs/breakdown/drill) dan TIDAK PERNAH mengirim angka saat inputnya tidak
                ada (aturan "0 ≠ belum ada data").
  2. TIE-OUT  : metrik marketing SAMA DENGAN `/api/ads/performance` (sumber yang sudah dipakai
                layar Kampanye), bukan hitungan kedua.
  3. TIE-OUT  : metrik penjualan & kas SAMA DENGAN hitungan langsung atas koleksi mentah
                (units/deals/receipts/ar_invoices/journal_entries) — dihitung ulang di sini
                dengan cara yang independen.
  4. TIE-OUT  : funnel lead dihitung dari `stage_history` dan cakupannya dilaporkan apa adanya
                (lead tanpa riwayat tidak boleh dianggap "tidak pernah lolos tahap").
  5. DRILL    : setiap metrik menunjuk rute daftar yang BENAR-BENAR ADA di `App.js`.

Jalankan: `python3 poc/poc_44.py` (butuh backend + Mongo hidup). Exit != 0 bila ada yang gagal.
"""
import asyncio
import os
import pathlib
import re
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

ROOT = pathlib.Path("/app")
load_dotenv(ROOT / "backend" / ".env")

import ads_report as rep  # noqa: E402
import metrics  # noqa: E402
from db import ORG_ID, db  # noqa: E402
from metrics.base import PERSONAS, UNITS  # noqa: E402

fails = []
RANGE = {"date_from": "2026-01-01", "date_to": "2026-12-31"}


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)
    return bool(cond)


async def test_contract():
    print("\n1. KONTRAK — setiap metrik menepati bentuk baku & tidak mengarang angka")
    app_routes = set(re.findall(r'<Route\s+path="([^"]+)"',
                                (ROOT / "frontend/src/App.js").read_text()))
    check("kamus metrik terisi", len(metrics.REGISTRY) >= 40, f"{len(metrics.REGISTRY)} metrik")
    persona_count = {}
    for code, spec in metrics.REGISTRY.items():
        persona_count[spec["persona"]] = persona_count.get(spec["persona"], 0) + 1
    check("kelima persona dashboard punya metrik",
          set(persona_count) == set(PERSONAS), f"{persona_count}")
    results = await metrics.compute_many(list(metrics.REGISTRY), **RANGE, org_id=ORG_ID)
    bad_shape, lying, bad_unit, bad_drill, no_label = [], [], [], [], []
    for code, res in results.items():
        spec = metrics.REGISTRY[code]
        for key in ("code", "value", "unit", "complete", "missing", "coverage", "inputs",
                    "breakdown", "series", "note", "drill"):
            if key not in res:
                bad_shape.append(f"{code}:{key}")
        if res.get("unit") not in UNITS:
            bad_unit.append(f"{code}={res.get('unit')}")
        # ATURAN INTI: input tidak ada (missing) & bukan sebagian (coverage None) -> value None
        if res.get("missing") and res.get("coverage") is None and res.get("value") is not None:
            lying.append(f"{code}={res.get('value')} missing={res['missing'][:1]}")
        if not res.get("label"):
            no_label.append(code)
        drill = spec.get("drill")
        if drill and drill.split("?")[0] not in app_routes:
            bad_drill.append(f"{code}->{drill}")
    check("bentuk hasil metrik lengkap", not bad_shape, f"{bad_shape[:5]}")
    check("satuan metrik dari daftar sah", not bad_unit, f"{bad_unit[:5]}")
    check("TIDAK ADA metrik yang mengirim angka tanpa input (0 ≠ belum ada data)",
          not lying, f"{lying[:5]}")
    check("setiap metrik punya nama untuk layar", not no_label, f"{no_label[:5]}")
    check("setiap drill-down menunjuk rute yang ada di App.js", not bad_drill, f"{bad_drill[:5]}")
    incomplete = [c for c, r in results.items() if not r["complete"]]
    print(f"       (peta kekosongan data: {len(incomplete)} metrik mengaku belum lengkap "
          f"— {incomplete[:6]})")
    return results


async def test_marketing_tieout(results):
    print("\n2. TIE-OUT MARKETING — angka BI = angka halaman Kampanye (bukan hitungan kedua)")
    perf = await rep.campaign_performance(org_id=ORG_ID, **RANGE)
    totals = perf["totals"]
    mkt1 = results["MKT-01"]
    check("biaya iklan BI = total biaya laporan kampanye",
          mkt1["value"] == totals["spend"], f"{mkt1['value']} vs {totals['spend']}")
    mkt3 = results["MKT-03"]
    check("ROAS BI = ROAS laporan kampanye (termasuk sama-sama null bila biaya belum lengkap)",
          mkt3["value"] == totals.get("roas"), f"{mkt3['value']} vs {totals.get('roas')}")
    attrib = await rep.attribution(org_id=ORG_ID, level="campaign", **RANGE)
    mkt4 = results["MKT-04"]
    mix_leads = sum(int(r.get("leads") or 0) for r in mkt4["breakdown"])
    check("campuran kanal BI = total lead laporan atribusi",
          mix_leads == attrib["totals"]["leads"],
          f"{mix_leads} vs {attrib['totals']['leads']}")
    cpl = results["LED-09"]
    spend_rows = await db.ad_spend.find({"org_id": ORG_ID}, {"_id": 0, "spend": 1}).to_list(20000)
    spend_manual = sum(int(r["spend"]) for r in spend_rows)
    check("CPL memakai biaya iklan yang sama dengan jumlah baris biaya di database",
          cpl["inputs"]["biaya"] == spend_manual,
          f"{cpl['inputs']['biaya']} vs {spend_manual}")


async def test_sales_tieout(results):
    print("\n3. TIE-OUT PENJUALAN & KAS — dihitung ulang langsung dari koleksi mentah")
    units = await db.units.find({"org_id": ORG_ID}, {"_id": 0, "status": 1, "price": 1}).to_list(5000)
    sold = len([u for u in units if u.get("status") in ("booked", "sold")])
    check("SLS-01 unit terjual = hitung ulang dari koleksi units",
          results["SLS-01"]["value"] == sold, f"{results['SLS-01']['value']} vs {sold}")
    check("SLS-02 absorpsi = terjual/total (dibulatkan 1 desimal)",
          results["SLS-02"]["value"] == round(sold / len(units) * 100, 1) if units else True,
          f"{results['SLS-02']['value']}")
    deals = await db.deals.find({"org_id": ORG_ID,
                                 "status": {"$in": ["reserved", "booked", "completed"]}},
                                {"_id": 0, "price": 1}).to_list(5000)
    nilai = sum(int(d.get("price") or 0) for d in deals)
    check("SLS-03 nilai penjualan = Σ harga deal aktif",
          results["SLS-03"]["value"] == nilai, f"{results['SLS-03']['value']} vs {nilai}")
    receipts = await db.receipts.find({"org_id": ORG_ID}, {"_id": 0, "amount": 1}).to_list(5000)
    kas = sum(int(r.get("amount") or 0) for r in receipts)
    check("SLS-05 kas masuk = Σ kuitansi", results["SLS-05"]["value"] == kas,
          f"{results['SLS-05']['value']} vs {kas}")
    # AR: yang dihitung HANYA termin yang sudah lewat tanggal — dihitung ulang di sini.
    invs = await db.ar_invoices.find({"org_id": ORG_ID}, {"_id": 0, "items": 1}).to_list(5000)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    overdue = 0
    for inv in invs:
        for item in inv.get("items") or []:
            sisa = int(item.get("amount") or 0) - int(item.get("paid_amount") or 0)
            if sisa > 0 and item.get("due_date") and item["due_date"] < now:
                overdue += sisa
    check("SLS-06 piutang jatuh tempo = Σ termin lewat tanggal (bukan seluruh sisa tagihan)",
          results["SLS-06"]["value"] == overdue,
          f"{results['SLS-06']['value']} vs {overdue}")
    outstanding = results["SLS-06"]["inputs"]["outstanding_total"]
    check("total sisa piutang DIBEDAKAN dari yang jatuh tempo (tidak dilebih-lebihkan)",
          outstanding >= results["SLS-06"]["value"],
          f"sisa {outstanding} >= jatuh tempo {results['SLS-06']['value']}")
    jes = await db.journal_entries.find({"org_id": ORG_ID}, {"_id": 0, "lines": 1}).to_list(20000)
    rev = sum(int(line.get("credit") or 0) - int(line.get("debit") or 0)
              for je in jes for line in je.get("lines") or []
              if line.get("account_type") == "revenue")
    check("SLS-04 pendapatan diakui = Σ (kredit-debit) akun revenue di buku besar",
          results["SLS-04"]["value"] == rev, f"{results['SLS-04']['value']} vs {rev}")


async def test_leads_tieout(results):
    print("\n4. TIE-OUT LEAD — funnel dari riwayat tahap + cakupan dilaporkan apa adanya")
    leads = await db.leads.find({"org_id": ORG_ID}, {"_id": 0, "stage": 1, "stage_history": 1,
                                                    "created_at": 1}).to_list(50000)
    check("LED-01 lead masuk = jumlah lead pada rentang",
          results["LED-01"]["value"] == len(leads),
          f"{results['LED-01']['value']} vs {len(leads)}")
    tanpa_riwayat = len([l for l in leads if not l.get("stage_history")])
    conv = results["LED-02"]
    check("LED-02 melaporkan lead tanpa riwayat sebagai cakupan yang belum penuh",
          (conv["coverage"] or {}).get("rows") == len(leads) - tanpa_riwayat,
          f"coverage={conv['coverage']} tanpa_riwayat={tanpa_riwayat}")
    # Hitung ulang: berapa lead yang PERNAH mencapai 'appointment'
    def reached(lead, stage):
        if lead.get("stage") == stage:
            return True
        return any(h.get(key) == stage for h in (lead.get("stage_history") or [])
                   for key in ("from", "to", "stage"))
    manual = len([l for l in leads if reached(l, "appointment")])
    step = next((s for s in conv["breakdown"] if s["key"] == "nurturing->appointment"), {})
    check("LED-02 jumlah lead yang pernah mencapai 'appointment' = hitung ulang manual",
          step.get("to_count") == manual, f"{step.get('to_count')} vs {manual}")
    won = len([l for l in leads if l.get("stage") in ("booking", "won")])
    lost = len([l for l in leads if l.get("stage") == "lost"])
    expected = round(won / (won + lost) * 100, 1) if (won + lost) else None
    check("LED-07 win rate = menang/(menang+hilang) hitung ulang",
          results["LED-07"]["value"] == expected,
          f"{results['LED-07']['value']} vs {expected}")
    demo = results["LED-12"]
    check("LED-12 demografi mengaku BELUM ADA (bukan 0%)",
          demo["value"] is None and demo["missing"], f"{demo['missing']}")
    vel = results["LED-04"]
    check("LED-04 velocity dihitung dari riwayat, bukan dari field stage_durations yang kosong",
          vel["inputs"]["lead_berriwayat"] == len(leads) - tanpa_riwayat,
          f"{vel['inputs']}")


async def test_project_team(results):
    print("\n5. PROYEK & TIM — realisasi biaya hanya dari yang bisa ditautkan")
    items = await db.build_items.find({"org_id": ORG_ID},
                                      {"_id": 0, "status": 1, "weight": 1}).to_list(50000)
    total_w = sum(float(i.get("weight") or 0) for i in items)
    done_w = sum(float(i.get("weight") or 0) for i in items
                 if i.get("status") in ("verified", "done", "selesai"))
    expected = round(done_w / total_w * 100, 1) if total_w else None
    check("PRJ-01 progres = Σ bobot selesai / Σ bobot (berbobot, bukan rata-rata sederhana)",
          results["PRJ-01"]["value"] == expected, f"{results['PRJ-01']['value']} vs {expected}")
    prj3 = results["PRJ-03"]
    check("PRJ-03 melaporkan anggaran yang BELUM TERTAUT ke langkah jadwal",
          "unmapped_budget" in prj3["inputs"], f"{prj3['inputs']}")
    prj7 = results["PRJ-07"]
    check("PRJ-07 margin TIDAK dihitung setengah lalu disebut margin",
          prj7["value"] is None and prj7["missing"], f"{prj7['missing']}")
    tasks_done = await db.tasks.count_documents({"org_id": ORG_ID,
                                                 "status": {"$in": ["done", "completed",
                                                                    "verified"]}})
    usr1 = results["USR-01"]
    check("USR-01 memakai jejak nyata (aktivitas + tugas selesai)",
          usr1["inputs"]["tugas_selesai"] == tasks_done,
          f"{usr1['inputs']['tugas_selesai']} vs {tasks_done}")
    usr2 = results["USR-02"]
    check("USR-02 hanya menilai tugas yang punya tenggat (sisanya dilaporkan)",
          usr2["inputs"]["dinilai"] <= usr2["inputs"]["tugas_selesai"], f"{usr2['inputs']}")


async def test_recompute_stability(results):
    print("\n6. BISA DIHITUNG ULANG — dua kali hitung memberi angka yang sama (uji Dok 31 §9.2)")
    ulang = await metrics.compute_many(["SLS-01", "SLS-03", "SLS-05", "LED-01", "LED-07",
                                        "MKT-01", "PRJ-01", "USR-02"], **RANGE, org_id=ORG_ID)
    beda = [c for c, r in ulang.items() if r["value"] != results[c]["value"]]
    check("perhitungan ulang menghasilkan angka identik", not beda, f"{beda}")


async def main():
    print("=" * 78)
    print("POC FASE 44 — LAPISAN METRIK BI (kontrak + tie-out + kejujuran angka)")
    print("=" * 78)
    results = await test_contract()
    await test_marketing_tieout(results)
    await test_sales_tieout(results)
    await test_leads_tieout(results)
    await test_project_team(results)
    await test_recompute_stability(results)
    print("-" * 78)
    if fails:
        print(f"POC GAGAL: {len(fails)} temuan — {fails[:8]}")
        sys.exit(1)
    print("POC HIJAU: kontrak metrik dipatuhi, angka BI cocok dengan sumbernya, dan metrik "
          "tanpa data mengaku belum lengkap (tidak mengarang 0).")


if __name__ == "__main__":
    asyncio.run(main())
