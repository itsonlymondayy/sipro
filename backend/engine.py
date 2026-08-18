"""Engine layer: Event Bus (outbox) + Dispatcher + Scheduler + Guided Work Engine
+ Activity/Notification helpers. In-process (no external broker) per Dok 13.
"""
import logging

import attribution as attr
import reference as ref
from db import db, ORG_ID
from core_utils import new_id, now_iso, due_in, serialize_doc
from ws_manager import manager as ws_manager

logger = logging.getLogger("sipro.engine")

# ----------------------------- Event Bus (outbox) -----------------------------
async def emit(etype: str, entity_type: str, entity_id: str, data: dict = None, org_id: str = ORG_ID):
    await db.events.insert_one({
        "id": new_id(), "org_id": org_id, "type": etype,
        "entity_type": entity_type, "entity_id": entity_id,
        "data": data or {}, "status": "pending", "retries": 0,
        "created_at": now_iso(),
    })


# ----------------------------- Activity + Notifications -----------------------------
async def create_notification(*, user_email, title, body=None, type="info",
                              related_entity_type=None, related_entity_id=None, org_id=ORG_ID):
    if not user_email:
        return None
    doc = {
        "id": new_id(), "org_id": org_id, "user_email": user_email,
        "title": title, "body": body, "type": type,
        "related_entity_type": related_entity_type, "related_entity_id": related_entity_id,
        "read": False, "created_at": now_iso(),
    }
    await db.notifications.insert_one(doc)
    # Real-time push (EPIC M3 — WebSocket): deliver the instant it happens,
    # event-driven (no ~2s poll). Never blocks on transport errors.
    try:
        unread = await db.notifications.count_documents(
            {"org_id": org_id, "user_email": user_email, "read": False})
        await ws_manager.send_personal(user_email, {
            "event": "notification", "data": serialize_doc(doc), "unread": unread,
        })
    except Exception:  # noqa: BLE001
        logger.debug("ws push skipped for %s", user_email, exc_info=True)
    return doc


async def add_activity(*, entity_type, entity_id, body, type="comment", actor="system",
                       mentions=None, parent_id=None, org_id=ORG_ID, meta=None):
    doc = {
        "id": new_id(), "org_id": org_id, "entity_type": entity_type, "entity_id": entity_id,
        "type": type, "body": body, "actor": actor, "mentions": mentions or [],
        "parent_id": parent_id, "meta": meta or {}, "created_at": now_iso(),
    }
    await db.activities.insert_one(doc)
    for m in (mentions or []):
        await create_notification(user_email=m, title="Anda disebut dalam sebuah catatan",
                                  body=(body or "")[:140], type="mention",
                                  related_entity_type=entity_type, related_entity_id=entity_id, org_id=org_id)
    return doc


# ----------------------------- Guided Work Engine -----------------------------
async def auto_create_task(*, source_event, title, type, related_entity_type, related_entity_id,
                           assigned_to=None, due_date=None, sla_due_at=None, description=None,
                           priority="medium", org_id=ORG_ID, jobdesk_code=None):
    """Idempotent auto-task: skip if an OPEN task with same source_event exists.

    Fase 29: setiap task diberi **divisi** (diturunkan dari penerima bila `jobdesk_code`
    tidak diberikan) supaya muncul di papan divisi yang benar. Tanpa ini, task warisan
    tidak pernah terlihat oleh supervisor mana pun.
    """
    existing = await db.tasks.find_one({
        "org_id": org_id, "source_event": source_event,
        "status": {"$in": ["open", "in_progress", "snoozed", "submitted"]},
    }, {"_id": 0, "id": 1})
    if existing:
        return None
    division, proof_kind, verify_mode, link = None, "none", "none", None
    if jobdesk_code:
        import jobdesk_catalog as _cat
        jd = _cat.defaults(jobdesk_code)
        division, proof_kind = jd.get("division"), jd.get("proof_kind", "note")
        verify_mode, link = jd.get("verify_mode", "none"), jd.get("link")
    elif assigned_to:
        import reference_p29 as _p29
        u = await db.users.find_one({"org_id": org_id, "email": assigned_to},
                                    {"_id": 0, "division": 1, "role": 1})
        if u:
            division = u.get("division") or _p29.ROLE_DIVISION.get(u.get("role"))
    ts = now_iso()
    doc = {
        "id": new_id(), "org_id": org_id, "title": title, "description": description,
        "type": type, "status": "open", "priority": priority,
        "related_entity_type": related_entity_type, "related_entity_id": related_entity_id,
        "assigned_to": assigned_to, "due_date": due_date, "sla_due_at": sla_due_at,
        "sla_breached": False, "source_event": source_event, "auto_generated": True,
        "division": division, "jobdesk_code": jobdesk_code, "proof_kind": proof_kind,
        "verify_mode": verify_mode, "review": "none", "proof": [], "link": link,
        "outcome": None, "created_by": "system", "created_at": ts, "updated_at": ts,
    }
    # Fase 41: jam tahap ditulis saat tugas LAHIR supaya umur status tidak menunggu sweeper.
    import stage_clock as clock
    doc.update(await clock.patch_for("task", "open", org_id=org_id, at=ts))
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ----------------------------- Sales helpers (Slice A) -----------------------------
# SSOT di reference.SOURCE_SCORE. Dulu google_lead & tiktok_ads TIDAK terdaftar di sini,
# sehingga lead dari iklan Google/TikTok selalu mendapat skor terendah (10) seperti import.
SCORE_SOURCE = ref.SOURCE_SCORE
SCORE_STAGE = {"nurturing": 10, "appointment": 25, "booking": 35, "won": 40}


