/* ═══════════════════════════════════════════════════════════
   個資確認系統 — Frontend Logic (Vanilla JS)
═══════════════════════════════════════════════════════════ */

// ── Globals ────────────────────────────────────────────
let currentUser = null;
let classroom = null;

// ── 欄位中文標籤 ────────────────────────────────────────
const FIELD_LABEL = {
  seat: "座號", student_id: "學號", name: "姓名", gender: "性別",
  national_id: "身分證字號", dob: "出生日期", blood: "血型", religion: "宗教信仰",
  address_household: "戶籍地址", address_mailing: "通訊地址",
  phone: "學生電話", home_phone: "家用電話",
  father_name: "父親姓名", father_phone: "父親電話", father_job: "父親職業",
  mother_name: "母親姓名", mother_phone: "母親電話", mother_job: "母親職業",
  emergency_name: "緊急聯絡人", emergency_phone: "緊急聯絡電話", emergency_relation: "與本人關係",
};

// 個資分組顯示（學生確認頁更清楚）
const FIELD_GROUPS = [
  { title: "基本資料", fields: ["seat", "student_id", "name", "gender", "national_id", "dob", "blood", "religion"] },
  { title: "聯絡資訊", fields: ["address_household", "address_mailing", "phone", "home_phone"] },
  { title: "家長資料", fields: ["father_name", "father_phone", "father_job", "mother_name", "mother_phone", "mother_job"] },
  { title: "緊急聯絡", fields: ["emergency_name", "emergency_phone", "emergency_relation"] },
];

const ROLE_NAME = {
  student:   "學生",
  officer:   "學藝股長",
  registrar: "註冊組長",
};

// ── API helper ─────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, status: res.status, data };
}

// ── Page switcher ──────────────────────────────────────
function showPage(id) {
  document.querySelectorAll(".page").forEach(p => p.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
  if (id === "page-login") {
    document.getElementById("topbar").classList.add("hidden");
  } else {
    document.getElementById("topbar").classList.remove("hidden");
  }
}

// ── Login ──────────────────────────────────────────────
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const errBox = document.getElementById("login-error");
  errBox.textContent = "";
  const r = await api("/api/login", { method: "POST", body: JSON.stringify({ username, password }) });
  if (!r.ok) {
    errBox.textContent = (r.data && r.data.error) || "登入失敗";
    return;
  }
  currentUser = r.data.user;
  await afterLogin();
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  currentUser = null;
  showPage("page-login");
  document.getElementById("login-username").value = "";
  document.getElementById("login-password").value = "";
});

// ── Init / route ───────────────────────────────────────
async function checkSession() {
  const r = await api("/api/me");
  if (r.ok && r.data.ok) {
    currentUser = r.data.user;
    await afterLogin();
  } else {
    showPage("page-login");
  }
}

async function afterLogin() {
  // 取班級資訊
  const cr = await api("/api/classroom");
  if (cr.ok && cr.data.classroom) {
    classroom = cr.data.classroom;
    document.getElementById("classroom-info").textContent =
      `${classroom.school} ${classroom.grade}${classroom.class_name} (${classroom.academic_year}學年度${classroom.semester})`;
  }
  // 設 topbar
  const badge = document.getElementById("role-badge");
  badge.textContent = ROLE_NAME[currentUser.role] || currentUser.role;
  badge.className = "badge " + currentUser.role;
  document.getElementById("display-name").textContent = currentUser.display_name;

  // 路由到對應頁
  if (currentUser.role === "student") {
    await loadStudentPage();
  } else if (currentUser.role === "officer") {
    await loadOfficerPage();
  } else if (currentUser.role === "registrar") {
    await loadRegistrarPage();
  }
}

// ════════════════════ 學生頁 ════════════════════
async function loadStudentPage() {
  showPage("page-student");
  const r = await api("/api/student/me");
  if (!r.ok) return alert((r.data && r.data.error) || "無法取得個資");
  const s = r.data.student;
  renderStudentInfo("student-info", s, false);
  renderConfirmBanner(s);
  document.getElementById("student-note").value = s.note || "";

  document.getElementById("confirm-btn").onclick = async () => {
    if (!confirm("確認後將鎖定此筆資料，若需修改要聯繫註冊組。確定？")) return;
    const r = await api("/api/student/confirm", { method: "POST" });
    if (r.ok) await loadStudentPage();
    else alert("確認失敗");
  };
  document.getElementById("save-note-btn").onclick = async () => {
    const note = document.getElementById("student-note").value;
    const r = await api("/api/student/note", { method: "POST", body: JSON.stringify({ note }) });
    document.getElementById("note-saved-msg").textContent = r.ok ? "✓ 已儲存" : "✗ 失敗";
    setTimeout(() => { document.getElementById("note-saved-msg").textContent = ""; }, 2000);
  };
}

