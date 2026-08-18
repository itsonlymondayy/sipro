"""Customer Portal (EPIC M1): buyer-facing, OTP auth, transparency on
unit/payment/progress/documents + complaint channel with SLA.

Auth is via portal JWT (type='portal'); staff tokens are rejected. OTP is sent
via the WhatsApp provider (simulation reveals the code in dev). A master OTP
(PORTAL_MASTER_OTP, default '000000') is accepted for deterministic testing.
"""
import io
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from db import db, ORG_ID, ORG_NAME
import build_monitor as bm
import p28_utils as p28
import payment_intake as intake
import reference as ref
import storage
from core_utils import new_id, now_iso, serialize_doc, due_in, normalize_phone_e164
from engine import build_s_curve, auto_create_task, create_notification
from pdf_utils import build_document_pdf
from portal_security import create_portal_token, get_portal_user
from notifications import send_whatsapp, gen_otp
from models import PortalOtpRequest, PortalOtpVerify, ComplaintCreate
from models_p47 import PaymentProofIn

router = APIRouter(prefix="/portal", tags=["portal"])


# ----------------------------- helpers -----------------------------
def _norm(ident: str):
    ident = (ident or "").strip()
    if "@" in ident:
        return "email", ident.lower()
    return "phone", normalize_phone_e164(ident)


async def _find_portal_user(ident: str):
    """Find a portal_user by phone/email; auto-provision from a matching customer."""
    kind, val = _norm(ident)
    pu = await db.portal_users.find_one({kind: val}, {"_id": 0})
    if pu:
        return pu
    cust = await db.customers.find_one({kind: val}, {"_id": 0})
    if not cust:
        return None
    ts = now_iso()
    pu = {
        "id": new_id(), "org_id": cust.get("org_id", ORG_ID), "customer_id": cust["id"],
        "name": cust.get("name"), "phone": cust.get("phone"), "email": cust.get("email"),
        "is_active": True, "created_at": ts, "last_login_at": None,
    }
    await db.portal_users.insert_one(dict(pu))
    pu.pop("_id", None)
    return pu


async def _customer(pu: dict) -> dict:
    return await db.customers.find_one({"id": pu.get("customer_id")}, {"_id": 0}) or {}


async def _deals(pu: dict, customer: dict) -> list:
    org = pu.get("org_id", ORG_ID)
    lead_id = customer.get("lead_id")
    if not lead_id:
        return []
    return await db.deals.find({"org_id": org, "lead_id": lead_id}, {"_id": 0}).sort("created_at", -1).to_list(50)


def _payment_summary(inv: dict) -> dict:
    if not inv:
        return {"total": 0, "paid": 0, "outstanding": 0, "next_due": None, "next_amount": 0}
    items = inv.get("items") or []
    nxt = None
    for it in sorted(items, key=lambda x: x.get("due_date") or ""):
        if it.get("status") != "paid":
            nxt = it
            break
    return {
        "total": inv.get("total", 0), "paid": inv.get("paid", 0),
        "outstanding": inv.get("outstanding", 0), "status": inv.get("status"),
        "next_due": (nxt or {}).get("due_date"), "next_amount": (nxt or {}).get("amount", 0),
        "next_label": (nxt or {}).get("label"),
    }


# ----------------------------- auth -----------------------------
@router.post("/auth/request-otp")
async def request_otp(payload: PortalOtpRequest):
    pu = await _find_portal_user(payload.identifier)
    if not pu:
        raise HTTPException(status_code=404, detail="Data pembeli tidak ditemukan untuk kontak tersebut.")
    code = gen_otp()
    await db.portal_otps.update_one(
        {"portal_user_id": pu["id"]},
        {"$set": {"portal_user_id": pu["id"], "code": code, "attempts": 0,
                  "expires_at": due_in(minutes=10), "created_at": now_iso()}},
        upsert=True,
    )
    to = pu.get("phone") or pu.get("email")
    channel = "whatsapp" if pu.get("phone") else "email"
    res = await send_whatsapp(to, f"Kode OTP Portal SIPRO Anda: {code} (berlaku 10 menit). Jangan bagikan kode ini.")
    simulated = res.get("provider") == "simulation"
    return {
        "sent": True, "channel": channel, "masked": _mask(to),
        "dev_code": code if simulated else None,
        "message": "OTP dikirim." + (" Mode simulasi: kode ditampilkan untuk pengujian." if simulated else ""),
    }


