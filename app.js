Telegram.WebApp.ready();
Telegram.WebApp.expand();

const API_BASE = "";  // если тот же домен — пусто. Иначе — https://backend.com
let currentEventId = null;
let currentStatus = "active";
let isOrganizerAllowed = false;

// ═══ Утилиты ═══

async function apiCall(endpoint, data = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...data,
      initData: Telegram.WebApp.initData,
    }),
  });
  return res.json();
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.style.display = "none");
  document.getElementById(id).style.display = "block";
}

function showMain() {
  showScreen("screen-main");
  loadEvents(currentStatus);
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

// ═══ ГЛАВНЫЙ ЭКРАН ═══

async function loadEvents(status) {
  currentStatus = status;
  const container = document.getElementById("events-list");
  container.textContent = "Загрузка...";

  const result = await apiCall("/api/events/list", { status });
  if (!result.ok) {
    container.textContent = "Ошибка: " + (result.detail || "неизвестно");
    return;
  }

  isOrganizerAllowed = result.is_organizer_allowed;
  document.getElementById("btn-create-event").style.display =
    isOrganizerAllowed ? "block" : "none";

  if (!result.events.length) {
    container.innerHTML = status === "active"
      ? '<p style="text-align:center;color:#999;padding:40px 0;">📭 Актуальных мероприятий нет</p>'
      : '<p style="text-align:center;color:#999;padding:40px 0;">📭 Прошедших мероприятий нет</p>';
    return;
  }

  container.innerHTML = result.events.map(ev => {
    const dt = new Date(ev.event_date);
    const dateStr = dt.toLocaleString("ru-RU", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
    const past = ev.status === "past";
    return `
      <div class="event-card ${past ? "past" : ""}"
           onclick="openEvent(${ev.event_id})">
        <h3>${escapeHtml(ev.title)}</h3>
        <p style="color:#666;font-size:14px;">
          Организатор: ${escapeHtml(ev.organizer_name || "?")}
        </p>
        <p style="font-size:14px;">📅 ${dateStr}</p>
        <span class="badge ${ev.status}">
          ${past ? "Завершено" : "Активно"}
        </span>
      </div>
    `;
  }).join("");
}

// Табы
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    loadEvents(tab.dataset.status);
  });
});

// ═══ КОД ОРГАНИЗАТОРА ═══

document.getElementById("btn-enter-code").addEventListener("click", () => {
  showScreen("screen-code");
});

document.getElementById("btn-save-code").addEventListener("click", async () => {
  const code = document.getElementById("org-code-input").value.trim();
  if (!code) return Telegram.WebApp.showAlert("Введите код");

  const result = await apiCall("/api/become-organizer", { code });
  if (result.ok) {
    Telegram.WebApp.showAlert("Вы стали организатором!");
    isOrganizerAllowed = true;
    showMain();
  } else {
    Telegram.WebApp.showAlert("Ошибка: " + (result.detail || "неверный код"));
  }
});

// ═══ СОЗДАНИЕ МЕРОПРИЯТИЯ ═══

document.getElementById("btn-create-event").addEventListener("click", () => {
  showScreen("screen-create");
});

document.getElementById("btn-save-event").addEventListener("click", async () => {
  const title = document.getElementById("ev-title").value.trim();
  const desc = document.getElementById("ev-desc").value.trim();
  const date = document.getElementById("ev-date").value;

  if (!title || !date) {
    return Telegram.WebApp.showAlert("Заполните название и дату");
  }

  const result = await apiCall("/api/events/create", {
    title, description: desc, event_date: date,
  });

  if (result.ok) {
    Telegram.WebApp.showAlert("Мероприятие создано");
    document.getElementById("ev-title").value = "";
    document.getElementById("ev-desc").value = "";
    showMain();
  } else {
    Telegram.WebApp.showAlert("Ошибка: " + (result.detail || "?"));
  }
});

// ═══ КАРТОЧКА МЕРОПРИЯТИЯ ═══

