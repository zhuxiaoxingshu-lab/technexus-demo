const state = {
  submissionId: "",
  submission: {},
  results: [],
  selectedResult: null,
  matchMode: "ai",
  adminAuthenticated: false,
  adminUsername: "",
  adminStatuses: [],
  intentFilters: {
    status: "",
    keyword: "",
  },
};

const titleMap = {
  home: ["技术成果找需求", "提交技术成果，AI 匹配真实技术需求，合作意向由平台人工审核撮合。"],
  submit: ["成果提交", "字段都不是必填，写得越详细，匹配越精准。"],
  results: ["匹配结果", "展示匹配分数、理由和合作建议，不展示需求方联系方式。"],
  intent: ["合作意向", "确认中介服务协议后，线索进入后台审核。"],
  admin: ["后台管理", "管理需求库、匹配记录、合作意向和协议确认。"],
};

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 2600);
}

function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function showView(id) {
  $all(".view").forEach((view) => view.classList.toggle("active", view.id === id));
  $all(".nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === id));
  if (titleMap[id]) {
    $("#page-title").textContent = titleMap[id][0];
    $("#page-subtitle").textContent = titleMap[id][1];
  }
  if (id === "admin") {
    if (!state.adminAuthenticated) {
      setAdminView(false, "");
    }
    loadAdmin();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.message || "请求失败");
    error.status = response.status;
    throw error;
  }
  return data;
}

function formDataToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function fillSubmissionForm(payload) {
  const form = $("#submission-form");
  Object.entries(payload).forEach(([key, value]) => {
    const field = form.elements[key];
    if (field) field.value = value || "";
  });
}

function homePayload() {
  return {
    title: $("#home-title").value.trim(),
    tech_field: $("#home-field").value.trim(),
    summary: $("#home-summary").value.trim(),
    application_scene: $("#home-summary").value.trim(),
  };
}