async def auto_assign_lead(org_id: str = ORG_ID):
    """Load-balanced assignment: pick active sales with fewest open leads."""
    sales = await db.users.find({"org_id": org_id, "role": "sales", "is_active": True},
                                {"_id": 0, "email": 1}).to_list(100)
    if not sales:
        return None
    best, best_count = None, None
    for s in sales:
        c = await db.leads.count_documents({
            "org_id": org_id, "assigned_to": s["email"],
            "stage": {"$nin": ["won", "lost", "recycle"]}})
        if best_count is None or c < best_count:
            best, best_count = s["email"], c
    return best


def compute_lead_score(lead: dict) -> dict:
    """Heuristic lead score (0..100) + band (hot/warm/cold). No LLM."""
    score = 30
    score += SCORE_SOURCE.get(lead.get("source"), 10)
    score += SCORE_STAGE.get(lead.get("stage"), 0)
    if lead.get("first_contact_at"):
        score += 10
    created = lead.get("created_at")
    if created and created > due_in(hours=-24):
        score += 10
    score = max(0, min(100, score))
    band = "hot" if score >= 70 else "warm" if score >= 45 else "cold"
    return {"score": score, "score_band": band}


async def process_lead_capture(provider: str, payload: dict, org_id: str = ORG_ID,
                               dispatch: bool = True):
    """Dedup by provider:phone; create lead + conversation + capture event; emit
    lead.captured (+ message.received if inbound text). Returns (lead_id, duplicate)."""
    phone = payload.get("phone")
    dedup_key = f"{provider}:{phone}"
    existing = await db.lead_capture_events.find_one({"org_id": org_id, "dedup_key": dedup_key})
    if existing:
        return existing.get("lead_id"), True
    assignee = await auto_assign_lead(org_id)
    ts = now_iso()
    lead_id = new_id()
    src = payload.get("source") or (
        provider if provider in SCORE_SOURCE else ("meta_ads" if "meta" in provider else "whatsapp"))
    # Fase 43 — bentuk atribusi (campaign_id, utm_*, fbclid/gclid, landing_url) & sentuhan
    # pertama/terakhir hidup di `attribution.py` supaya SEMUA pintu masuk lead memakai bentuk
    # yang sama; lihat modul itu untuk alasannya.
    attribution = attr.build(payload)
    campaign = attr.campaign_of(payload)
    touch = attr.touch(at=ts, provider=provider, source=src, attribution=attribution,
                       campaign=campaign, partner_id=payload.get("partner_id"))
    lead = {
        "id": lead_id, "org_id": org_id, "name": payload.get("name") or "Lead Baru",
        "phone": phone, "email": payload.get("email"), "source": src,
        "campaign": campaign, "stage": "acquisition", "assigned_to": assignee,
        "interest_unit_type": payload.get("interest"), "notes": payload.get("message"),
        "first_contact_at": None, "response_time_minutes": None, "attribution": attribution,
        "first_touch": touch, "last_touch": touch,
        "created_at": ts, "updated_at": ts, "created_by": "webhook",
    }
    if payload.get("partner_id"):
        lead["partner_id"] = payload["partner_id"]
    lead.update(compute_lead_score(lead))
    await db.leads.insert_one(lead)
    conv_id = new_id()
    has_msg = bool(payload.get("message"))
    await db.conversations.insert_one({
        "id": conv_id, "org_id": org_id, "channel": "whatsapp", "contact_phone": phone,
        "contact_name": lead["name"], "lead_id": lead_id, "owner": assignee, "status": "new",
        "mode": "simulation", "unread": 1 if has_msg else 0,
        "last_message_at": ts if has_msg else None, "last_direction": "in" if has_msg else None,
        "window_expires_at": due_in(hours=24), "created_at": ts, "updated_at": ts,
    })
    if has_msg:
        await db.messages.insert_one({
            "id": new_id(), "org_id": org_id, "conversation_id": conv_id, "direction": "in",
            "body": payload["message"], "sender": "contact", "created_at": ts})
    await db.lead_capture_events.insert_one({
        "id": new_id(), "org_id": org_id, "provider": provider, "dedup_key": dedup_key,
        "status": "processed", "lead_id": lead_id, "source": src, "campaign": campaign,
        "campaign_id": attribution["campaign_id"],
        "adset_id": attribution["adset_id"], "ad_id": attribution["ad_id"],
        "creative_id": attribution["creative_id"], "form_id": attribution["form_id"],
        "partner_id": payload.get("partner_id"), "attribution": attribution,
        "raw_payload": payload, "created_at": ts})
    await emit("lead.captured", "lead", lead_id, {"provider": provider}, org_id=org_id)
    if has_msg:
        await emit("message.received", "conversation", conv_id, {"body": payload["message"]}, org_id=org_id)
    if dispatch:
        await dispatch_pending()
    return lead_id, False