async function openEvent(eventId) {
  currentEventId = eventId;
  showScreen("screen-event");

  const result = await apiCall("/api/events/get", { event_id: eventId });
  if (!result.ok) {
    Telegram.WebApp.showAlert("Ошибка загрузки");
    return;
  }

  const ev = result.event;
  document.getElementById("event-title").textContent = ev.title;
  document.getElementById("event-meta").textContent =
    `Организатор: ${ev.organizer_name} · 📅 ${new Date(ev.event_date).toLocaleString("ru-RU")}`;

  // Бейдж
  const past = ev.status === "past";
  document.getElementById("event-status-badge").innerHTML =
    `<span class="badge ${ev.status}">${past ? "Завершено" : "Активно"}</span>`;

  // Участники
  document.getElementById("event-members").innerHTML = ev.members.map(m => `
    <div class="member-row">
      ${m.role === "organizer" ? "👑" : "•"}
      ${escapeHtml(m.first_name || "Без имени")}
      ${m.username ? `<span style="color:#999;"> @${escapeHtml(m.username)}</span>` : ""}
      ${m.role === "organizer" ? '<span class="role"> (организатор)</span>' : ""}
    </div>
  `).join("");

  // Кнопки
  const isOrg = ev.my_role === "organizer";
  document.getElementById("btn-create-poll").style.display =
    (isOrg && !past) ? "block" : "none";
  document.getElementById("btn-leave").style.display = (!isOrg && !past) ? "block" : "none";
  document.getElementById("btn-finish").style.display = (isOrg && !past) ? "block" : "none";
  document.getElementById("btn-delete-event").style.display = (isOrg && past) ? "block" : "none";

  // Ссылка-приглашение
  if (isOrg && !past && ev.invite_code) {
    document.getElementById("invite-block").style.display = "block";
    const botUsername = Telegram.WebApp.initDataUnsafe?.user
      ? "" : "";
    // Ссылка в Mini App (startapp):
    const link = `https://t.me/${getBotUsername()}?start=evt_${ev.invite_code}`;
    document.getElementById("invite-link").textContent = link;
    document.getElementById("btn-copy-invite").onclick = () => {
      navigator.clipboard.writeText(link);
      Telegram.WebApp.showAlert("Ссылка скопирована");
    };
  } else {
    document.getElementById("invite-block").style.display = "none";
  }

  loadPolls(eventId, past);
}

// Имя бота — подставьте своё
function getBotUsername() {
  return "your_bot_username";  // ← ЗАМЕНИТЕ
}

// ═══ ОПРОСЫ ═══

async function loadPolls(eventId, past) {
  const container = document.getElementById("event-polls");
  container.textContent = "Загрузка...";

  const result = await apiCall("/api/polls/list", { event_id: eventId });
  if (!result.ok) {
    container.textContent = "Ошибка";
    return;
  }

  if (!result.polls.length) {
    container.innerHTML = '<p style="color:#999;">📭 Опросов нет</p>';
    return;
  }

  container.innerHTML = result.polls.map(poll => {
    const optionsHtml = poll.options.map(opt => {
      const isMine = poll.my_vote === opt.option_id;
      const disabled = past ? "disabled" : "";
      return `
        <button class="poll-option-btn ${isMine ? "my-vote" : ""}"
                ${disabled}
                onclick="vote(${poll.poll_id}, ${opt.option_id})">
          ${isMine ? "✓ " : ""}${escapeHtml(opt.option_text)} — ${opt.votes}
        </button>
      `;
    }).join("");

    let meta = "";
    if (poll.deadline && !past) {
      meta = `<p style="font-size:12px;color:#999;">
        ⏰ до ${new Date(poll.deadline).toLocaleString("ru-RU")}
      </p>`;
    }

    return `
      <div class="poll-block">
        <p><strong>${escapeHtml(poll.theme)}</strong></p>
        ${meta}
        ${optionsHtml}
      </div>
    `;
  }).join("");
}

async function vote(pollId, optionId) {
  const result = await apiCall("/api/polls/vote", {
    poll_id: pollId, option_id: optionId,
  });
  if (result.ok) {
    Telegram.WebApp.HapticFeedback.impactOccurred("light");
    loadPolls(currentEventId, false);
  } else {
    Telegram.WebApp.showAlert("Ошибка: " + (result.detail || "?"));
  }
}

