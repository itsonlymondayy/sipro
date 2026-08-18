"""Projects & Units management — Slice B. Project-membership scoped for pm/site."""
from fastapi import APIRouter, Depends, HTTPException

from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc, parse_pagination
from rbac import require_permission, project_query, assert_project_access
from engine import build_s_curve
from models import ProjectCreate, UnitGenerate
from models_master import ProjectUpdate, UnitUpdate
from denorm import cascade_master_change
from rbac import audit_log

router = APIRouter(tags=["projects"])


async def _project_summary(proj: dict) -> dict:
    org = proj.get("org_id", ORG_ID)
    pid = proj["id"]
    total = await db.units.count_documents({"org_id": org, "project_id": pid})
    counts = {}
    for st in ("available", "reserved", "booked", "sold"):
        counts[st] = await db.units.count_documents({"org_id": org, "project_id": pid, "status": st})
    proj["unit_total"] = total
    proj["unit_counts"] = counts
    proj["construction_progress"] = proj.get("construction_progress", 0)
    return proj


@router.get("/projects")
async def list_projects(skip: int = 0, limit: int = 50,
                        user: dict = Depends(require_permission("projects", "view"))):
    skip, limit = parse_pagination(skip, limit)
    q = project_query(user, {})
    total = await db.projects.count_documents(q)
    rows = await db.projects.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for p in rows:
        await _project_summary(p)
    return {"data": serialize_doc(rows), "total": total}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(require_permission("projects", "view"))):
    proj = await assert_project_access(project_id, user)
    org = user.get("org_id", ORG_ID)
    await _project_summary(proj)
    units = await db.units.find({"org_id": org, "project_id": project_id}, {"_id": 0}).sort("code", 1).to_list(500)
    phases = await db.construction_phases.find({"org_id": org, "project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(300)
    return {"data": {"project": serialize_doc(proj), "units": serialize_doc(units),
                     "phases": serialize_doc(phases), "curve": build_s_curve(phases)}}


@router.get("/projects/{project_id}/target-summary")
async def project_target_summary(
        project_id: str, user: dict = Depends(require_permission("targets", "view"))):
    """Ringkasan target proyek untuk kartu dashboard (Fase 45, `docs/v2/32` §2.2).

    Kontraknya hidup di bawah `/projects/{id}` karena inilah bentuk yang dipakai layar detail
    proyek. Tanpa target AKTIF, jawabannya `state: "kosong"` + ajakan membuat target — BUKAN
    angka 0 yang membuat kartu terlihat "target 0 unit, tercapai 100%".
    """
    await assert_project_access(project_id, user)
    import target_store as tstore
    return {"data": serialize_doc(
        await tstore.project_summary(user.get("org_id", ORG_ID), project_id))}



@router.post("/projects")
async def create_project(payload: ProjectCreate,
                         user: dict = Depends(require_permission("projects", "create"))):
    org = user.get("org_id", ORG_ID)
    if await db.projects.find_one({"org_id": org, "code": payload.code}):
        raise HTTPException(status_code=400, detail="Kode proyek sudah dipakai")
    ts = now_iso()
    members = list(set(payload.members + [user.get("email")]))
    proj = {
        "id": new_id(), "org_id": org, "name": payload.name, "code": payload.code,
        "location": payload.location, "status": "active", "members": members,
        "construction_progress": 0, "created_at": ts, "updated_at": ts, "created_by": user.get("email"),
    }
    await db.projects.insert_one(proj)
    proj.pop("_id", None)
    await _project_summary(proj)
    return {"data": serialize_doc(proj)}


@router.post("/projects/{project_id}/units")
async def generate_units(project_id: str, payload: UnitGenerate,
                         user: dict = Depends(require_permission("projects", "update"))):
    await assert_project_access(project_id, user)
    org = user.get("org_id", ORG_ID)
    ts = now_iso()
    created = []
    for i in range(payload.start_index, payload.start_index + payload.count):
        code = f"{payload.prefix}-{i:02d}"
        if await db.units.find_one({"org_id": org, "project_id": project_id, "code": code}):
            continue
        unit = {
            "id": new_id(), "org_id": org, "project_id": project_id, "code": code,
            "type": payload.type, "price": payload.price, "status": "available",
            "construction_status": "not_started", "construction_progress": 0,
            "payment_status": "none", "reserved_by_deal": None, "booked_by_deal": None,
            "created_at": ts, "updated_at": ts,
        }
        await db.units.insert_one(unit)
        created.append(code)
    return {"data": {"created": created, "count": len(created)}}


@router.put("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectUpdate,
                         user: dict = Depends(require_permission("projects", "update"))):
    """Koreksi master proyek. SEBELUM PERBAIKAN INI TIDAK ADA endpoint update, jadi nama/
    lokasi/status/anggota proyek tidak bisa dibetulkan setelah dibuat.
    Perubahan nama otomatis disamakan ke semua dokumen anak (SSOT)."""
    proj = await assert_project_access(project_id, user)
    org = user.get("org_id", ORG_ID)
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "code" in upd and upd["code"] != proj.get("code"):
        if await db.projects.find_one({"org_id": org, "code": upd["code"], "id": {"$ne": project_id}}):
            raise HTTPException(status_code=409, detail="Kode proyek sudah dipakai proyek lain.")
    if "members" in upd:
        upd["members"] = sorted(set(upd["members"] + [proj.get("created_by") or user.get("email")]))
    if not upd:
        return {"data": serialize_doc(await _project_summary(proj))}
    upd["updated_at"] = now_iso()
    await db.projects.update_one({"id": project_id, "org_id": org}, {"$set": upd})
    fresh = await db.projects.find_one({"id": project_id, "org_id": org}, {"_id": 0})
    synced = await cascade_master_change("projects", project_id, fresh)
    await audit_log(user, "update", "projects", project_id,
                    {"fields": sorted(upd), "denorm_synced": synced})
    await _project_summary(fresh)
    return {"data": serialize_doc(fresh), "denorm_synced": synced}


@router.put("/projects/{project_id}/units/{unit_id}")
async def update_unit(project_id: str, unit_id: str, payload: UnitUpdate,
                      user: dict = Depends(require_permission("projects", "update"))):
    """Koreksi tipe/harga unit (sebelumnya unit hanya bisa digenerate, tak bisa dibetulkan)."""
    await assert_project_access(project_id, user)
    org = user.get("org_id", ORG_ID)
    unit = await db.units.find_one({"id": unit_id, "org_id": org, "project_id": project_id}, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan pada proyek ini.")
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not upd:
        return {"data": serialize_doc(unit)}
    if "price" in upd and unit.get("status") in ("booked", "sold"):
        raise HTTPException(status_code=400,
                            detail="Harga unit yang sudah booked/terjual tidak boleh diubah "
                                   "(mengubah dasar tagihan & komisi).")
    upd["updated_at"] = now_iso()
    await db.units.update_one({"id": unit_id, "org_id": org}, {"$set": upd})
    await audit_log(user, "update", "units", unit_id, {"fields": sorted(upd)})
    return {"data": serialize_doc(await db.units.find_one({"id": unit_id}, {"_id": 0}))}


@router.delete("/projects/{project_id}/units/{unit_id}")
async def delete_unit(project_id: str, unit_id: str,
                      user: dict = Depends(require_permission("projects", "update"))):
    """Hapus unit yang salah digenerate. Hanya unit 'available' tanpa jejak transaksi."""
    await assert_project_access(project_id, user)
    org = user.get("org_id", ORG_ID)
    unit = await db.units.find_one({"id": unit_id, "org_id": org, "project_id": project_id}, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan pada proyek ini.")
    if unit.get("status") != "available":
        raise HTTPException(status_code=400, detail=(
            f"Unit berstatus '{unit.get('status')}' tidak bisa dihapus. "
            "Hanya unit yang masih tersedia boleh dihapus."))
    blockers = {
        "deal": await db.deals.count_documents({"org_id": org, "unit_id": unit_id}),
        "inspeksi": await db.inspections.count_documents({"org_id": org, "unit_id": unit_id}),
        "punch list": await db.punch_items.count_documents({"org_id": org, "unit_id": unit_id}),
        "komplain": await db.complaints.count_documents({"org_id": org, "unit_id": unit_id}),
    }
    used = {k: v for k, v in blockers.items() if v}
    if used:
        detail = ", ".join(f"{v} {k}" for k, v in used.items())
        raise HTTPException(status_code=400, detail=f"Unit dipakai oleh {detail} — tidak bisa dihapus.")
    await db.units.delete_one({"id": unit_id, "org_id": org})
    await audit_log(user, "delete", "units", unit_id, {"code": unit.get("code")})
    return {"data": {"id": unit_id, "code": unit.get("code"), "deleted": True}}