# ----------------------------- Construction helpers (Slice B) -----------------------------
async def recompute_project_progress(project_id: str, org_id: str = ORG_ID):
    """Progres PROYEK dari fase level proyek (infrastruktur) + rekap progres unit.

    Fase 31 memperbaiki cacat lama: dulu angka proyek DITIMPA ke `units` sehingga setiap
    rumah menampilkan progres yang sama dan tidak pernah nyata. Progres unit kini
    dihitung dari jadwal pembangunannya sendiri (`build_engine.recompute_schedule`),
    sedangkan di sini hanya disimpan rekap rata-ratanya untuk kartu ringkasan proyek.
    """
    ts = now_iso()
    scheds = await db.build_schedules.find(
        {"org_id": org_id, "project_id": project_id}, {"_id": 0, "progress": 1}).to_list(2000)
    units_progress = round(sum(float(s.get("progress") or 0)
                               for s in scheds) / len(scheds)) if scheds else 0
    phases = await db.construction_phases.find(
        {"org_id": org_id, "project_id": project_id}, {"_id": 0}).to_list(300)
    if not phases:
        await db.projects.update_one({"id": project_id, "org_id": org_id},
                                     {"$set": {"units_progress": units_progress,
                                               "units_scheduled": len(scheds),
                                               "updated_at": ts}})
        return 0
    total_w = sum(p.get("weight", 0) for p in phases) or 1
    overall = round(sum(p.get("weight", 0) * p.get("progress", 0) for p in phases) / total_w)
    await db.projects.update_one({"id": project_id, "org_id": org_id},
                                 {"$set": {"construction_progress": overall,
                                           "units_progress": units_progress,
                                           "units_scheduled": len(scheds),
                                           "updated_at": ts}})
    return overall


def build_s_curve(phases: list) -> dict:
    """Cumulative weighted S-curve: planned vs actual completion %."""
    ordered = sorted(phases, key=lambda p: (p.get("order", 0), p.get("name", "")))
    total_w = sum(p.get("weight", 0) for p in ordered) or 1
    planned_cum = actual_cum = 0.0
    points = [{"name": "Mulai", "planned": 0, "actual": 0}]
    for p in ordered:
        w = p.get("weight", 0)
        planned_cum += w * (p.get("planned_pct", 0) / 100.0)
        actual_cum += w * (p.get("progress", 0) / 100.0)
        points.append({
            "name": p.get("name"),
            "planned": round(planned_cum / total_w * 100),
            "actual": round(actual_cum / total_w * 100),
        })
    op = round(planned_cum / total_w * 100)
    oa = round(actual_cum / total_w * 100)
    return {"points": points, "overall_planned": op, "overall_actual": oa,
            "deviation": oa - op, "behind": (oa - op) <= -10}


async def material_book_stock(project_id: str, material_id: str, org_id: str = ORG_ID) -> float:
    """Book stock = sum(in) - sum(out) + sum(adjust signed)."""
    txns = await db.material_txns.find(
        {"org_id": org_id, "project_id": project_id, "material_id": material_id}, {"_id": 0}).to_list(5000)
    stock = 0.0
    for t in txns:
        if t.get("type") == "in":
            stock += t.get("qty", 0)
        elif t.get("type") == "out":
            stock -= t.get("qty", 0)
        else:  # adjust (signed)
            stock += t.get("qty", 0)
    return round(stock, 2)


# ----------------------------- EPIC 1.7 Automation action executor -----------------------------
async def _find_template(org, *, code=None, tid=None):
    if tid:
        return await db.wa_templates.find_one({"org_id": org, "id": tid})
    if code:
        return await db.wa_templates.find_one({"org_id": org, "code": code})
    return None


