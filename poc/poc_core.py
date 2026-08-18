"""
SIPRO POC CORE — membuktikan bagian TERSULIT bekerja sebelum membangun aplikasi.
Mengacu Dok 17 §2.2 (POC core) + Dok 12/13/15 (state machine, engine, finance).

Menguji SEKALIGUS (clean-room di database 'sipro_poc'):
  1. Event Bus (outbox) + Guided Work Engine (idempotent via source_event) + Expiry Sweeper
  2. Atomic booking konkuren (find_one_and_update) — anti double-booking
  3. Automation Rule (pesan 'harga' -> task/NBA)  [REBUILD auto_followup jadi nyata]
  4. RevRec math (receipt -> contract_liability naik; BAST -> revenue+COGS, liability -> 0)  [PSAK 72]
  5. Document + PDF (PPJB dgn guard prasyarat -> finalize -> sign -> PDF reportlab)
  6. WA/Ads webhook (SIMULASI) -> lead/conversation + task 'Hubungi <=5 menit' + dedup

Jalankan: python /app/poc/poc_core.py
Exit code 0 = semua lulus; !=0 = ada yang gagal.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# reportlab (PDF)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

load_dotenv("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
POC_DB = "sipro_poc"

client = AsyncIOMotorClient(MONGO_URL)
db = client[POC_DB]

# ----------------------------- helpers -----------------------------
def now() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.isoformat()

def new_id() -> str:
    return str(uuid.uuid4())

ORG = "org-poc"

# ----------------------------- Event Bus (outbox) -----------------------------
async def emit(etype: str, entity_type: str, entity_id: str, data: dict):
    await db.events.insert_one({
        "id": new_id(), "org_id": ORG, "type": etype,
        "entity_type": entity_type, "entity_id": entity_id,
        "data": data, "status": "pending", "created_at": iso(now()),
    })

# Guided Work Engine — idempotent task creation via source_event
async def create_task(source_event: str, title: str, ttype: str, related_type: str,
                      related_id: str, assignee: str, sla_minutes: int | None = None):
    existing = await db.tasks.find_one({"org_id": ORG, "source_event": source_event,
                                        "status": {"$in": ["open", "in_progress"]}})
    if existing:
        return existing["id"]  # idempotent: skip duplicate
    tid = new_id()
    doc = {
        "id": tid, "org_id": ORG, "title": title, "type": ttype, "status": "open",
        "priority": "urgent" if sla_minutes else "medium",
        "related_entity_type": related_type, "related_entity_id": related_id,
        "assigned_to": assignee, "source_event": source_event, "auto_generated": True,
        "created_at": iso(now()),
    }
    if sla_minutes is not None:
        doc["sla_due_at"] = iso(now() + timedelta(minutes=sla_minutes))
    await db.tasks.insert_one(doc)
    return tid

# Event handlers (registry) ------------------------------------------------
async def h_lead_created(ev):
    lead = await db.leads.find_one({"id": ev["entity_id"]})
    await create_task(f"lead.created:{ev['entity_id']}", "Hubungi lead baru", "contact",
                      "lead", ev["entity_id"], lead.get("assigned_to", "system"), sla_minutes=5)

async def h_lead_captured(ev):
    lead = await db.leads.find_one({"id": ev["entity_id"]})
    await create_task(f"lead.captured:{ev['entity_id']}", "Hubungi lead (<=5 menit)", "contact",
                      "lead", ev["entity_id"], lead.get("assigned_to", "system"), sla_minutes=5)

async def h_message_received(ev):
    # Automation rule engine: keyword -> suggestion task (human-in-the-loop)
    rules = await db.automation_rules.find({"org_id": ORG, "is_active": True,
                                            "trigger.event": "message.received"}).to_list(100)
    body = (ev["data"].get("body") or "").lower()
    conv_id = ev["entity_id"]
    conv = await db.conversations.find_one({"id": conv_id})
    for r in rules:
        kws = r["trigger"].get("keywords", [])
        if any(k in body for k in kws):
            await create_task(f"automation:{r['id']}:{conv_id}",
                              f"Tindak lanjut intent '{kws[0]}' (usulan)", "follow_up",
                              "conversation", conv_id, conv.get("owner", "system"))
            await db.automation_rules.update_one({"id": r["id"]}, {"$inc": {"executions": 1}})

async def h_unit_bast(ev):
    # RevRec (PSAK 72): recognize revenue+COGS at BAST, zero out contract liability
    deal_id = ev["data"]["deal_id"]
    deal = await db.deals.find_one({"id": deal_id})
    cl = await db.contract_liabilities.find_one({"deal_id": deal_id})
    revenue = deal["price"]
    cogs = ev["data"].get("cogs", int(revenue * 0.7))
    await db.revenue_recognitions.insert_one({
        "id": new_id(), "org_id": ORG, "deal_id": deal_id, "unit_id": deal["unit_id"],
        "revenue": revenue, "cogs": cogs, "recognized_at": iso(now()),
    })
    if cl:
        await db.contract_liabilities.update_one({"id": cl["id"]}, {"$set": {"balance": 0}})

HANDLERS = {
    "lead.created": [h_lead_created],
    "lead.captured": [h_lead_captured],
    "message.received": [h_message_received],
    "unit.bast": [h_unit_bast],
}

async def dispatch_pending():
    """Dispatcher tick — proses outbox events (idempotent, aman diulang)."""
    processed = 0
    pending = await db.events.find({"org_id": ORG, "status": "pending"}).sort("created_at", 1).to_list(500)
    for ev in pending:
        for handler in HANDLERS.get(ev["type"], []):
            await handler(ev)
        await db.events.update_one({"id": ev["id"]}, {"$set": {"status": "dispatched",
                                                               "dispatched_at": iso(now())}})
        processed += 1
    return processed

# Scheduler job (dipanggil langsung di POC) --------------------------------
async def sweep_expired_reservations():
    """Deal draft/reserved dgn reserved_until < now -> expired; unit -> available."""
    expired = 0
    cur = await db.deals.find({"org_id": ORG, "status": {"$in": ["draft", "reserved"]}}).to_list(1000)
    for d in cur:
        ru = d.get("reserved_until")
        if ru and ru < iso(now()):
            await db.deals.update_one({"id": d["id"]}, {"$set": {"status": "expired"}})
            await db.units.update_one({"id": d["unit_id"]}, {"$set": {"status": "available"}})
            expired += 1
    return expired

# Atomic booking -----------------------------------------------------------
async def book_unit_atomic(unit_id: str, deal_id: str):
    """find_one_and_update: hanya sukses jika unit masih 'available'."""
    res = await db.units.find_one_and_update(
        {"id": unit_id, "status": "available"},
        {"$set": {"status": "booked", "booked_by_deal": deal_id, "updated_at": iso(now())}},
    )
    return res is not None  # True bila deal ini yang berhasil mengunci unit

# Finance: apply receipt --------------------------------------------------
async def apply_receipt(deal_id: str, amount: int):
    cl = await db.contract_liabilities.find_one({"deal_id": deal_id})
    if not cl:
        await db.contract_liabilities.insert_one({"id": new_id(), "org_id": ORG,
                                                  "deal_id": deal_id, "balance": amount})
    else:
        await db.contract_liabilities.update_one({"id": cl["id"]}, {"$inc": {"balance": amount}})

# Document engine ----------------------------------------------------------
def resolve_variables(content: str, ctx: dict) -> str:
    out = content
    for k, v in ctx.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out

async def create_ppjb_document(deal_id: str, progress_pct: int, ctx: dict):
    """Guard prasyarat PPJB: butuh construction_progress >= 20%."""
    if progress_pct < 20:
        raise ValueError("PPJB ditolak: progres konstruksi < 20% (prasyarat belum terpenuhi)")
    tpl = await db.document_templates.find_one({"org_id": ORG, "code": "PPJB"})
    content = resolve_variables(tpl["content"], ctx)
    doc_id = new_id()
    year = now().year
    seq = await db.documents.count_documents({"org_id": ORG, "template_code": "PPJB"}) + 1
    await db.documents.insert_one({
        "id": doc_id, "org_id": ORG, "template_id": tpl["id"], "template_code": "PPJB",
        "doc_number": f"PPJB/{year}/{seq:04d}", "deal_id": deal_id, "content": content,
        "status": "draft", "signatures": [], "created_at": iso(now()),
    })
    return doc_id

async def finalize_document(doc_id: str):
    await db.documents.update_one({"id": doc_id, "status": "draft"},
                                  {"$set": {"status": "finalized", "finalized_at": iso(now())}})

async def sign_document(doc_id: str, role: str, name: str):
    await db.documents.update_one({"id": doc_id, "status": {"$in": ["finalized", "signed"]}},
        {"$push": {"signatures": {"role": role, "name": name, "signed_at": iso(now())}},
         "$set": {"status": "signed", "first_signed_at": iso(now())}})

def build_pdf(doc_content: str, doc_number: str, out_path: str):
    doct = SimpleDocTemplate(out_path, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = [Paragraph(f"<b>SIPRO — {doc_number}</b>", styles["Title"]), Spacer(1, 12)]
    for line in doc_content.split("\n"):
        flow.append(Paragraph(line if line.strip() else "&nbsp;", styles["Normal"]))
        flow.append(Spacer(1, 4))
    doct.build(flow)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

# Webhook simulation (Ads/WA) ---------------------------------------------
async def process_lead_capture(provider: str, payload: dict):
    """Dedup by phone; create lead + conversation + emit lead.captured."""
    phone = payload["phone"]
    dedup_key = f"{provider}:{phone}"
    existing_evt = await db.lead_capture_events.find_one({"org_id": ORG, "dedup_key": dedup_key})
    if existing_evt:
        return existing_evt.get("lead_id"), True  # duplicate
    lead_id = new_id()
    await db.leads.insert_one({
        "id": lead_id, "org_id": ORG, "name": payload.get("name", "Lead"),
        "phone": phone, "source": provider, "stage": "acquisition",
        "campaign": payload.get("campaign"), "assigned_to": "sales@poc",
        "created_at": iso(now()),
    })
    conv_id = new_id()
    await db.conversations.insert_one({
        "id": conv_id, "org_id": ORG, "channel": "whatsapp", "contact_phone": phone,
        "lead_id": lead_id, "owner": "sales@poc", "status": "new",
        "window_expires_at": iso(now() + timedelta(hours=24)), "created_at": iso(now()),
    })
    await db.lead_capture_events.insert_one({
        "id": new_id(), "org_id": ORG, "provider": provider, "dedup_key": dedup_key,
        "status": "processed", "lead_id": lead_id, "raw_payload": payload,
        "created_at": iso(now()),
    })
    await emit("lead.captured", "lead", lead_id, {"provider": provider})
    return lead_id, False

# ----------------------------- TESTS -----------------------------
results = []
def record(name, passed, detail=""):
    results.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

async def test_1_event_engine():
    lead_id = new_id()
    await db.leads.insert_one({"id": lead_id, "org_id": ORG, "name": "Budi", "phone": "+628111",
                               "stage": "acquisition", "assigned_to": "sales@poc", "created_at": iso(now())})
    # emit SAME event twice -> idempotent
    await emit("lead.created", "lead", lead_id, {})
    await emit("lead.created", "lead", lead_id, {})
    await dispatch_pending()
    await dispatch_pending()  # run twice to prove dispatcher is safe to repeat
    cnt = await db.tasks.count_documents({"org_id": ORG, "source_event": f"lead.created:{lead_id}"})
    ok_idem = (cnt == 1)
    # expiry sweeper
    unit_id = new_id(); deal_id = new_id()
    await db.units.insert_one({"id": unit_id, "org_id": ORG, "status": "reserved"})
    await db.deals.insert_one({"id": deal_id, "org_id": ORG, "unit_id": unit_id, "status": "reserved",
                               "reserved_until": iso(now() - timedelta(minutes=1)), "price": 500_000_000})
    swept = await sweep_expired_reservations()
    deal_after = await db.deals.find_one({"id": deal_id})
    unit_after = await db.units.find_one({"id": unit_id})
    ok_sweep = (deal_after["status"] == "expired" and unit_after["status"] == "available" and swept >= 1)
    record("1. Event Bus + Guided Work Engine (idempotent)", ok_idem, f"tasks utk 2 event identik = {cnt} (harus 1)")
    record("1b. Expiry sweeper (deal->expired, unit->available)", ok_sweep,
           f"deal={deal_after['status']}, unit={unit_after['status']}")

async def test_2_atomic_booking():
    unit_id = new_id()
    await db.units.insert_one({"id": unit_id, "org_id": ORG, "status": "available"})
    # dua booking paralel pada unit yang sama
    r1, r2 = await asyncio.gather(book_unit_atomic(unit_id, "dealA"),
                                  book_unit_atomic(unit_id, "dealB"))
    ok = ([r1, r2].count(True) == 1)  # tepat satu sukses
    unit_after = await db.units.find_one({"id": unit_id})
    record("2. Atomic booking konkuren (anti double-booking)", ok,
           f"sukses={[r1, r2].count(True)} (harus 1), unit={unit_after['status']}")

async def test_3_automation_rule():
    await db.automation_rules.insert_one({
        "id": new_id(), "org_id": ORG, "name": "Intent Harga", "is_active": True,
        "trigger": {"event": "message.received", "keywords": ["harga", "kpr", "survey"]},
        "actions": [{"type": "create_task"}], "require_confirmation": True, "executions": 0})
    conv_id = new_id()
    await db.conversations.insert_one({"id": conv_id, "org_id": ORG, "channel": "whatsapp",
                                       "owner": "sales@poc", "status": "active", "created_at": iso(now())})
    await emit("message.received", "conversation", conv_id, {"body": "Halo, berapa HARGA unitnya?"})
    await dispatch_pending()
    task = await db.tasks.find_one({"org_id": ORG, "source_event": {"$regex": f"automation:.*:{conv_id}"}})
    record("3. Automation rule (keyword 'harga' -> task/NBA)", task is not None,
           "task usulan terbuat" if task else "tidak ada task")

async def test_4_revrec():
    deal_id = new_id(); unit_id = new_id()
    await db.deals.insert_one({"id": deal_id, "org_id": ORG, "unit_id": unit_id, "status": "booked",
                               "price": 800_000_000})
    await apply_receipt(deal_id, 100_000_000)  # DP
    await apply_receipt(deal_id, 50_000_000)   # cicilan
    cl_before = await db.contract_liabilities.find_one({"deal_id": deal_id})
    ok_liab = (cl_before["balance"] == 150_000_000)  # penerimaan = contract liability (BUKAN revenue)
    rev_before = await db.revenue_recognitions.count_documents({"deal_id": deal_id})
    # BAST -> recognize
    await emit("unit.bast", "unit", unit_id, {"deal_id": deal_id})
    await dispatch_pending()
    cl_after = await db.contract_liabilities.find_one({"deal_id": deal_id})
    rr = await db.revenue_recognitions.find_one({"deal_id": deal_id})
    ok = (ok_liab and rev_before == 0 and rr is not None and rr["revenue"] == 800_000_000
          and cl_after["balance"] == 0)
    record("4. RevRec PSAK 72 (liability sblm BAST; revenue@BAST; liability->0)", ok,
           f"liab_sblm={cl_before['balance']:,}, revenue={rr['revenue'] if rr else 0:,}, liab_stlh={cl_after['balance']:,}")

async def test_5_document_pdf():
    await db.document_templates.insert_one({
        "id": new_id(), "org_id": ORG, "code": "PPJB", "name": "PPJB Standar",
        "content": "PERJANJIAN PENGIKATAN JUAL BELI\nPembeli: {{buyer_name}}\nUnit: {{unit_label}}\nHarga: Rp {{price}}\nTanggal: {{date}}",
        "is_active": True})
    ctx = {"buyer_name": "Ibu Dewi", "unit_label": "A-12", "price": "800.000.000", "date": "2026-07-01"}
    # guard: progress < 20 harus DITOLAK
    guard_ok = False
    try:
        await create_ppjb_document("dealX", 10, ctx)
    except ValueError:
        guard_ok = True
    # progress >= 20 -> lolos
    doc_id = await create_ppjb_document("dealX", 25, ctx)
    await finalize_document(doc_id)
    await sign_document(doc_id, "buyer", "Ibu Dewi")
    await sign_document(doc_id, "seller", "PT SIPRO")
    doc = await db.documents.find_one({"id": doc_id})
    out_path = "/app/poc/_ppjb_test.pdf"
    pdf_ok = build_pdf(doc["content"], doc["doc_number"], out_path)
    ok = (guard_ok and doc["status"] == "signed" and len(doc["signatures"]) == 2 and pdf_ok)
    record("5. Document PPJB (guard prasyarat + finalize + sign + PDF)", ok,
           f"guard_ditolak@10%={guard_ok}, status={doc['status']}, ttd={len(doc['signatures'])}, pdf={pdf_ok}")

async def test_6_webhook_sim():
    payload = {"name": "Andi", "phone": "+628999", "campaign": "cluster-A-meta"}
    lead_id, dup1 = await process_lead_capture("meta_lead_ads", payload)
    await dispatch_pending()  # lead.captured -> task 5 menit
    task = await db.tasks.find_one({"org_id": ORG, "source_event": f"lead.captured:{lead_id}"})
    conv = await db.conversations.find_one({"lead_id": lead_id})
    # dedup: proses payload sama lagi -> tidak buat lead baru
    lead_id2, dup2 = await process_lead_capture("meta_lead_ads", payload)
    lead_cnt = await db.leads.count_documents({"org_id": ORG, "phone": "+628999"})
    ok = (not dup1 and dup2 and lead_cnt == 1 and task is not None and conv is not None
          and task.get("sla_due_at") is not None)
    record("6. WA/Ads webhook (SIMULASI) -> lead+conv+task 5mnt + dedup", ok,
           f"dup_pertama={dup1}, dedup_kedua={dup2}, jml_lead={lead_cnt}, task_5mnt={'ya' if task else 'tidak'}")

async def main():
    print("=" * 70)
    print("SIPRO POC CORE — clean-room DB:", POC_DB)
    print("=" * 70)
    # clean-room
    await client.drop_database(POC_DB)
    for t in (test_1_event_engine, test_2_atomic_booking, test_3_automation_rule,
              test_4_revrec, test_5_document_pdf, test_6_webhook_sim):
        try:
            await t()
        except Exception as e:
            record(t.__name__, False, f"EXCEPTION: {type(e).__name__}: {e}")
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"RINGKASAN: {passed}/{total} lulus")
    print("=" * 70)
    await client.drop_database(POC_DB)  # cleanup
    client.close()
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    asyncio.run(main())