def _mask(s: str) -> str:
    if not s:
        return ""
    if "@" in s:
        u, _, d = s.partition("@")
        return (u[:2] + "***@" + d)
    return s[:5] + "****" + s[-2:]


@router.post("/auth/verify-otp")
async def verify_otp(payload: PortalOtpVerify):
    pu = await _find_portal_user(payload.identifier)
    if not pu:
        raise HTTPException(status_code=404, detail="Data pembeli tidak ditemukan.")
    master = os.environ.get("PORTAL_MASTER_OTP", "000000")
    code = (payload.code or "").strip()
    if code != master:
        rec = await db.portal_otps.find_one({"portal_user_id": pu["id"]}, {"_id": 0})
        if not rec or rec.get("code") != code:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")
        if rec.get("expires_at") and rec["expires_at"] < now_iso():
            raise HTTPException(status_code=400, detail="Kode OTP kedaluwarsa. Minta kode baru.")
    await db.portal_otps.delete_one({"portal_user_id": pu["id"]})
    await db.portal_users.update_one({"id": pu["id"]}, {"$set": {"last_login_at": now_iso()}})
    token = create_portal_token(pu)
    return {"token": token, "profile": {"name": pu.get("name"), "customer_id": pu.get("customer_id"),
                                         "phone": pu.get("phone"), "email": pu.get("email")}}


# ----------------------------- data -----------------------------
@router.get("/me")
async def me(pu: dict = Depends(get_portal_user)):
    cust = await _customer(pu)
    return {"data": {"name": pu.get("name"), "phone": pu.get("phone"), "email": pu.get("email"),
                     "customer": serialize_doc({k: cust.get(k) for k in
                                                ["name", "nik", "npwp", "address", "kyc_status"]})}}


@router.get("/overview")
async def overview(pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    out = []
    for d in deals:
        unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0}) or {}
        project = await db.projects.find_one({"id": d.get("project_id")}, {"_id": 0}) or {}
        inv = await db.ar_invoices.find_one({"org_id": org, "deal_id": d["id"]}, {"_id": 0})
        fin = await db.financing_apps.find_one({"org_id": org, "deal_id": d["id"]}, {"_id": 0})
        doc_count = await db.documents.count_documents({"org_id": org, "deal_id": d["id"]})
        open_complaints = await db.complaints.count_documents(
            {"org_id": org, "deal_id": d["id"], "status": {"$ne": "resolved"}})
        out.append({
            "deal_id": d["id"], "status": d.get("status"), "price": d.get("price"),
            "unit_code": unit.get("code"), "unit_type": unit.get("type"),
            "project_name": project.get("name"),
            "construction_progress": unit.get("construction_progress", 0),
            "construction_status": unit.get("construction_status"),
            "payment": _payment_summary(inv),
            "financing": fin and {"bank_name": fin.get("bank_name"), "status": fin.get("status"),
                                  "plafon": fin.get("plafon"), "disbursed_total": fin.get("disbursed_total"),
                                  "slik_status": fin.get("slik_status")},
            "documents_count": doc_count, "open_complaints": open_complaints,
        })
    return {"data": serialize_doc(out), "customer_name": cust.get("name")}


