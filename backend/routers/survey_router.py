"""Surveys (EPIC 1.2) — kunjungan lokasi/unit yang terikat lead + appointment.

Checklist terstruktur + foto (via storage abstraction) + hasil/rekomendasi.
RBAC resource `surveys` + row-scope sales (hanya survey miliknya).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc, parse_pagination
from rbac import require_permission, scope_query, is_scoped_sales
from engine import add_activity
from models import SurveyCreate, SurveyUpdate, SurveyResult
import storage

router = APIRouter(prefix="/surveys", tags=["surveys"])

# Checklist standar survey lokasi/unit (developer properti).
DEFAULT_CHECKLIST = [
    {"key": "akses_jalan", "label": "Akses jalan menuju lokasi", "status": "na", "note": None},
    {"key": "kondisi_tanah", "label": "Kondisi tanah & kontur", "status": "na", "note": None},
    {"key": "batas_kavling", "label": "Batas kavling & patok jelas", "status": "na", "note": None},
    {"key": "listrik", "label": "Ketersediaan listrik", "status": "na", "note": None},
    {"key": "air", "label": "Ketersediaan air / PDAM", "status": "na", "note": None},
    {"key": "drainase", "label": "Saluran drainase", "status": "na", "note": None},
    {"key": "lingkungan", "label": "Lingkungan & keamanan sekitar", "status": "na", "note": None},
]
RESULTS = ("recommended", "needs_followup", "not_recommended")
ITEM_STATUS = ("na", "ok", "issue")


async def _get_survey_scoped(survey_id: str, user: dict) -> dict:
    s = await db.surveys.find_one({"id": survey_id, "org_id": user.get("org_id", ORG_ID)}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Survey tidak ditemukan")
    if is_scoped_sales(user) and s.get("assigned_to") != user.get("email"):
        raise HTTPException(status_code=403, detail="Akses ditolak: bukan survey Anda")
    return s


async def _photos(survey_id: str, org: str) -> list:
    rows = await db.files.find(
        {"org_id": org, "owner_type": "survey", "owner_id": survey_id, "is_deleted": False},
        {"_id": 0, "data_b64": 0}).sort("created_at", 1).to_list(100)
    return serialize_doc(rows)


@router.get("")
async def list_surveys(lead_id: str = None, appointment_id: str = None, status: str = None,
                       skip: int = 0, limit: int = 50,
                       user: dict = Depends(require_permission("surveys", "view"))):
    skip, limit = parse_pagination(skip, limit)
    base = {}
    if lead_id:
        base["lead_id"] = lead_id
    if appointment_id:
        base["appointment_id"] = appointment_id
    if status:
        base["status"] = status
    q = scope_query(user, base)
    total = await db.surveys.count_documents(q)
    rows = await db.surveys.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"data": serialize_doc(rows), "total": total}


@router.post("")
async def create_survey(payload: SurveyCreate,
                        user: dict = Depends(require_permission("surveys", "create"))):
    org = user.get("org_id", ORG_ID)
    lead = await db.leads.find_one({"id": payload.lead_id, "org_id": org}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead tidak ditemukan")
    if is_scoped_sales(user) and lead.get("assigned_to") != user.get("email"):
        raise HTTPException(status_code=403, detail="Akses ditolak: bukan lead Anda")

    appt = None
    if payload.appointment_id:
        appt = await db.appointments.find_one(
            {"id": payload.appointment_id, "org_id": org}, {"_id": 0})
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment tidak ditemukan")
        # idempotent: bila survey utk appointment ini sudah ada, kembalikan itu.
        existing = await db.surveys.find_one(
            {"org_id": org, "appointment_id": payload.appointment_id}, {"_id": 0})
        if existing:
            return {"data": serialize_doc({**existing, "photos": await _photos(existing["id"], org)})}

    ts = now_iso()
    survey = {
        "id": new_id(), "org_id": org, "lead_id": payload.lead_id, "lead_name": lead.get("name"),
        "appointment_id": payload.appointment_id,
        "location": payload.location or (appt.get("location") if appt else None),
        "notes": payload.notes, "summary": None,
        "assigned_to": lead.get("assigned_to"), "status": "in_progress", "result": None,
        "checklist": [dict(c) for c in DEFAULT_CHECKLIST], "photo_count": 0,
        "created_by": user.get("email"), "created_at": ts, "updated_at": ts, "completed_at": None,
    }
    await db.surveys.insert_one(dict(survey))
    await add_activity(entity_type="lead", entity_id=payload.lead_id, type="system",
                       body=f"Survey dimulai untuk {lead.get('name')}.", actor=user.get("email"), org_id=org)
    survey.pop("_id", None)
    return {"data": serialize_doc({**survey, "photos": []})}


@router.get("/{survey_id}")
async def get_survey(survey_id: str, user: dict = Depends(require_permission("surveys", "view"))):
    s = await _get_survey_scoped(survey_id, user)
    return {"data": serialize_doc({**s, "photos": await _photos(survey_id, user.get("org_id", ORG_ID))})}


@router.put("/{survey_id}")
async def update_survey(survey_id: str, payload: SurveyUpdate,
                        user: dict = Depends(require_permission("surveys", "update"))):
    s = await _get_survey_scoped(survey_id, user)
    if s.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Survey sudah selesai; tidak bisa diubah.")
    updates = {"updated_at": now_iso()}
    if payload.location is not None:
        updates["location"] = payload.location
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if payload.summary is not None:
        updates["summary"] = payload.summary
    if payload.checklist is not None:
        items = []
        for it in payload.checklist:
            st = it.status if it.status in ITEM_STATUS else "na"
            items.append({"key": it.key, "label": it.label, "status": st, "note": it.note})
        updates["checklist"] = items
    await db.surveys.update_one({"id": survey_id}, {"$set": updates})
    fresh = await db.surveys.find_one({"id": survey_id}, {"_id": 0})
    return {"data": serialize_doc({**fresh, "photos": await _photos(survey_id, user.get("org_id", ORG_ID))})}


@router.post("/{survey_id}/result")
async def finalize_survey(survey_id: str, payload: SurveyResult,
                          user: dict = Depends(require_permission("surveys", "update"))):
    org = user.get("org_id", ORG_ID)
    s = await _get_survey_scoped(survey_id, user)
    if payload.result not in RESULTS:
        raise HTTPException(status_code=400, detail="Hasil survey tidak valid.")
    ts = now_iso()
    updates = {"status": "completed", "result": payload.result, "updated_at": ts, "completed_at": ts}
    if payload.summary is not None:
        updates["summary"] = payload.summary
    await db.surveys.update_one({"id": survey_id}, {"$set": updates})
    # Tandai appointment terkait selesai (bila ada & masih terjadwal).
    if s.get("appointment_id"):
        await db.appointments.update_one(
            {"id": s["appointment_id"], "org_id": org, "status": "scheduled"},
            {"$set": {"status": "done", "updated_at": ts}})
    result_label = {"recommended": "Direkomendasikan", "needs_followup": "Perlu tindak lanjut",
                    "not_recommended": "Tidak direkomendasikan"}.get(payload.result, payload.result)
    await add_activity(entity_type="lead", entity_id=s.get("lead_id"), type="system",
                       body=f"Survey selesai — hasil: {result_label}.", actor=user.get("email"), org_id=org)
    fresh = await db.surveys.find_one({"id": survey_id}, {"_id": 0})
    return {"data": serialize_doc({**fresh, "photos": await _photos(survey_id, org)})}


@router.post("/{survey_id}/photos")
async def upload_survey_photo(survey_id: str, file: UploadFile = File(...), caption: str = Form(None),
                              user: dict = Depends(require_permission("surveys", "update"))):
    org = user.get("org_id", ORG_ID)
    s = await _get_survey_scoped(survey_id, user)
    data = await file.read()
    try:
        rec = await storage.save_file(
            data=data, filename=file.filename or "foto-survey.jpg",
            content_type=file.content_type or "application/octet-stream",
            org_id=org, owner_type="survey", owner_id=survey_id,
            uploaded_by=user.get("email"), doc_type=caption or "survey_photo", tag="survey")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.surveys.update_one({"id": survey_id}, {"$inc": {"photo_count": 1},
                                                    "$set": {"updated_at": now_iso()}})
    return {"data": rec}