function renderStudentInfo(containerId, s, editable) {
  const root = document.getElementById(containerId);
  root.innerHTML = "";
  for (const group of FIELD_GROUPS) {
    const h = document.createElement("div");
    h.className = "section-header";
    h.textContent = group.title;
    root.appendChild(h);
    for (const f of group.fields) {
      const cell = document.createElement("div");
      cell.className = "info-row";
      cell.innerHTML = `
        <div class="label">${FIELD_LABEL[f] || f}</div>
        <div class="value">${escapeHtml(String(s[f] ?? ""))}</div>
      `;
      root.appendChild(cell);
    }
  }
}

function renderConfirmBanner(s) {
  const box = document.getElementById("confirm-status-banner");
  if (s.confirmed) {
    box.className = "banner success";
    box.innerHTML = `<strong>✓ 已確認</strong>　確認時間：${escapeHtml(s.confirmed_at || "")}`;
    document.getElementById("confirm-btn").disabled = true;
    document.getElementById("confirm-btn").textContent = "✓ 已確認";
    document.getElementById("confirm-btn").style.opacity = 0.6;
  } else {
    box.className = "banner warning";
    box.innerHTML = `<strong>⚠ 尚未確認</strong>　請核對資料後按下方確認鈕`;
  }
}

// ════════════════════ 學藝股長頁 ════════════════════
async function loadOfficerPage() {
  showPage("page-officer");
  // 全班狀態
  const r = await api("/api/class/status");
  if (!r.ok) return alert("讀取失敗");
  const list = r.data.students;
  const sum = r.data.summary;

  // summary
  const sb = document.getElementById("officer-summary");
  sb.innerHTML = `
    <div class="stat"><div class="num">${sum.total}</div><div class="label">全班人數</div></div>
    <div class="stat success"><div class="num">${sum.confirmed}</div><div class="label">已確認</div></div>
    <div class="stat warning"><div class="num">${sum.pending}</div><div class="label">待確認</div></div>
  `;

  // table
  const tbody = document.getElementById("officer-tbody");
  tbody.innerHTML = list.map(s => `
    <tr>
      <td class="seat-cell">${s.seat}</td>
      <td>${escapeHtml(s.name)}</td>
      <td>${s.confirmed
          ? '<span class="pill confirmed">✓ 已確認</span>'
          : '<span class="pill pending">⌛ 待確認</span>'}</td>
      <td class="muted small">${escapeHtml(s.confirmed_at || "—")}</td>
    </tr>
  `).join("");

  // 自己的個資
  const me = await api("/api/student/me");
  if (me.ok) {
    renderStudentInfo("officer-self-info", me.data.student, false);
    document.getElementById("officer-confirm-btn").disabled = me.data.student.confirmed;
    if (me.data.student.confirmed) {
      document.getElementById("officer-confirm-btn").textContent = "✓ 您已確認過";
      document.getElementById("officer-confirm-btn").style.opacity = 0.6;
    }
    document.getElementById("officer-confirm-btn").onclick = async () => {
      if (!confirm("確認後將鎖定，若需修改要聯繫註冊組。確定？")) return;
      const r = await api("/api/student/confirm", { method: "POST" });
      if (r.ok) await loadOfficerPage();
    };
  }
}

// ════════════════════ 註冊組長頁 ════════════════════
let registrarCache = [];

async function loadRegistrarPage() {
  showPage("page-registrar");
  const r = await api("/api/students/all");
  if (!r.ok) return alert("讀取失敗");
  registrarCache = r.data.students;

  // summary
  const total = registrarCache.length;
  const confirmed = registrarCache.filter(s => s.confirmed).length;
  document.getElementById("registrar-summary").innerHTML = `
    <div class="stat"><div class="num">${total}</div><div class="label">全班人數</div></div>
    <div class="stat success"><div class="num">${confirmed}</div><div class="label">已確認</div></div>
    <div class="stat warning"><div class="num">${total - confirmed}</div><div class="label">待確認</div></div>
  `;

  renderRegistrarTable(registrarCache);

  document.getElementById("search-input").oninput = filterAndRender;
  document.getElementById("filter-status").onchange = filterAndRender;
  document.getElementById("export-btn").onclick = exportJson;
}