@router.get("/payments")
async def payments(pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    result = []
    for d in deals:
        inv = await db.ar_invoices.find_one({"org_id": org, "deal_id": d["id"]}, {"_id": 0})
        receipts = await db.receipts.find({"org_id": org, "deal_id": d["id"]},
                                          {"_id": 0}).sort("created_at", -1).to_list(200)
        result.append({
            "deal_id": d["id"], "unit_code": inv.get("unit_code") if inv else None,
            "summary": _payment_summary(inv),
            "schedule": (inv or {}).get("items", []),
            "receipts": receipts,
        })
    return {"data": serialize_doc(result)}


# ----------------------------- Fase 47B: setor bukti transfer -----------------------------
@router.post("/payments/proof")
async def submit_payment_proof(payload: PaymentProofIn,
                              pu: dict = Depends(get_portal_user)):
    """Pelanggan mengirim bukti transfer.

    Yang PENTING: ini KLAIM, bukan pelunasan. Tagihan tidak berubah sedikit pun sampai
    finance memverifikasi (uji negatif di gate). Dengan begitu portal berhenti menjadi
    ruang tafsir ("saya sudah transfer kok") tanpa mengorbankan kebenaran uang.
    """
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    deal = next((d for d in deals if d["id"] == payload.deal_id), None)
    if not deal:
        raise HTTPException(status_code=404,
                            detail="Transaksi tidak ditemukan pada akun Anda.")
    owned = await db.files.count_documents({"org_id": org, "id": {"$in": payload.file_ids}})
    if owned != len(payload.file_ids):
        raise HTTPException(status_code=400,
                            detail="Berkas bukti tidak lengkap - unggah ulang fotonya.")
    try:
        doc = await intake.create_from_portal(
            org, customer=cust, deal=deal, amount=payload.amount,
            transfer_date=payload.transfer_date, file_ids=payload.file_ids,
            bank_name=payload.bank_name, note=payload.note,
            actor=(pu.get("email") or pu.get("phone") or cust.get("name")))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": serialize_doc(doc),
            "message": ("Bukti transfer terkirim. Status: menunggu verifikasi finance - "
                        "tagihan Anda akan berkurang setelah diverifikasi.")}


@router.get("/payments/submissions")
async def my_payment_submissions(pu: dict = Depends(get_portal_user)):
    """Riwayat bukti transfer + statusnya (termasuk ALASAN bila ditolak)."""
    out = await intake.listing(pu.get("org_id", ORG_ID), customer_id=pu.get("customer_id"),
                               limit=100)
    return {"data": serialize_doc(out["data"]), "total": out["total"],
            "summary": out["summary"]}