async def send_template_message(conv, template, org, variables=None, actor="automation"):
    """SIMULATION: append an OUTBOUND template message to the conversation (no external send).
    Templates bypass the 24h session-window rule (that's their WA purpose)."""
    if not conv or not template:
        return None
    ts = now_iso()
    body = template.get("body", "")
    for k, v in (variables or {}).items():
        body = body.replace("{{%s}}" % k, str(v))
    msg = {
        "id": new_id(), "org_id": org, "conversation_id": conv["id"], "direction": "out",
        "body": body, "sender": actor, "is_template": True,
        "template_id": template.get("id"), "template_code": template.get("code"),
        "mode": "simulation", "created_at": ts,
    }
    await db.messages.insert_one(msg)
    await db.conversations.update_one(
        {"id": conv["id"]}, {"$set": {"last_message_at": ts, "updated_at": ts}})
    return msg


async def run_rule_actions(rule, org, *, conv=None, lead_id=None, intent=None):
    """Execute a rule's configured actions. Human-in-the-loop by default (suggestion
    tasks); send_template posts a simulated outbound WA template message."""
    lid = lead_id or (conv.get("lead_id") if conv else None)
    owner = conv.get("owner") if conv else None
    if not owner and lid:
        _l = await db.leads.find_one({"id": lid}, {"_id": 0, "assigned_to": 1})
        owner = (_l or {}).get("assigned_to")
    anchor = (conv or {}).get("id") or lid or "na"
    executed = 0
    for a in rule.get("actions", []):
        atype = a.get("type")
        if atype == "create_task":
            r = await auto_create_task(
                source_event=f"automation:{rule['id']}:task:{anchor}",
                title=a.get("title") or f"Tindak lanjut otomasi: {rule.get('name')}"
                + (f" — intent '{intent}'" if intent else ""),
                type="follow_up",
                related_entity_type="conversation" if conv else "lead",
                related_entity_id=anchor, assigned_to=owner, priority="high",
                due_date=due_in(hours=2), sla_due_at=due_in(hours=2), org_id=org)
            executed += 1 if r else 0
        elif atype == "send_template":
            tmpl = await _find_template(org, code=a.get("template_code"), tid=a.get("template_id"))
            if tmpl and conv:
                await send_template_message(conv, tmpl, org)
                await add_activity(entity_type="conversation", entity_id=conv["id"], type="system",
                                   body=f"Template '{tmpl.get('name')}' terkirim otomatis (SIMULASI).",
                                   actor="automation", org_id=org)
                executed += 1
        elif atype == "suggest_stage" and lid:
            r = await auto_create_task(
                source_event=f"automation:{rule['id']}:stage:{lid}",
                title=f"Usulan (NBA): majukan stage lead ke '{a.get('stage', 'appointment')}'",
                type="review", related_entity_type="lead", related_entity_id=lid,
                assigned_to=owner, priority="high", due_date=due_in(hours=4),
                sla_due_at=due_in(hours=4), org_id=org)
            executed += 1 if r else 0
        elif atype == "notify" and owner:
            await create_notification(user_email=owner, title=a.get("title") or "Otomasi omnichannel",
                                      body=rule.get("name"),
                                      related_entity_type="conversation" if conv else "lead",
                                      related_entity_id=anchor, type="info", org_id=org)
            executed += 1
    if executed:
        await db.automation_rules.update_one({"id": rule["id"]}, {"$inc": {"executions": executed}})
    return executed


# ----------------------------- Event Handlers -----------------------------
async def _h_lead_created(ev):
    lead = await db.leads.find_one({"id": ev["entity_id"]})
    if not lead:
        return
    await auto_create_task(
        source_event=f"lead.created:{ev['entity_id']}", jobdesk_code="SM-01",
        title=f"Hubungi lead baru: {lead.get('name', '(tanpa nama)')}",
        type="contact", related_entity_type="lead", related_entity_id=ev["entity_id"],
        assigned_to=lead.get("assigned_to"), due_date=due_in(minutes=5),
        sla_due_at=due_in(minutes=5), priority="urgent", org_id=ev.get("org_id", ORG_ID),
    )
    await add_activity(entity_type="lead", entity_id=ev["entity_id"], type="system",
                       body="Lead baru dibuat dan masuk pipeline.", actor="system",
                       org_id=ev.get("org_id", ORG_ID))


