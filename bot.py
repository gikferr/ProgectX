    header = f"🗳️ {'Результаты' if is_past else 'Опросы'} «{ev['title']}»:\n\n"
    text = header
    for poll in polls:
        text += f"❓️ {poll['theme']}"
        if poll["deadline"] and not is_past:
            text += f" (до {poll['deadline'][:16]})"
        text += "\n"
        c = await db.execute("""
            SELECT o.option_text, COUNT(v.vote_id) AS cnt
            FROM poll_options o
            LEFT JOIN votes v ON v.option_id = o.option_id
            WHERE o.poll_id = ?
            GROUP BY o.option_id
            ORDER BY cnt DESC
        """, (poll["poll_id"],))
        for opt in await c.fetchall():
            text += f"   • {opt['option_text']} — {opt['cnt']}\n"
        text += "\n"

    if is_past:
        text += "_Голосование закрыто_"

    await cb.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="polls_menu")]
        ])
    )
    await db.close()


@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.edit_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_menu_kb()
    )
