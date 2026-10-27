from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db import get_db
from routes.events import (
    get_user_id, require_event_member, require_event_organizer,
    require_active_event, is_event_past
)

router = APIRouter(prefix="/api/polls")


@router.post("/list")
async def list_polls(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    user_id = await get_user_id(init_data)
    await require_event_member(user_id, event_id, db)

    cursor = await db.execute(
        "SELECT poll_id, theme, deadline, is_active FROM polls WHERE event_id = ? AND is_active = 1",
        (event_id,)
    )
    polls = []
    for p in await cursor.fetchall():
        poll = dict(p)
        c = await db.execute("""
            SELECT o.option_id, o.option_text,
                   (SELECT COUNT(*) FROM votes v WHERE v.option_id = o.option_id) AS votes
            FROM poll_options o WHERE o.poll_id = ?
            ORDER BY votes DESC, o.option_id
        """, (poll["poll_id"],))
        poll["options"] = [dict(o) for o in await c.fetchall()]

        c = await db.execute(
            "SELECT option_id FROM votes WHERE poll_id = ? AND user_id = ?",
            (poll["poll_id"], user_id)
        )
        v = await c.fetchone()
        poll["my_vote"] = v["option_id"] if v else None
        polls.append(poll)

    return {"ok": True, "polls": polls}


@router.post("/create")
async def create_poll(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    event_id = req.get("event_id")
    theme = req.get("theme", "").strip()
    options = req.get("options", [])
    deadline = req.get("deadline")

    if not theme or len(options) < 2:
        raise HTTPException(400, "Нужна тема и минимум 2 варианта")

    user_id = await get_user_id(init_data)
    await require_event_organizer(user_id, event_id, db)
    await require_active_event(event_id, db)

    await db.execute(
        "INSERT INTO polls (event_id, theme, deadline) VALUES (?, ?, ?)",
        (event_id, theme, deadline)
    )
    c = await db.execute("SELECT last_insert_rowid() AS id")
    poll_id = (await c.fetchone())["id"]

    for opt in options:
        if opt.strip():
            await db.execute(
                "INSERT INTO poll_options (poll_id, option_text) VALUES (?, ?)",
                (poll_id, opt.strip())
            )
    await db.commit()
    return {"ok": True, "poll_id": poll_id}


@router.post("/vote")
async def vote(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    poll_id = req.get("poll_id")
    option_id = req.get("option_id")
    user_id = await get_user_id(init_data)

    c = await db.execute("SELECT event_id FROM polls WHERE poll_id = ?", (poll_id,))
    row = await c.fetchone()
    if not row:
        raise HTTPException(404, "Опрос не найден")
    event_id = row["event_id"]

    await require_event_member(user_id, event_id, db)
    await require_active_event(event_id, db)

    c = await db.execute(
        "SELECT 1 FROM poll_options WHERE option_id = ? AND poll_id = ?",
        (option_id, poll_id)
    )
    if not await c.fetchone():
        raise HTTPException(400, "Неверный вариант")

    await db.execute("""
        INSERT INTO votes (poll_id, user_id, option_id)
        VALUES (?, ?, ?)
        ON CONFLICT (poll_id, user_id) DO UPDATE SET option_id = excluded.option_id
    """, (poll_id, user_id, option_id))
    await db.commit()
    return {"ok": True}


@router.post("/delete")
async def delete_poll(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    poll_id = req.get("poll_id")
    user_id = await get_user_id(init_data)

    c = await db.execute("SELECT event_id FROM polls WHERE poll_id = ?", (poll_id,))
    row = await c.fetchone()
    if not row:
        raise HTTPException(404, "Опрос не найден")
    event_id = row["event_id"]

    await require_event_organizer(user_id, event_id, db)

    await db.execute("DELETE FROM votes WHERE poll_id = ?", (poll_id,))
    await db.execute("DELETE FROM poll_options WHERE poll_id = ?", (poll_id,))
    await db.execute("DELETE FROM polls WHERE poll_id = ?", (poll_id,))
    await db.commit()
    return {"ok": True}