async def _h_lead_captured(ev):
    lead = await db.leads.find_one({"id": ev["entity_id"]})
    if not lead:
        return
    org = ev.get("org_id", ORG_ID)
    await auto_create_task(
        source_event=f"lead.captured:{ev['entity_id']}", jobdesk_code="SM-01",
        title=f"Hubungi lead (<=5 menit): {lead.get('name', '(tanpa nama)')}",
        type="contact", related_entity_type="lead", related_entity_id=ev["entity_id"],
        assigned_to=lead.get("assigned_to"), due_date=due_in(minutes=5),
        sla_due_at=due_in(minutes=5), priority="urgent", org_id=org,
    )
    # Run lead.captured automation rules (e.g. first-touch welcome template).
    conv = await db.conversations.find_one({"org_id": org, "lead_id": ev["entity_id"]})
    rules = await db.automation_rules.find({
        "org_id": org, "is_active": True, "trigger.event": "lead.captured",
    }).to_list(100)
    for r in rules:
        await run_rule_actions(r, org, conv=conv, lead_id=ev["entity_id"])


async def _h_message_received(ev):
    """Automation rule engine: keyword intent -> configured actions (human-in-the-loop)."""
    org = ev.get("org_id", ORG_ID)
    rules = await db.automation_rules.find({
        "org_id": org, "is_active": True, "trigger.event": "message.received",
    }).to_list(100)
    body = (ev["data"].get("body") or "").lower()
    conv_id = ev["entity_id"]
    conv = await db.conversations.find_one({"id": conv_id}) or {}
    for r in rules:
        kws = r.get("trigger", {}).get("keywords", [])
        matched = next((k for k in kws if k in body), None)
        if matched:
            await run_rule_actions(r, org, conv=conv, intent=matched)


HANDLERS = {
    "lead.created": [_h_lead_created],
    "lead.captured": [_h_lead_captured],
    "message.received": [_h_message_received],
    "deal.booked": [],  # populated below (lazy-imports finance_engine to avoid cycle)
    # later phases: unit.bast, payment.paid_off, etc.
}


async def _h_deal_booked(ev):
    """On booking: generate AR schedule (default scheme) + commission (if trigger=booked)."""
    deal = await db.deals.find_one({"id": ev["entity_id"]}, {"_id": 0})
    if not deal:
        return
    org = ev.get("org_id", ORG_ID)
    # Lazy import to avoid circular import (finance_engine imports engine).
    from finance_engine import create_ar_for_deal, create_commission_for_deal
    try:
        await create_ar_for_deal(deal, org_id=org)
        await create_commission_for_deal(deal, org_id=org, trigger="booked")
    except Exception:  # noqa: BLE001
        logger.exception("Finance artifact generation failed for deal %s", deal.get("id"))


HANDLERS["deal.booked"] = [_h_deal_booked]


async def _h_deal_won(ev):
    """Fase 29b: tahap lead `won` HANYA lahir dari bukti legal (AJB/serah terima/lunas)."""
    import lead_lifecycle as lc
    deal = await db.deals.find_one({"id": ev["entity_id"]}, {"_id": 0})
    if not deal:
        return
    try:
        await lc.advance_on_deal(deal, stage="won", actor="system",
                                 reason=f"Deal {ev['type'].split('.')[-1].upper()} selesai")
    except Exception:  # noqa: BLE001
        logger.exception("Gagal menaikkan lead ke 'won' untuk deal %s", deal.get("id"))


HANDLERS["deal.sold"] = [_h_deal_won]
HANDLERS["deal.ajb"] = [_h_deal_won]
HANDLERS["payment.paid_off"] = HANDLERS.get("payment.paid_off", [])


# ----------------------------- Fase 29: Work Hub (jobdesk per divisi) -----------------------------
async def _h_jobdesk(ev):
    """Setiap event yang punya jobdesk melahirkan/melengkapi task divisi terkait.

    Import di dalam fungsi untuk memutus siklus impor (workhub -> engine -> workhub).
    """
    import workhub as wh
    try:
        await wh.dispatch_jobdesk_event(ev)
    except Exception:  # noqa: BLE001
        logger.exception("Work Hub jobdesk dispatch gagal untuk event %s", ev.get("type"))


def _register_jobdesk_handlers():
    import jobdesk_catalog as cat
    for etype in cat.EVENT_CODES:
        HANDLERS.setdefault(etype, [])
        if _h_jobdesk not in HANDLERS[etype]:
            HANDLERS[etype].append(_h_jobdesk)


_register_jobdesk_handlers()


async def _workhub_tick() -> int:
    """Ubah kondisi nyata menjadi event Work Hub (WA belum dibalas, survey H-1, dll)."""
    import workhub as wh
    made = 0
    try:
        res = await wh.workhub_sweeper()
        made = sum(res.values())
        if made:
            await dispatch_pending()
    except Exception:  # noqa: BLE001
        logger.exception("Work Hub sweeper gagal")
    return made