function filterAndRender() {
  const q = document.getElementById("search-input").value.trim().toLowerCase();
  const f = document.getElementById("filter-status").value;
  let list = registrarCache;
  if (q) {
    list = list.filter(s =>
      s.name.toLowerCase().includes(q) ||
      String(s.seat).includes(q) ||
      (s.student_id || "").toLowerCase().includes(q)
    );
  }
  if (f === "confirmed") list = list.filter(s => s.confirmed);
  if (f === "pending")   list = list.filter(s => !s.confirmed);
  renderRegistrarTable(list);
}

function renderRegistrarTable(list) {
  const tbody = document.getElementById("registrar-tbody");
  tbody.innerHTML = list.map(s => `
    <tr>
      <td class="seat-cell">${s.seat}</td>
      <td>${escapeHtml(s.name)}</td>
      <td>${escapeHtml(s.gender)}</td>
      <td>${escapeHtml(s.student_id)}</td>
      <td>${escapeHtml(s.national_id)}</td>
      <td>${escapeHtml(s.dob)}</td>
      <td>${escapeHtml(s.phone)}</td>
      <td>${escapeHtml(s.address_mailing)}</td>
      <td>${escapeHtml(s.father_name)}</td>
      <td>${escapeHtml(s.father_phone)}</td>
      <td>${escapeHtml(s.mother_name)}</td>
      <td>${escapeHtml(s.mother_phone)}</td>
      <td>${s.confirmed
          ? '<span class="pill confirmed">已確認</span>'
          : '<span class="pill pending">待確認</span>'}</td>
      <td class="note-cell">${escapeHtml(s.note || "")}</td>
      <td><button class="btn-mini" onclick="openEditModal(${s.seat})">編輯</button></td>
    </tr>
  `).join("");
}

function exportJson() {
  const blob = new Blob([JSON.stringify(registrarCache, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `students_${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Edit modal (registrar) ──────────────────────────────
function openEditModal(seat) {
  const s = registrarCache.find(x => x.seat === seat);
  if (!s) return;
  document.getElementById("edit-seat").textContent = s.seat;
  document.getElementById("edit-name").textContent = "(" + s.name + ")";
  const form = document.getElementById("edit-form");
  form.innerHTML = "";
  for (const group of FIELD_GROUPS) {
    const h = document.createElement("div");
    h.className = "section-header";
    h.textContent = group.title;
    form.appendChild(h);
    for (const f of group.fields) {
      if (f === "seat" || f === "student_id") continue;  // 不可改
      const lab = document.createElement("label");
      lab.textContent = FIELD_LABEL[f] || f;
      const inp = document.createElement("input");
      inp.type = "text";
      inp.dataset.field = f;
      inp.value = s[f] || "";
      lab.appendChild(inp);
      form.appendChild(lab);
    }
  }
  document.getElementById("edit-msg").textContent = "";
  document.getElementById("edit-modal").classList.remove("hidden");

  document.getElementById("edit-save-btn").onclick = async () => {
    const inputs = form.querySelectorAll("input[data-field]");
    const patch = {};
    inputs.forEach(i => { patch[i.dataset.field] = i.value; });
    const r = await api("/api/registrar/edit", {
      method: "POST",
      body: JSON.stringify({ seat, patch })
    });
    if (r.ok) {
      document.getElementById("edit-msg").textContent = "✓ 已儲存";
      setTimeout(() => closeModal(), 800);
      await loadRegistrarPage();
    } else {
      document.getElementById("edit-msg").textContent = "✗ 儲存失敗";
    }
  };
  document.getElementById("edit-reset-confirm-btn").onclick = async () => {
    if (!confirm("確定要重置此學生的確認狀態？(會變回「待確認」讓他重新確認)")) return;
    const r = await api("/api/registrar/reset_confirm", {
      method: "POST",
      body: JSON.stringify({ seat })
    });
    if (r.ok) {
      document.getElementById("edit-msg").textContent = "✓ 已重置";
      setTimeout(() => { closeModal(); loadRegistrarPage(); }, 800);
    }
  };
}
function closeModal() {
  document.getElementById("edit-modal").classList.add("hidden");
}
document.getElementById("edit-close").onclick = closeModal;
document.getElementById("edit-modal").addEventListener("click", (e) => {
  if (e.target.id === "edit-modal") closeModal();
});

// ── Util ───────────────────────────────────────────────
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Boot ───────────────────────────────────────────────
checkSession();
