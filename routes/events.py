from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import aiosqlite
import secrets

from auth import validate_init_data
from db import get_db

router = APIRouter(prefix="/api/events")


async def get_user_id(init_data: str) -> int:
    return validate_init_data(init_data)["id"]


async def require_organizer_allowed(user_id: int, db):
    cursor = await db.execute(
        "SELECT is_organizer_allowed FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    if not row or not row["is_organizer_allowed"]:
        raise HTTPException(403, "Только организатор может создавать мероприятия")


async def require_event_member(user_id: int, event_id: int, db):
    cursor = await db.execute(
        "SELECT role FROM event_members WHERE event_id = ? AND user_id = ?",
        (event_id, user_id)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(403, "Вы не участник этого мероприятия")
    return row["role"]


async def require_event_organizer(user_id: int, event_id: int, db):
    role = await require_event_member(user_id, event_id, db)
    if role != "organizer":
        raise HTTPException(403, "Только организатор мероприятия")


async def is_event_past(event_id: int, db) -> bool:
    cursor = await db.execute(
        "SELECT is_active, event_date FROM events WHERE event_id = ?", (event_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Мероприятие не найдено")
    if row["is_active"] == 0:
        return True
    try:
        dt = datetime.fromisoformat(row["event_date"].replace("Z", ""))
    except Exception:
        return False
    return dt < datetime.utcnow()


async def require_active_event(event_id: int, db):
    if await is_event_past(event_id, db):
        raise HTTPException(403, "Мероприятие завершено")


@router.post("/list")
async def list_events(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    status = req.get("status", "active")
    user_id = await get_user_id(init_data)

    if status == "active":
        where = "AND e.is_active = 1 AND e.event_date >= CURRENT_TIMESTAMP"
        order = "ORDER BY e.event_date ASC"
    elif status == "past":
        where = "AND (e.is_active = 0 OR e.event_date < CURRENT_TIMESTAMP)"
        order = "ORDER BY e.event_date DESC"
    else:
        where = ""
        order = "ORDER BY e.event_date ASC"

    cursor = await db.execute(f"""
        SELECT e.event_id, e.title, e.description, e.event_date,
               e.is_active, e.organizer_id,
               u.first_name AS organizer_name,
               m.role
        FROM events e
        JOIN event_members m ON m.event_id = e.event_id
        JOIN users u ON u.user_id = e.organizer_id
        WHERE m.user_id = ? {where}
        {order}
    """, (user_id,))
    rows = await cursor.fetchall()

    events = []
    for row in rows:
        ev = dict(row)
        is_past = (ev["is_active"] == 0 or
                   datetime.fromisoformat(ev["event_date"].replace("Z", "")) < datetime.utcnow())
        ev["status"] = "past" if is_past else "active"
        events.append(ev)

    c = await db.execute(
        "SELECT is_organizer_allowed FROM users WHERE user_id = ?", (user_id,)
    )
    u = await c.fetchone()

    return {
        "ok": True,
        "is_organizer_allowed": bool(u["is_organizer_allowed"]) if u else False,
        "events": events,
    }


@router.post("/create")
async def create_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    title = req.get("title", "").strip()
    description = req.get("description", "").strip()
    event_date = req.get("event_date")

    if not title or not event_date:
        raise HTTPException(400, "title и event_date обязательны")

    user_id = await get_user_id(init_data)
    await require_organizer_allowed(user_id, db)

    invite_code = secrets.token_urlsafe(8)

    await db.execute("""
        INSERT INTO events (title, description, event_date, organizer_id, invite_code)
        VALUES (?, ?, ?, ?, ?)
    """, (title, description, event_date, user_id, invite_code))

    cursor = await db.execute("SELECT last_insert_rowid() AS id")
    event_id = (await cursor.fetchone())["id"]

    await db.execute("""
        INSERT INTO event_members (event_id, user_id, role)
        VALUES (?, ?, 'organizer')
    """, (event_id, user_id))

    await db.commit()
    return {"ok": True, "event_id": event_id, "invite_code": invite_code}


@router.post("/join")
async def join_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    code = req.get("invite_code", "").strip()
    if not code:
        raise HTTPException(400, "Нет invite_code")

    user_id = await get_user_id(init_data)

    cursor = await db.execute(
        "SELECT event_id FROM events WHERE invite_code = ?", (code,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Код не найден")
    event_id = row["event_id"]

    if await is_event_past(event_id, db):
        raise HTTPException(403, "Мероприятие завершено")

    await db.execute("""
        INSERT INTO event_members (event_id, user_id, role)
        VALUES (?, ?, 'member')
        ON CONFLICT (event_id, user_id) DO NOTHING
    """, (event_id, user_id))
    await db.commit()

    return {"ok": True, "event_id": event_id}


@router.post("/get")
async def get_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    user_id = await get_user_id(init_data)
    role = await require_event_member(user_id, event_id, db)

    cursor = await db.execute("""
        SELECT e.*, u.first_name AS organizer_name
        FROM events e
        JOIN users u ON u.user_id = e.organizer_id
        WHERE e.event_id = ?
    """, (event_id,))
    ev = dict(await cursor.fetchone())

    ev["status"] = "past" if await is_event_past(event_id, db) else "active"
    ev["my_role"] = role

    c = await db.execute("""
        SELECT u.user_id, u.first_name, u.username, m.role
        FROM event_members m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.event_id = ?
        ORDER BY m.role DESC, m.joined_at
    """, (event_id,))
    ev["members"] = [dict(r) for r in await c.fetchall()]

    return {"ok": True, "event": ev}


@router.post("/leave")
async def leave_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    user_id = await get_user_id(init_data)

    role = await require_event_member(user_id, event_id, db)
    if role == "organizer":
        raise HTTPException(400, "Сначала передайте роль организатора")

    if await is_event_past(event_id, db):
        raise HTTPException(403, "Мероприятие завершено")

    await db.execute("""
        DELETE FROM votes
        WHERE user_id = ? AND poll_id IN
            (SELECT poll_id FROM polls WHERE event_id = ?)
    """, (user_id, event_id))
    await db.execute(
        "DELETE FROM event_members WHERE event_id = ? AND user_id = ?",
        (event_id, user_id)
    )
    await db.commit()
    return {"ok": True}


@router.post("/finish")
async def finish_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    user_id = await get_user_id(init_data)
    await require_event_organizer(user_id, event_id, db)

    await db.execute(
        "UPDATE events SET is_active = 0, finished_at = CURRENT_TIMESTAMP WHERE event_id = ?",
        (event_id,)
    )
    await db.commit()
    return {"ok": True}


@router.post("/delete")
async def delete_event(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    user_id = await get_user_id(init_data)
    await require_event_organizer(user_id, event_id, db)

    if not await is_event_past(event_id, db):
        raise HTTPException(400, "Сначала завершите мероприятие")

    await db.execute("""
        DELETE FROM votes WHERE poll_id IN
            (SELECT poll_id FROM polls WHERE event_id = ?)
    """, (event_id,))
    await db.execute("""
        DELETE FROM poll_options WHERE poll_id IN
            (SELECT poll_id FROM polls WHERE event_id = ?)
    """, (event_id,))
    await db.execute("DELETE FROM polls WHERE event_id = ?", (event_id,))
    await db.execute("DELETE FROM event_members WHERE event_id = ?", (event_id,))
    await db.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
    await db.commit()
    return {"ok": True}