async def _workhub_report_tick() -> int:
    """Fase 29d: snapshot rapor mingguan divisi + kirim ringkasannya ke supervisor."""
    import workhub_report as wr
    try:
        return await wr.report_tick()
    except Exception:  # noqa: BLE001
        logger.exception("Rapor mingguan Work Hub gagal")
        return 0


async def _capture_retry_tick() -> dict:
    """Fase 30c: coba ulang otomatis lead yang gagal masuk karena gangguan sementara."""
    import capture_failures as cf
    try:
        return await cf.auto_retry_tick()
    except Exception:  # noqa: BLE001
        logger.exception("Retry otomatis lead gagal masuk bermasalah")
        return {"tried": 0, "recovered": 0}


async def _wa_playbook_tick() -> int:
    """Fase 29b: playbook WA per tahap lead (reminder/follow-up) yang boleh kirim otomatis."""
    import wa_playbooks as wp
    try:
        res = await wp.playbook_tick()
        return sum(r.get("sent", 0) + r.get("tasks", 0) for r in res.values())
    except Exception:  # noqa: BLE001
        logger.exception("Playbook WA gagal")
        return 0


async def _workhub_recurring_tick() -> int:
    import workhub as wh
    try:
        return await wh.recurring_tick()
    except Exception:  # noqa: BLE001
        logger.exception("Work Hub recurring gagal")
        return 0


# ----------------------------- Dispatcher + Scheduler -----------------------------
async def dispatch_pending(limit: int = 200) -> int:
    pending = await db.events.find({"status": "pending"}).sort("created_at", 1).to_list(limit)
    for ev in pending:
        try:
            for handler in HANDLERS.get(ev["type"], []):
                await handler(ev)
            await db.events.update_one({"id": ev["id"]},
                                       {"$set": {"status": "dispatched", "dispatched_at": now_iso()}})
        except Exception as e:  # noqa: BLE001
            logger.exception("Event dispatch failed: %s", ev.get("type"))
            retries = ev.get("retries", 0) + 1
            await db.events.update_one({"id": ev["id"]}, {
                "$set": {"last_error": str(e), "status": "failed" if retries >= 3 else "pending"},
                "$inc": {"retries": 1},
            })
    return len(pending)


async def reservation_expiry_sweeper() -> int:
    swept = 0
    cur = await db.deals.find({"status": {"$in": ["draft", "reserved"]}}).to_list(1000)
    for d in cur:
        ru = d.get("reserved_until")
        if ru and ru < now_iso():
            await db.deals.update_one({"id": d["id"]}, {"$set": {"status": "expired", "updated_at": now_iso()}})
            if d.get("unit_id"):
                await db.units.update_one({"id": d["unit_id"]}, {"$set": {"status": "available", "updated_at": now_iso()}})
            await emit("deal.expired", "deal", d["id"], {"unit_id": d.get("unit_id")}, org_id=d.get("org_id", ORG_ID))
            swept += 1
    return swept


async def stage_clock_tick() -> int:
    """Fase 41 — JARING PENGAMAN jam tahap.

    Transisi yang lewat pintu resmi (lead lifecycle, deal, komplain) menulis
    `stage_entered_at` seketika. Sisa jalur penulisan status (tugas, dokumen, AR, impor)
    masih banyak dan tersebar; daripada menambal tiga puluh tempat sekaligus (risiko regresi
    lebih besar daripada manfaatnya), sweeper ini menyamakan jam tahap setiap menit dari
    FAKTA yang tercatat (`updated_at`) dan menandai asalnya `reconcile:updated_at` supaya
    tingkat kepastiannya terlihat di data & laporan, tidak disembunyikan.
    """
    import stage_clock as clock
    filled = await clock.reconcile()
    total = sum(filled.values())
    if total:
        logger.info("Jam tahap disamakan: %s", {k: v for k, v in filled.items() if v})
    return total


async def sla_breach_check() -> int:
    breached = await db.tasks.find({
        "status": {"$in": ["open", "in_progress"]},
        "sla_due_at": {"$ne": None, "$lt": now_iso()}, "sla_breached": {"$ne": True},
    }).to_list(1000)
    for t in breached:
        await db.tasks.update_one({"id": t["id"]}, {"$set": {"sla_breached": True, "updated_at": now_iso()}})
        await create_notification(
            user_email=t.get("assigned_to"), title="SLA task terlampaui",
            body=f"Task '{t.get('title')}' telah melewati batas SLA.", type="sla",
            related_entity_type=t.get("related_entity_type"), related_entity_id=t.get("related_entity_id"),
            org_id=t.get("org_id", ORG_ID),
        )
    return len(breached)