@router.get("/progress")
async def progress(pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    result = []
    for d in deals:
        unit = await db.units.find_one({"id": d.get("unit_id")}, {"_id": 0}) or {}
        phases = await db.construction_phases.find(
            {"org_id": org, "project_id": d.get("project_id")}, {"_id": 0}).sort("order", 1).to_list(300)
        # Fase 28b — bukti visual: foto lapangan (punch berfoto pada unit ini + buku
        # harian proyek) dengan cakupan ditandai jujur agar pembeli tidak salah paham.
        photos = await p28.collect_unit_photos(org, d.get("project_id"), d.get("unit_id"), limit=6)
        # Bukti kerja berpasangan: pembeli melihat foto SEBELUM & SESUDAH tiap temuan
        # pada unitnya, bukan tumpukan foto tanpa konteks.
        repairs = await p28.collect_repair_pairs(org, d.get("unit_id"), limit=5)
        # Fase 31: progres RUMAH pembeli berasal dari jadwal pembangunan unitnya sendiri.
        # `phases` di bawah adalah pekerjaan KAWASAN (jalan/drainase), dilabeli jujur di UI.
        build = await bm.buyer_milestones(org, d.get("unit_id")) if d.get("unit_id") else None
        result.append({
            "deal_id": d["id"], "unit_code": unit.get("code"),
            "construction_progress": unit.get("construction_progress", 0),
            "construction_status": unit.get("construction_status"),
            "build": build,
            "phases": [{"name": p.get("name"), "weight": p.get("weight"),
                        "progress": p.get("progress", 0), "status": p.get("status")} for p in phases],
            "curve": build_s_curve(phases),
            "photos": photos,
            "repairs": repairs,
        })
    return {"data": serialize_doc(result)}


# ------------------- Peta kavling pembeli (Fase 28b) -------------------
async def _portal_projects(pu: dict, deals: list) -> list:
    return sorted({d.get("project_id") for d in deals if d.get("project_id")})


@router.get("/site-plan")
async def portal_site_plan(pu: dict = Depends(get_portal_user)):
    """Peta site plan untuk pembeli: kavling MILIKNYA disorot, kavling lain anonim.

    Privasi tetangga dijaga: yang keluar hanya kode + status kavling lain (tanpa harga,
    tanpa nama pembeli, tanpa nilai transaksi). Data harga hanya untuk kavling sendiri.
    """
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    pids = await _portal_projects(pu, deals)
    if not pids:
        return {"data": {"projects": []}}
    own_units = {d.get("unit_id") for d in deals if d.get("unit_id")}
    out = []
    for pid in pids:
        proj = await db.projects.find_one({"id": pid, "org_id": org},
                                          {"_id": 0, "name": 1, "location": 1}) or {}
        plan = await db.site_plans.find_one({"org_id": org, "project_id": pid},
                                            {"_id": 0, "view_box": 1, "shapes": 1})
        rows = await db.units.find({"org_id": org, "project_id": pid},
                                   {"_id": 0, "id": 1, "code": 1, "block": 1, "type": 1,
                                    "status": 1, "price": 1, "luas_bangunan": 1,
                                    "luas_tanah": 1, "orientation": 1, "corner": 1,
                                    "construction_progress": 1}).sort("code", 1).to_list(2000)
        units = []
        for u in rows:
            mine = u["id"] in own_units
            lb, lt = p28.parse_luas(u)
            units.append({
                "id": u["id"], "code": u.get("code"), "block": p28.block_of(u),
                "status": u.get("status", "available"), "mine": mine,
                "type": u.get("type") if mine else None,
                "price": int(u.get("price") or 0) if mine else None,
                "luas_bangunan": lb if mine else None, "luas_tanah": lt if mine else None,
                "orientation": u.get("orientation") if mine else None,
                "corner": bool(u.get("corner")) if mine else None,
                "construction_progress": u.get("construction_progress", 0) if mine else None,
            })
        out.append({"project_id": pid, "project_name": proj.get("name"),
                    "location": proj.get("location"), "plan": serialize_doc(plan),
                    "units": units,
                    "my_codes": [u["code"] for u in units if u["mine"]]})
    return {"data": {"projects": out}}


@router.get("/files/{file_id}")
async def portal_file(file_id: str, request: Request, variant: str = Query(None)):
    """Unduh/tampilkan foto lapangan untuk pembeli (mendukung `?auth=` untuk <img>).

    Kepemilikan diverifikasi NYATA: berkas hanya boleh diakses bila benar-benar
    dirujuk oleh buku harian atau temuan punch pada proyek tempat pembeli punya deal.
    Fase 30b: `?variant=thumb` melayani versi kecil (hemat kuota pembeli di galeri).
    """
    pu = await get_portal_user(request)
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    pids = await _portal_projects(pu, deals)
    if not pids:
        raise HTTPException(403, "Tidak ada proyek terkait akun Anda.")
    q = {"org_id": org, "project_id": {"$in": pids},
         "$or": [{"photo": file_id}, {"photos": file_id}, {"fix_photos": file_id}]}
    allowed = (await db.site_diaries.count_documents(q)) or (await db.punch_items.count_documents(q))
    if not allowed:
        raise HTTPException(404, "Foto tidak ditemukan.")
    rec = await db.files.find_one({"id": file_id, "org_id": org, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Foto tidak ditemukan.")
    path, want_type = await storage.variant_source(rec, variant)
    try:
        data, ctype = await storage.get_file_bytes(path, rec.get("provider"))
    except FileNotFoundError:
        raise HTTPException(404, "Objek foto tidak ada di storage.")
    return Response(content=data, media_type=want_type or ctype,
                    headers={"Cache-Control": "private, max-age=3600"})


@router.get("/documents")
async def documents(pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    ids = [d["id"] for d in deals]
    rows = []
    if ids:
        rows = await db.documents.find({"org_id": org, "deal_id": {"$in": ids}},
                                       {"_id": 0, "content": 0}).sort("created_at", -1).to_list(100)
    return {"data": serialize_doc(rows)}


@router.get("/documents/{doc_id}/pdf")
async def document_pdf(doc_id: str, request: Request):
    pu = await get_portal_user(request)
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    ids = [d["id"] for d in deals]
    doc = await db.documents.find_one({"id": doc_id, "org_id": org}, {"_id": 0})
    if not doc or doc.get("deal_id") not in ids:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    pdf = build_document_pdf(title=doc.get("title", "Dokumen"), doc_number=doc.get("doc_number"),
                             content=doc.get("content", ""), signatures=doc.get("signatures"),
                             org_name=ORG_NAME)
    filename = f"{(doc.get('doc_number') or 'dokumen').replace('/', '-')}.pdf"
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ----------------------------- reference (SSOT untuk portal) -----------------------------
@router.get("/reference")
async def portal_reference(_pu: dict = Depends(get_portal_user)):
    """Subset kamus data untuk portal pembeli (Fase 26).

    Portal memakai token sendiri sehingga tidak bisa mengakses `/api/reference` milik staf;
    dulu akibatnya daftar kategori komplain di-hardcode di frontend portal dan nilainya
    menyimpang dari SSOT (mis. \"umum\" vs kanonik \"lainnya\").
    """
    allowed = ("complaint_category", "complaint_status", "priority")
    reg = ref.public_registry()
    return {"data": {k: reg[k] for k in allowed if k in reg}}


# ----------------------------- complaints -----------------------------
@router.get("/complaints")
async def list_complaints(pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    rows = await db.complaints.find({"org_id": org, "customer_id": pu.get("customer_id")},
                                    {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"data": serialize_doc(rows)}


@router.post("/complaints")
async def create_complaint(payload: ComplaintCreate, pu: dict = Depends(get_portal_user)):
    org = pu.get("org_id", ORG_ID)
    cust = await _customer(pu)
    deals = await _deals(pu, cust)
    deal = next((d for d in deals if d["id"] == payload.deal_id), deals[0] if deals else None)
    unit_code = None
    if deal:
        unit = await db.units.find_one({"id": deal.get("unit_id")}, {"_id": 0}) or {}
        unit_code = unit.get("code")
    ts = now_iso()
    cid = new_id()
    sla = due_in(hours=48)
    doc = {
        "id": cid, "org_id": org, "customer_id": pu.get("customer_id"),
        "customer_name": pu.get("name"), "deal_id": deal["id"] if deal else None,
        "unit_code": unit_code, "category": payload.category or "umum",
        "subject": payload.subject, "message": payload.message,
        "status": "open", "priority": payload.priority or "medium",
        "assigned_to": (deal or {}).get("assigned_to"),
        "sla_due_at": sla, "responses": [], "created_at": ts, "updated_at": ts,
    }
    await db.complaints.insert_one(dict(doc))
    # SLA task for the responsible sales/CS + notification.
    assignee = doc.get("assigned_to")
    await auto_create_task(
        source_event=f"complaint:{cid}", title=f"Komplain pembeli: {payload.subject}",
        jobdesk_code="SM-09",
        type="complaint", related_entity_type="complaint", related_entity_id=cid,
        assigned_to=assignee, sla_due_at=sla, priority=doc["priority"],
        description=f"{pu.get('name')} ({unit_code or '-'}): {payload.message}", org_id=org)
    if assignee:
        await create_notification(user_email=assignee, title="Komplain pembeli baru",
                                  body=f"{pu.get('name')}: {payload.subject}", type="complaint", org_id=org)
    await send_whatsapp(pu.get("phone"),
                        f"Terima kasih. Komplain Anda '{payload.subject}' telah kami terima dan akan ditindaklanjuti (SLA 2x24 jam).")
    doc.pop("_id", None)
    return {"data": serialize_doc(doc)}