function setButtonLoading(button, loading, text) {
  if (!button) return;
  if (loading) {
    button.dataset.oldHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<i data-lucide="loader-2"></i>${text || "处理中"}`;
  } else {
    button.disabled = false;
    if (button.dataset.oldHtml) {
      button.innerHTML = button.dataset.oldHtml;
      delete button.dataset.oldHtml;
    }
  }
  refreshIcons();
}

function currentMatchModeLabel() {
  return state.matchMode === "quick" ? "快速匹配" : "AI智能匹配";
}

function setMatchMode(mode) {
  state.matchMode = mode === "quick" ? "quick" : "ai";
  $all("[data-match-mode]").forEach((button) => {
    const active = button.dataset.matchMode === state.matchMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  const hint = $("#match-mode-hint");
  if (hint) {
    hint.textContent =
      state.matchMode === "quick"
        ? "快速匹配不会调用 DeepSeek API，适合先看大致方向。"
        : "AI智能匹配会调用 DeepSeek API，对候选需求做精排并生成更细的理由。";
  }
  const submitButton = $("#submit-match");
  if (submitButton) {
    submitButton.innerHTML =
      state.matchMode === "quick"
        ? '<i data-lucide="scan-search"></i>开始快速匹配'
        : '<i data-lucide="sparkles"></i>开始AI智能匹配';
    refreshIcons();
  }
}

async function runMatch(payload, button) {
  const data = payload || formDataToObject($("#submission-form"));
  data.match_mode = state.matchMode;
  state.submission = data;
  setButtonLoading(button, true, state.matchMode === "quick" ? "快速匹配中" : "AI匹配中");
  $("#result-status").textContent =
    state.matchMode === "quick" ? "正在进行快速匹配，不调用 DeepSeek API..." : "正在调用 DeepSeek API 进行智能匹配...";
  $("#result-status").style.display = "block";
  $("#result-list").innerHTML = "";
  try {
    const response = await api("/api/match", {
      method: "POST",
      body: JSON.stringify(data),
    });
    state.submissionId = response.submission_id;
    state.results = response.results || [];
    if (response.ai_meta?.message) {
      $("#result-status").textContent = response.ai_meta.message;
      $("#result-status").style.display = "block";
    }
    renderResults(state.results);
    updateStats(response);
    showView("results");
    toast(`${response.ai_meta?.used_ai ? "DeepSeek AI 已精排" : currentMatchModeLabel() + "已完成"}，生成 ${state.results.length} 条结果`);
  } catch (error) {
    $("#result-status").textContent = error.message;
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

function updateStats(stats) {
  const demandCount = stats.demand_count ?? "-";
  $("#home-demand-count").textContent = Number(demandCount).toLocaleString("zh-CN");
  $("#admin-demand-count").textContent = Number(demandCount).toLocaleString("zh-CN");
  $("#admin-match-count").textContent = Number(stats.match_count ?? 0).toLocaleString("zh-CN");
  $("#admin-intent-count").textContent = Number(stats.intent_count ?? 0).toLocaleString("zh-CN");
  $("#home-ai-mode").textContent = stats.ai_mode || "-";
  $("#admin-ai-mode").textContent = stats.ai_mode || "-";
}

function tag(text) {
  return text ? `<span class="tag">${escapeHtml(text)}</span>` : "";
}

function renderResults(results) {
  const status = $("#result-status");
  const list = $("#result-list");
  if (!results.length) {
    status.textContent = "暂未找到匹配需求，可以补充技术领域、应用场景或技术摘要后重试。";
    status.style.display = "block";
    list.innerHTML = "";
    return;
  }
  status.style.display = "none";
  list.innerHTML = results
    .map((item, index) => {
      const dims = item.dimensions || {};
      return `
        <article class="result-item">
          <div class="result-top">
            <div>
              <h2 class="result-title">${escapeHtml(item.name)}</h2>
              <div class="tags">
                ${tag(item.tech_field)}
                ${tag(item.demand_type)}
                ${tag(item.intended_price ? `意向投入 ${item.intended_price}` : "")}
                ${tag(item.region)}
                ${tag(item.cooperation_mode)}
                ${tag(item.scoring_source || "本地规则")}
              </div>
            </div>
            <div class="score">${escapeHtml(item.score)}<small>匹配分</small></div>
          </div>
          <div class="score-stack">
            ${scoreBar("技术领域", dims["技术领域"])}
            ${scoreBar("应用场景", dims["应用场景"])}
            ${scoreBar("产业方向", dims["产业方向"])}
            ${scoreBar("成熟度", dims["成熟度"])}
          </div>
          <div class="reason">${escapeHtml(item.reason)}</div>
          <div class="suggestion">${escapeHtml(item.suggestion)}</div>
          <div class="top-actions left">
            <button class="btn primary" data-intent-index="${index}"><i data-lucide="handshake"></i>我想合作</button>
          </div>
        </article>
      `;
    })
    .join("");
  $all("[data-intent-index]").forEach((button) => {
    button.addEventListener("click", () => selectResult(Number(button.dataset.intentIndex)));
  });
  refreshIcons();
}

function scoreBar(name, value = 0) {
  const safe = Math.max(0, Math.min(100, Number(value || 0)));
  return `
    <div class="score-bar">
      ${escapeHtml(name)} ${safe}
      <div class="bar"><span style="width:${safe}%"></span></div>
    </div>
  `;
}

function selectResult(index) {
  state.selectedResult = state.results[index];
  renderSelectedDemand();
  showView("intent");
}

function renderSelectedDemand() {
  const box = $("#selected-demand");
  const item = state.selectedResult;
  if (!item) {
    box.textContent = "请先在匹配结果中选择“我想合作”的需求。";
    return;
  }
  box.innerHTML = `
    <strong>${escapeHtml(item.name)}</strong>
    <div class="tags">
      ${tag(`匹配分 ${item.score}`)}
      ${tag(item.tech_field)}
      ${tag(item.demand_type)}
      ${tag(item.region)}
      ${tag(item.intended_price ? `意向投入 ${item.intended_price}` : "")}
    </div>
    <p>${escapeHtml(item.reason)}</p>
  `;
}

async function submitIntent(button) {
  if (!state.selectedResult) {
    toast("请先在匹配结果中选择一个需求");
    showView("results");
    return;
  }
  const agreement = $("#agreement-check").checked;
  if (!agreement) {
    toast("请先勾选并确认中介服务协议");
    return;
  }
  const form = formDataToObject($("#intent-form"));
  const payload = {
    submission_id: state.submissionId,
    agreement,
    contact: {
      name: form.name || "",
      phone: form.phone || "",
      company: form.company || "",
      technology_summary: state.submission.summary || state.submission.title || "",
    },
    message: form.message || "",
    extra_note: form.extra_note || state.submission.extra_note || "",
    selected_result: state.selectedResult,
  };
  setButtonLoading(button, true, "正在提交");
  try {
    await api("/api/intents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast("已收到合作意向，后台可查看");
    $("#intent-form").reset();
    $("#agreement-check").checked = false;
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadStats() {
  try {
    const stats = await api("/api/stats");
    updateStats(stats);
  } catch (error) {
    toast(error.message);
  }
}

async function loadAdmin() {
  try {
    const session = await api("/api/admin/session");
    setAdminView(session.authenticated, session.username || "");
    if (!session.authenticated) {
      resetAdminData();
      return;
    }
    const query = intentFilterQuery();
    const [stats, intents] = await Promise.all([api("/api/stats"), api(`/api/intents${query}`)]);
    updateStats(stats);
    state.adminStatuses = intents.statuses || [];
    renderIntentFilterOptions();
    renderIntentTable(intents.items || []);
    if (!$("#demand-preview").dataset.loaded) {
      await loadDemandPreview();
    }
  } catch (error) {
    if (error.status === 401) {
      setAdminView(false, "");
      resetAdminData();
      return;
    }
    toast(error.message);
  }
}

function intentFilterQuery() {
  const params = new URLSearchParams();
  if (state.intentFilters.status) params.set("status", state.intentFilters.status);
  if (state.intentFilters.keyword) params.set("keyword", state.intentFilters.keyword);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function renderIntentFilterOptions() {
  const select = $("#intent-status-filter");
  const current = state.intentFilters.status;
  const options = [`<option value="">全部状态</option>`].concat(
    state.adminStatuses.map(
      (status) => `<option value="${escapeHtml(status)}" ${status === current ? "selected" : ""}>${escapeHtml(status)}</option>`,
    ),
  );
  select.innerHTML = options.join("");
  select.value = current;
  $("#intent-keyword").value = state.intentFilters.keyword || "";
}

function applyIntentFilters() {
  state.intentFilters.status = $("#intent-status-filter").value.trim();
  state.intentFilters.keyword = $("#intent-keyword").value.trim();
  loadAdmin();
}

function clearIntentFilters() {
  state.intentFilters.status = "";
  state.intentFilters.keyword = "";
  $("#intent-status-filter").value = "";
  $("#intent-keyword").value = "";
  loadAdmin();
}

function exportIntents() {
  if (!state.adminAuthenticated) {
    toast("请先登录后台");
    return;
  }
  window.location.href = `/api/intents/export${intentFilterQuery()}`;
}

function resetAdminData() {
  $("#admin-demand-count").textContent = "-";
  $("#admin-match-count").textContent = "-";
  $("#admin-intent-count").textContent = "-";
  $("#admin-ai-mode").textContent = "-";
  $("#intent-table").innerHTML = `<tr><td colspan="8">登录后显示合作意向</td></tr>`;
  $("#intent-detail").className = "intent-detail empty-state";
  $("#intent-detail").textContent = "登录后查看线索详情。";
  $("#demand-preview").dataset.loaded = "";
  $("#demand-preview").innerHTML = "";
}

function setAdminView(authenticated, username = "") {
  state.adminAuthenticated = authenticated;
  state.adminUsername = username;
  $("#admin-login-panel").hidden = authenticated;
  $("#admin-content").hidden = !authenticated;
  $("#admin-username").textContent = username || "-";
}

async function loginAdmin(button) {
  const payload = formDataToObject($("#admin-login-form"));
  setButtonLoading(button, true, "正在登录");
  try {
    const response = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAdminView(true, response.username || payload.username || "admin");
    $("#admin-login-form").reset();
    toast("后台登录成功");
    await loadAdmin();
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function logoutAdmin() {
  try {
    await api("/api/admin/logout", { method: "POST", body: JSON.stringify({}) });
  } catch {
    // Even if the server session expired, the UI should return to the login state.
  }
  setAdminView(false, "");
  $("#demand-preview").dataset.loaded = "";
  $("#intent-table").innerHTML = `<tr><td colspan="8">请先登录后台</td></tr>`;
  $("#intent-detail").className = "intent-detail empty-state";
  $("#intent-detail").textContent = "请选择左侧线索查看详情。";
  toast("已退出后台");
}

function renderIntentTable(items) {
  const table = $("#intent-table");
  if (!items.length) {
    table.innerHTML = `<tr><td colspan="8">暂无合作意向</td></tr>`;
    return;
  }
  table.innerHTML = items
    .map((item) => {
      const contact = item.contact || {};
      const selected = item.selected_result || {};
      const status = item.status || "待审核";
      return `
        <tr>
          <td>${escapeHtml(item.created_at)}</td>
          <td>${escapeHtml(contact.name || "-")}<br>${escapeHtml(contact.phone || "-")}</td>
          <td>${escapeHtml(contact.company || "-")}</td>
          <td>${escapeHtml(selected.name || "-")}</td>
          <td>${escapeHtml(selected.score || "-")}</td>
          <td>
            <select class="status-select" data-status-select="${escapeHtml(item.intent_id)}">
              ${statusOptions(status)}
            </select>
          </td>
          <td><input class="note-input" data-note-input="${escapeHtml(item.intent_id)}" value="${escapeHtml(item.followup_note || "")}" placeholder="跟进备注" /></td>
          <td>
            <div class="top-actions left">
              <button class="btn" data-view-intent="${escapeHtml(item.intent_id)}"><i data-lucide="eye"></i>查看</button>
              <button class="btn" data-save-status="${escapeHtml(item.intent_id)}"><i data-lucide="save"></i>保存</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
  $all("[data-view-intent]").forEach((button) => {
    button.addEventListener("click", () => loadIntentDetail(button.dataset.viewIntent));
  });
  $all("[data-save-status]").forEach((button) => {
    button.addEventListener("click", () => updateIntentStatus(button));
  });
  refreshIcons();
}

async function loadIntentDetail(intentId) {
  const box = $("#intent-detail");
  box.className = "intent-detail empty-state";
  box.textContent = "正在加载线索详情...";
  try {
    const response = await api(`/api/intents/detail?intent_id=${encodeURIComponent(intentId)}`);
    renderIntentDetail(response.intent);
  } catch (error) {
    box.textContent = error.message;
    toast(error.message);
  }
}

function renderIntentDetail(item) {
  const contact = item.contact || {};
  const selected = item.selected_result || {};
  const logs = item.status_logs || [];
  const box = $("#intent-detail");
  box.className = "intent-detail";
  box.innerHTML = `
    <div class="detail-section">
      <h3>来访者</h3>
      ${detailRow("姓名", contact.name || "-")}
      ${detailRow("手机号", contact.phone || "-")}
      ${detailRow("单位", contact.company || "-")}
      ${detailRow("状态", item.status || "-")}
      ${detailRow("提交时间", item.created_at || "-")}
    </div>
    <div class="detail-section">
      <h3>成果和留言</h3>
      ${detailRow("成果摘要", contact.technology_summary || "-")}
      ${detailRow("留言", item.message || "-")}
      ${detailRow("补充说明", item.attachment_note || "-")}
    </div>
    <div class="detail-section">
      <h3>匹配需求</h3>
      ${detailRow("需求名称", selected.name || "-")}
      ${detailRow("匹配分", selected.score || "-")}
      ${detailRow("技术领域", selected.tech_field || "-")}
      ${detailRow("需求类型", selected.demand_type || "-")}
      ${detailRow("所在地区", selected.region || "-")}
      ${detailRow("意向投入", selected.intended_price || "-")}
      ${detailRow("需求ID", selected.demand_id || "-")}
    </div>
    <div class="detail-section">
      <h3>AI 判断</h3>
      ${detailRow("匹配理由", selected.reason || "-")}
      ${detailRow("合作建议", selected.suggestion || "-")}
      ${detailRow("评分来源", selected.scoring_source || "-")}
    </div>
    <div class="detail-section">
      <h3>协议和跟进</h3>
      ${detailRow("协议版本", item.agreement_version || "-")}
      ${detailRow("跟进备注", item.followup_note || "-")}
      <div class="log-list">
        ${logs.length ? logs.map(renderStatusLog).join("") : '<div class="log-item">暂无状态变更记录</div>'}
      </div>
    </div>
  `;
}

function detailRow(label, value) {
  return `
    <div class="detail-row">
      <span>${escapeHtml(label)}</span>
      <strong class="detail-text">${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function renderStatusLog(log) {
  const from = log.old_status ? `${log.old_status} → ` : "";
  const note = log.note ? `；${log.note}` : "";
  return `<div class="log-item">${escapeHtml(log.created_at || "")}：${escapeHtml(from + (log.new_status || ""))}${escapeHtml(note)}</div>`;
}

function statusOptions(current) {
  const statuses = state.adminStatuses.length
    ? state.adminStatuses
    : ["待审核", "已联系成果方", "已联系需求方", "撮合中", "已签中介协议", "合作成功", "合作失败"];
  return statuses
    .map((status) => `<option value="${escapeHtml(status)}" ${status === current ? "selected" : ""}>${escapeHtml(status)}</option>`)
    .join("");
}

async function updateIntentStatus(button) {
  const intentId = button.dataset.saveStatus;
  const status = $(`[data-status-select="${CSS.escape(intentId)}"]`).value;
  const note = $(`[data-note-input="${CSS.escape(intentId)}"]`).value;
  setButtonLoading(button, true, "保存中");
  try {
    const response = await api("/api/intents/status", {
      method: "POST",
      body: JSON.stringify({ intent_id: intentId, status, note }),
    });
    renderIntentTable(response.items || []);
    renderIntentDetail(response.intent);
    toast("线索状态已更新");
  } catch (error) {
    if (error.status === 401) {
      setAdminView(false, "");
    }
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadDemandPreview(keyword = "") {
  const params = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  const data = await api(`/api/demands${params}`);
  const box = $("#demand-preview");
  const items = data.items || [];
  box.dataset.loaded = "1";
  if (!items.length) {
    box.innerHTML = `<div class="empty-state">未找到需求</div>`;
    return;
  }
  box.innerHTML = items
    .slice(0, 20)
    .map(
      (item) => `
        <div class="demand-mini">
          <strong>${escapeHtml(item.name)}</strong>
          <div class="tags">
            ${tag(item.tech_field)}
            ${tag(item.demand_type)}
            ${tag(item.region)}
            ${tag(item.intended_price ? `意向投入 ${item.intended_price}` : "")}
          </div>
          <p>${escapeHtml(item.detail_summary || "")}</p>
        </div>
      `,
    )
    .join("");
}

function bindEvents() {
  $all("[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  $("#home-match").addEventListener("click", () => {
    const payload = homePayload();
    fillSubmissionForm(payload);
    runMatch(payload, $("#home-match"));
  });
  $("#submit-match").addEventListener("click", () => runMatch(null, $("#submit-match")));
  $("#intent-submit").addEventListener("click", () => submitIntent($("#intent-submit")));
  $("#admin-refresh").addEventListener("click", loadAdmin);
  $("#admin-logout").addEventListener("click", logoutAdmin);
  $("#admin-login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loginAdmin($("#admin-login-submit"));
  });
  $all("[data-match-mode]").forEach((button) => {
    button.addEventListener("click", () => setMatchMode(button.dataset.matchMode));
  });
  $("#intent-filter").addEventListener("click", applyIntentFilters);
  $("#intent-clear-filter").addEventListener("click", clearIntentFilters);
  $("#intent-export").addEventListener("click", exportIntents);
  $("#intent-keyword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyIntentFilters();
    }
  });
  $("#demand-search").addEventListener("click", () => loadDemandPreview($("#demand-keyword").value.trim()));
  $("#demand-keyword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadDemandPreview($("#demand-keyword").value.trim());
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  setMatchMode("ai");
  loadStats();
  refreshIcons();
});