async def permit_deadline_sweeper() -> int:
    """Corrective task + PM notification for permits due-soon or overdue (EPIC 2.7)."""
    now = now_iso()
    remind_horizon = due_in(days=14)
    pending = await db.permits.find({
        "status": {"$nin": ["approved", "rejected", "expired"]},
        "deadline": {"$ne": None},
    }).to_list(1000)
    made = 0
    for p in pending:
        deadline = p.get("deadline")
        overdue = deadline < now
        # remind window uses each permit's own reminder_days (fallback 14d horizon)
        horizon = due_in(days=p.get("reminder_days", 14)) if p.get("reminder_days") else remind_horizon
        if not overdue and deadline > horizon:
            continue
        org = p.get("org_id", ORG_ID)
        proj = await db.projects.find_one({"id": p.get("project_id")}, {"_id": 0}) or {}
        members = proj.get("members") or []
        assignee = None
        if members:
            pm = await db.users.find_one(
                {"org_id": org, "email": {"$in": members}, "role": "project_manager"},
                {"_id": 0, "email": 1})
            assignee = pm["email"] if pm else members[0]
        label = "TERLAMBAT" if overdue else "segera jatuh tempo"
        t = await auto_create_task(
            source_event=f"permit:{p['id']}:{now[:10]}", jobdesk_code="TK-08",
            title=f"Izin {p.get('type')} {label} — {proj.get('code') or p.get('project_name')}",
            type="review", related_entity_type="project", related_entity_id=p.get("project_id"),
            assigned_to=assignee, due_date=deadline, sla_due_at=deadline,
            priority="urgent" if overdue else "high", org_id=org,
            description=f"Perizinan {p.get('name')} ({p.get('type')}) {label} pada {str(deadline)[:10]}.")
        if t:
            made += 1
            await create_notification(
                user_email=assignee, title=f"Izin {p.get('type')} {label}",
                body=f"{p.get('name')} — {proj.get('name')}", type="permit",
                related_entity_type="project", related_entity_id=p.get("project_id"), org_id=org)
    return made


_scheduler = None


async def no_response_sweeper() -> int:
    """EPIC 1.7: re-engage stalled conversations per 'no_response' automation rules.
    Stalled = last message older than the rule's N days AND linked lead not advanced
    past nurturing. A per-conversation cooldown (last_reengage_at) prevents template spam."""
    made = 0
    orgs = await db.automation_rules.distinct(
        "org_id", {"is_active": True, "trigger.event": "no_response"})
    for org in orgs:
        rules = await db.automation_rules.find({
            "org_id": org, "is_active": True, "trigger.event": "no_response"}).to_list(100)
        for r in rules:
            days = r.get("trigger", {}).get("no_response_days") or 3
            cutoff = due_in(days=-days)
            convs = await db.conversations.find({
                "org_id": org, "status": {"$in": ["new", "active"]},
                "last_message_at": {"$ne": None, "$lt": cutoff}}).to_list(500)
            for c in convs:
                if c.get("last_reengage_at") and c["last_reengage_at"] > cutoff:
                    continue  # cooldown: already re-engaged within the window
                lead = await db.leads.find_one({"id": c.get("lead_id")}, {"_id": 0, "stage": 1})
                if lead and lead.get("stage") in ("booking", "won", "lost"):
                    continue
                n = await run_rule_actions(r, org, conv=c, intent="no_response")
                if n:
                    await db.conversations.update_one(
                        {"id": c["id"]}, {"$set": {"last_reengage_at": now_iso()}})
                    made += 1
    return made


async def _finance_retention_tick() -> int:
    from finance_engine import ap_retention_release_sweeper
    return await ap_retention_release_sweeper()


async def _p27_reminder_tick() -> int:
    """Fase 27: pengingat angsuran pembiayaan jatuh tempo + kas bon belum dipertanggungjawabkan."""
    import loans
    import petty_cash
    made = 0
    try:
        made += await loans.installment_reminder()
        made += await petty_cash.unsettled_reminder()
    except Exception:  # noqa: BLE001
        logger.exception("Pengingat Fase 27 gagal")
    return made


async def _build_tick() -> dict:
    """Fase 31: buka gerbang yang waktu tunggunya lewat, kirim pengingat, eskalasi telat."""
    import build_monitor as bm
    try:
        out = await bm.tick()
        if out.get("escalations") or out.get("gates_opened"):
            await dispatch_pending()
        return out
    except Exception:  # noqa: BLE001
        logger.exception("Pemantauan jadwal pembangunan gagal")
        return {"schedules": 0}


async def _bi_snapshot_tick() -> int:
    """Fase 44: snapshot metrik BI harian. Impor lokal supaya scheduler tidak menarik modul
    analitik saat modul ini dimuat (lingkar: analytics_engine → metrics → ads_report → engine).
    Pola sama dipakai Fase 45 di `scheduler_p45.py`."""
    import analytics_engine as ae
    return await ae.snapshot_tick()