// ═══ СОЗДАНИЕ ОПРОСА ═══

document.getElementById("btn-create-poll").addEventListener("click", () => {
  showScreen("screen-create-poll");
  document.getElementById("poll-theme").value = "";
  document.getElementById("poll-options").innerHTML = `
    <input type="text" class="poll-option" placeholder="Вариант 1" />
    <input type="text" class="poll-option" placeholder="Вариант 2" />
  `;
});

function closePollCreate() {
  showScreen("screen-event");
}

document.getElementById("btn-add-option").addEventListener("click", () => {
  const div = document.createElement("input");
  div.type = "text";
  div.className = "poll-option";
  div.placeholder = `Вариант ${document.querySelectorAll(".poll-option").length + 1}`;
  document.getElementById("poll-options").appendChild(div);
});

document.getElementById("btn-save-poll").addEventListener("click", async () => {
  const theme = document.getElementById("poll-theme").value.trim();
  const options = Array.from(document.querySelectorAll(".poll-option"))
    .map(o => o.value.trim())
    .filter(Boolean);
  const deadline = document.getElementById("poll-deadline").value || null;

  if (!theme || options.length < 2) {
    return Telegram.WebApp.showAlert("Нужна тема и минимум 2 варианта");
  }

  const result = await apiCall("/api/polls/create", {
    event_id: currentEventId,
    theme, options, deadline,
  });

  if (result.ok) {
    Telegram.WebApp.showAlert("Опрос создан");
    showScreen("screen-event");
    loadPolls(currentEventId, false);
  } else {
    Telegram.WebApp.showAlert("Ошибка: " + (result.detail || "?"));
  }
});

// ═══ ДЕЙСТВИЯ МЕРОПРИЯТИЯ ═══

document.getElementById("btn-leave").addEventListener("click", () => {
  Telegram.WebApp.showConfirm(
    "Выйти из мероприятия? Все ваши голоса будут удалены.",
    async (ok) => {
      if (!ok) return;
      const r = await apiCall("/api/events/leave", { event_id: currentEventId });
      if (r.ok) {
        Telegram.WebApp.showAlert("Вы вышли");
        showMain();
      } else {
        Telegram.WebApp.showAlert("Ошибка: " + (r.detail || "?"));
      }
    }
  );
});

document.getElementById("btn-finish").addEventListener("click", () => {
  Telegram.WebApp.showConfirm(
    "Завершить мероприятие? Оно перейдёт в «Прошедшие».",
    async (ok) => {
      if (!ok) return;
      const r = await apiCall("/api/events/finish", { event_id: currentEventId });
      if (r.ok) {
        Telegram.WebApp.showAlert("Мероприятие завершено");
        showMain();
      } else {
        Telegram.WebApp.showAlert("Ошибка: " + (r.detail || "?"));
      }
    }
  );
});

document.getElementById("btn-delete-event").addEventListener("click", () => {
  Telegram.WebApp.showConfirm(
    "Удалить навсегда? Данные восстановить нельзя.",
    (ok1) => {
      if (!ok1) return;
      Telegram.WebApp.showConfirm(
        "Вы точно уверены?",
        async (ok2) => {
          if (!ok2) return;
          const r = await apiCall("/api/events/delete", { event_id: currentEventId });
          if (r.ok) {
            Telegram.WebApp.showAlert("Удалено");
            showMain();
          } else {
            Telegram.WebApp.showAlert("Ошибка: " + (r.detail || "?"));
          }
        }
      );
    }
  );
});

// ═══ СТАРТ ═══

// Обработка startapp (приглашение через ссылку приложения)
const startParam = Telegram.WebApp.initDataUnsafe?.start_param;
if (startParam && startParam.startsWith("evt_")) {
  const inviteCode = startParam.replace("evt_", "");
  apiCall("/api/events/join", { invite_code: inviteCode }).then(() => {
    Telegram.WebApp.showAlert("Вы записаны на мероприятие!");
  });
}

loadEvents("active");