async def _build_weekly_report_tick() -> dict:
    """Fase 32: laporan mingguan pembangunan untuk direksi & manajer proyek.

    Dijalankan tiap Senin pagi WIB. Idempoten per pekan: bila sudah ada laporan untuk
    pekan tersebut, angkanya disegarkan tetapi notifikasi & tugas baca tidak dibuat ulang.
    """
    import build_reports as br
    try:
        out = await br.run_weekly(ORG_ID, actor="system")
        if out.get("created"):
            logger.info("Laporan mingguan pembangunan %s: %s laporan baru",
                        out.get("week_key"), out.get("created"))
        return out
    except Exception:  # noqa: BLE001
        logger.exception("Laporan mingguan pembangunan gagal")
        return {"created": 0}


def start_scheduler():
    global _scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(dispatch_pending, "interval", seconds=8, id="dispatcher_tick",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(reservation_expiry_sweeper, "interval", seconds=300, id="expiry_sweep",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(sla_breach_check, "interval", seconds=120, id="sla_check",
                       max_instances=1, coalesce=True)
    # Fase 41 — jam tahap: samakan `stage_entered_at`/`stage_due_at` dengan status nyata.
    _scheduler.add_job(stage_clock_tick, "interval", seconds=60, id="stage_clock_tick",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(permit_deadline_sweeper, "interval", seconds=900, id="permit_check",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(_finance_retention_tick, "interval", seconds=600, id="retention_sweep",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(no_response_sweeper, "interval", seconds=900, id="no_response_sweep",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(_p27_reminder_tick, "interval", seconds=1800, id="p27_reminders",
                       max_instances=1, coalesce=True)
    # Fase 29 — Work Hub: kondisi nyata -> event (5 mnt) & task berulang (15 mnt, idempoten)
    _scheduler.add_job(_workhub_tick, "interval", seconds=300, id="workhub_sweep",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(_workhub_recurring_tick, "interval", seconds=900, id="workhub_recurring",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(_wa_playbook_tick, "interval", seconds=1200, id="wa_playbooks",
                       max_instances=1, coalesce=True)
    # Rapor mingguan: dicek tiap 6 jam, idempoten per divisi per pekan ISO.
    _scheduler.add_job(_workhub_report_tick, "interval", seconds=21600, id="workhub_report",
                       max_instances=1, coalesce=True)
    # Fase 30c — antrean lead gagal masuk: kegagalan SEMENTARA dicoba ulang tiap 10 menit
    # (maks 3 kali). Kegagalan DATA menunggu koreksi manusia, tidak diputar sia-sia.
    _scheduler.add_job(_capture_retry_tick, "interval", seconds=600, id="capture_retry",
                       max_instances=1, coalesce=True)
    # Fase 31 — jadwal pembangunan per unit: gerbang curing dibuka saat waktunya, pengingat
    # H-1/hari-H, dan eskalasi berjenjang bila item pekerjaan lewat tenggat.
    _scheduler.add_job(_build_tick, "interval", seconds=600, id="build_monitor",
                       max_instances=1, coalesce=True)
    # Senin 00:05 UTC = Senin 07:05 WIB — laporan mingguan siap sebelum rapat pagi.
    _scheduler.add_job(_build_weekly_report_tick, "cron", day_of_week="mon", hour=0,
                       minute=5, id="build_weekly_report", max_instances=1, coalesce=True)
    # Fase 44 — snapshot metrik BI: 00:20 UTC (07:20 WIB) supaya dashboard periode besar tidak
    # menghitung ulang seluruh riwayat setiap kali dibuka. Snapshot BUKAN kebenaran: ia selalu
    # bisa dihitung ulang (`POST /api/analytics/snapshots/rebuild`) dan gate membandingkannya
    # dengan hitungan langsung.
    _scheduler.add_job(_bi_snapshot_tick, "cron", hour=0, minute=20, id="bi_snapshot",
                       max_instances=1, coalesce=True)
    # Fase 45 — target dinamis (dicek tiap 6 jam, hanya menulis sekali/bulan per target),
    # ambang anggaran 01:00 UTC, dan Fase 46 — kedaluwarsa izin 02:00 UTC. Registrasinya
    # dipindah ke `scheduler_p45.register()` agar berkas ini tetap di bawah batas NFR.
    import scheduler_p45 as sched_p45
    sched_p45.register(_scheduler)
    _scheduler.start()
    logger.info("APScheduler started (dispatcher + expiry + sla + retention + no_response + "
                "pengingat + work hub + retry lead + snapshot BI + target/anggaran Fase 45 "
                "+ kedaluwarsa izin Fase 46).")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
