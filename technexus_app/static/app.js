const state = {
  submissionId: "",
  submission: {},
  results: [],
  matchMeta: {},
  selectedResult: null,
  matchMode: "ai",
  currentIntent: null,
  currentMatch: null,
  matchFollowupStatuses: [],
  publicDemandOffset: 0,
  publicDemandTotal: 0,
  adminAuthenticated: false,
  adminUsername: "",
  adminCsrfToken: "",
  adminStatuses: [],
  intentFilters: {
    status: "",
    keyword: "",
  },
  matchFilters: {
    keyword: "",
  },
};

const titleMap = {
  home: ["技术成果找需求", "提交技术成果，AI 匹配真实技术需求，合作意向由平台人工审核撮合。"],
  demands: ["技术需求大厅", "浏览真实需求样本，提交成果后由 AI 从完整需求库精准匹配。"],
  submit: ["成果提交", "粘贴一段完整技术内容，系统自动分析并匹配。"],
  results: ["匹配结果", "展示匹配分数、具体技术需求和合作建议，不展示需求方身份及联系方式。"],
  intent: ["申请对接", "选中需求后填写联系方式并确认协议，进入平台人工审核。"],
  progress: ["进度查询", "输入查询码，查看技术撮合对接进度。"],
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

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
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
  if (id === "demands" && !$("#public-demand-list").dataset.loaded) {
    loadPublicDemands(true);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function api(path, options = {}) {
  let response;
  try {
    const method = String(options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const csrfProtectedPaths = new Set(["/api/admin/logout", "/api/intents/status", "/api/matches/followup"]);
    if (method !== "GET" && state.adminCsrfToken && csrfProtectedPaths.has(path)) {
      headers["X-CSRF-Token"] = state.adminCsrfToken;
    }
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new Error("暂时无法连接线上服务，请检查网络后重试。");
  }

  const responseText = await response.text();
  let data = {};
  if (responseText.trim()) {
    try {
      data = JSON.parse(responseText);
    } catch (error) {
      throw new Error("服务器返回内容不完整，请稍后重新匹配。");
    }
  }
  if (!response.ok) {
    let message = data.message || "请求失败，请稍后重试。";
    if (response.status === 503) {
      message = "线上服务正在唤醒或重新部署，请等待约 30 秒后重新匹配。";
    } else if (response.status === 502 || response.status === 504) {
      message = "AI 匹配服务暂时超时，请稍后重试，也可以先选择“快速匹配”。";
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  if (!responseText.trim()) {
    throw new Error("服务器未返回匹配结果，请稍后重新匹配。");
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
    achievement_text: $("#home-achievement-text").value.trim(),
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
        ? "快速匹配不会调用 DeepSeek API，会按技术标的、核心问题、所需功能、技术路线和指标完成初筛。"
        : "AI 智能匹配会读取预拆解的需求画像，再由 DeepSeek 完成前 6 条候选需求复核。";
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
  const achievementText = String(data.achievement_text || "").trim();
  if (achievementText.length < 20) {
    toast("请至少填写 20 个字的技术内容");
    return;
  }
  data.match_mode = state.matchMode;
  data.client_source = data.client_source || "网页端";
  state.submission = data;
  state.matchMeta = {};
  setButtonLoading(button, true, state.matchMode === "quick" ? "快速匹配中" : "AI匹配中");
  $("#result-status").textContent =
    state.matchMode === "quick"
      ? "正在进行快速匹配：比较技术标的、核心问题、所需功能、技术路线和指标..."
      : "第 1 步：正在解析成果并生成初步能力画像...";
  $("#result-status").style.display = "block";
  renderResultMeta({});
  $("#result-list").innerHTML = "";
  let progressTimer = null;
  if (state.matchMode === "ai") {
    const progressMessages = [
      "第 2 步：正在从需求库召回并筛选前 20 条候选...",
      "第 3 步：正在由 DeepSeek 复核前 6 条候选需求...",
    ];
    let progressIndex = 0;
    progressTimer = window.setInterval(() => {
      if (progressIndex < progressMessages.length) {
        $("#result-status").textContent = progressMessages[progressIndex];
        progressIndex += 1;
      }
    }, 6000);
  }
  try {
    const response = await api("/api/match", {
      method: "POST",
      body: JSON.stringify(data),
    });
    state.submissionId = response.submission_id;
    state.results = response.results || [];
    state.matchMeta = response.ai_meta || {};
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
    if (progressTimer) window.clearInterval(progressTimer);
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

function tag(text, extraClass = "") {
  return text ? `<span class="tag${extraClass ? ` ${extraClass}` : ""}">${escapeHtml(text)}</span>` : "";
}

const TAG_GROUP_ORDER = [
  "技术标签",
  "应用标签",
  "产业标签",
  "合作标签",
  "地区标签",
  "成熟度标签",
  "关键词",
];

function normalizeTagValues(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "").trim()).filter(Boolean);
  }
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function collectTagGroups(payload) {
  return TAG_GROUP_ORDER.map((label) => ({
    label,
    values: normalizeTagValues(payload?.[label]),
  })).filter((group) => group.values.length);
}

function flattenTagValues(payload, limit = 0) {
  const seen = new Set();
  const flat = [];
  collectTagGroups(payload).forEach((group) => {
    group.values.forEach((value) => {
      if (!seen.has(value)) {
        seen.add(value);
        flat.push(value);
      }
    });
  });
  return limit > 0 ? flat.slice(0, limit) : flat;
}

function renderResultMeta(meta = state.matchMeta) {
  const box = $("#result-meta");
  if (!box) return;
  const tags = meta?.structured_tags || meta?.tag_extraction?.merged_tags || {};
  const groups = collectTagGroups(tags);
  const profile = meta?.capability_profile || meta?.tag_extraction?.capability_profile || {};
  const sourceTags = meta?.used_ai
    ? ["成果能力画像", "技术任务召回", "AI技术精排"]
    : meta?.tag_extraction?.used_ai
      ? ["成果能力画像", "技术任务召回", "规则评分"]
      : ["本地能力画像", "技术任务召回", "规则评分"];
  const message =
    meta?.message ||
    (meta?.used_ai
      ? "系统会先抽取标准标签，再扩大候选需求范围，最后结合 DeepSeek 做解释型精排。"
      : "系统已用本地规则抽取标签，并基于扩大召回结果完成快速排序。");
  if (!groups.length && !message) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = `
    <div class="result-meta-card">
      <div class="result-meta-head">
        <div>
          <h3>本次成果能力画像</h3>
          <p>${escapeHtml(message)}</p>
        </div>
        <div class="tags meta-source-tags">
          ${sourceTags.map((item) => tag(item, "meta-tag")).join("")}
        </div>
      </div>
      ${
        profile.target || profile.core_problem || profile.technical_route
          ? `<div class="capability-profile-grid">
              ${profile.target ? `<div><span>技术标的</span><strong>${escapeHtml(profile.target)}</strong></div>` : ""}
              ${profile.core_problem ? `<div><span>能够解决的问题</span><strong>${escapeHtml(profile.core_problem)}</strong></div>` : ""}
              ${profile.technical_route ? `<div><span>技术路线</span><strong>${escapeHtml(profile.technical_route)}</strong></div>` : ""}
              ${
                normalizeTagValues(profile.indicators).length
                  ? `<div><span>已提供指标</span><strong>${escapeHtml(normalizeTagValues(profile.indicators).join("；"))}</strong></div>`
                  : ""
              }
            </div>`
          : ""
      }
      ${
        groups.length
          ? `
            <div class="tag-group-grid">
              ${groups
                .map(
                  (group) => `
                    <div class="tag-group">
                      <div class="tag-group-label">${escapeHtml(group.label)}</div>
                      <div class="tags compact-tags">
                        ${group.values.map((value) => tag(value, "soft-tag")).join("")}
                      </div>
                    </div>
                  `,
                )
                .join("")}
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderMatchedTagSummary(item) {
  const matched = flattenTagValues(item?.matched_tags, 8);
  if (!matched.length) return "";
  return `
    <div class="match-tag-row">
      <span class="match-tag-label">命中标签</span>
      <div class="tags compact-tags">
        ${matched.map((value) => tag(value, "match-tag")).join("")}
      </div>
    </div>
  `;
}

function renderDemandDetail(item, index) {
  const detail = String(item?.demand_detail || item?.detail_summary || "").trim();
  if (!detail) return "";
  const expandable = detail.length > 360;
  return `
    <section class="demand-detail-card${expandable ? " is-collapsed" : ""}" data-demand-detail-card="${index}">
      <div class="demand-detail-head">
        <div>
          <span class="demand-detail-eyebrow">匹配项目需求正文</span>
          <h3>具体技术需求</h3>
        </div>
        <span class="privacy-note"><i data-lucide="shield-check"></i>需求方身份与联系方式已隐藏</span>
      </div>
      <div class="demand-detail-text">${escapeHtml(detail)}</div>
      ${
        expandable
          ? `<button class="demand-detail-toggle" type="button" data-demand-toggle="${index}" aria-expanded="false">
              展开全部 <i data-lucide="chevron-down"></i>
            </button>`
          : ""
      }
    </section>
  `;
}

function renderAssessmentList(label, values, className = "") {
  const items = normalizeTagValues(values);
  if (!items.length) return "";
  return `
    <div class="assessment-list ${className}">
      <span>${escapeHtml(label)}</span>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderTechnicalAssessment(item) {
  return `
    <section class="technical-assessment">
      <div class="assessment-head">
        <div>
          <span class="demand-detail-eyebrow">技术可行性判断</span>
          <h3>${escapeHtml(item.match_type || "需验证")}</h3>
        </div>
        <div class="confidence-badge">
          <strong>${escapeHtml(item.confidence ?? "-")}</strong>
          <span>判断可信度</span>
        </div>
      </div>
      <div class="assessment-grid">
        <div><span>需求技术标的</span><strong>${escapeHtml(item.technical_target || "-")}</strong></div>
        <div><span>需求核心问题</span><strong>${escapeHtml(item.core_problem || "-")}</strong></div>
        <div><span>成果对应能力</span><strong>${escapeHtml(item.matched_capability || "-")}</strong></div>
        ${
          item.transfer_path
            ? `<div><span>技术迁移路径</span><strong>${escapeHtml(item.transfer_path)}</strong></div>`
            : ""
        }
      </div>
      <div class="assessment-lists">
        ${renderAssessmentList("已识别对应点", item.verified_items, "verified")}
        ${renderAssessmentList("尚待验证", item.unverified_items, "unverified")}
        ${renderAssessmentList("硬性冲突", item.hard_conflicts, "conflict")}
      </div>
      ${item.hard_gate ? `<div class="hard-gate-note">评分限制：${escapeHtml(item.hard_gate)}</div>` : ""}
    </section>
  `;
}

function scoreLevel(score) {

  const value = Number(score || 0);
  if (value >= 80) return "excellent";
  if (value >= 65) return "high";
  if (value >= 45) return "medium";
  if (value >= 35) return "low";
  return "weak";
}

function scoreLabel(score) {
  const value = Number(score || 0);
  if (value >= 80) return "建议优先对接";
  if (value >= 65) return "建议补充材料";
  if (value >= 45) return "建议进一步核验";
  return "暂不推荐";
}

function renderResults(results) {
  const status = $("#result-status");
  const list = $("#result-list");
  if (!results.length) {
    renderResultMeta();
    status.textContent = "暂未找到技术匹配度达到45分的需求。建议补充技术原理、可解决的问题、量化指标、样品或案例后重试。";
    status.style.display = "block";
    list.innerHTML = "";
    return;
  }
  status.style.display = "none";
  renderResultMeta();
  list.innerHTML = results
    .map((item, index) => {
      const dims = item.dimensions || {};
      const level = scoreLevel(item.score);
      return `
        <article class="result-item score-${level}">
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
                ${tag(scoreLabel(item.score))}
              </div>
            </div>
            <div class="score score-${level}">${escapeHtml(item.score)}%<small>${scoreLabel(item.score)}</small></div>
          </div>
          <div class="score-stack">
            ${scoreBar("核心问题", dims["核心问题"])}
            ${scoreBar("技术标的", dims["技术标的"])}
            ${scoreBar("所需功能", dims["所需功能"])}
            ${scoreBar("技术路线", dims["技术路线"])}
            ${scoreBar("指标约束", dims["指标约束"])}
            ${scoreBar("交付成熟度", dims["交付成熟度"])}
          </div>
          ${renderMatchedTagSummary(item)}
          ${renderDemandDetail(item, index)}
          ${renderTechnicalAssessment(item)}
          <div class="reason">${escapeHtml(item.reason)}</div>
          <div class="suggestion">${escapeHtml(item.suggestion)}</div>
          <div class="top-actions left">
            <button class="btn primary" data-intent-index="${index}"><i data-lucide="handshake"></i>申请对接</button>
          </div>
        </article>
      `;
    })
    .join("");
  $all("[data-intent-index]").forEach((button) => {
    button.addEventListener("click", () => selectResult(Number(button.dataset.intentIndex)));
  });
  $all("[data-demand-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = $(`[data-demand-detail-card="${button.dataset.demandToggle}"]`);
      if (!card) return;
      const expanded = card.classList.toggle("is-expanded");
      card.classList.toggle("is-collapsed", !expanded);
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      button.innerHTML = expanded
        ? '收起 <i data-lucide="chevron-up"></i>'
        : '展开全部 <i data-lucide="chevron-down"></i>';
      refreshIcons();
    });
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
  prefillIntentContact();
  renderSelectedDemand();
  showView("intent");
}

function prefillIntentContact() {
  const form = $("#intent-form");
  if (!form) return;
  ["name", "phone", "company"].forEach((fieldName) => {
    const field = form.elements[fieldName];
    const value = String(state.submission[fieldName] || "").trim();
    if (field && value && !field.value.trim()) field.value = value;
  });
}

function renderSelectedDemand() {
  const box = $("#selected-demand");
  const item = state.selectedResult;
  if (!item) {
    box.textContent = "请先在匹配结果中选择“申请对接”的需求。";
    return;
  }
  box.innerHTML = `
    <strong>${escapeHtml(item.name)}</strong>
    <div class="tags">
      ${tag(`匹配分 ${item.score}%`)}
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
  const contact = {
    name: form.name || state.submission.name || "",
    phone: form.phone || state.submission.phone || "",
    company: form.company || state.submission.company || "",
  };
  if (!contact.name || !contact.phone || !contact.company) {
    toast("请填写姓名、手机号和单位");
    return;
  }
  const payload = {
    submission_id: state.submissionId,
    agreement,
    contact: {
      ...contact,
      technology_summary: state.submission.achievement_text || state.submission.summary || state.submission.title || "",
    },
    message: form.message || "",
    extra_note: form.extra_note || state.submission.extra_note || "",
    selected_result: state.selectedResult,
  };
  setButtonLoading(button, true, "正在提交");
  try {
    const response = await api("/api/intents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderIntentSuccess(response.intent || {});
    toast("已收到合作意向，请保存查询码");
    $("#intent-form").reset();
    $("#agreement-check").checked = false;
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

function renderIntentSuccess(intent) {
  const box = $("#intent-success");
  const code = intent.query_code || "-";
  $("#success-query-code").textContent = code;
  $("#progress-query-code").value = code === "-" ? "" : code;
  $("#success-promise").textContent = intent.promise || "平台将在 3 个工作日内完成初步审核或联系。";
  box.hidden = false;
  box.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function queryProgress(button) {
  const queryCode = $("#progress-query-code").value.trim();
  if (!queryCode) {
    toast("请输入查询码");
    return;
  }
  setButtonLoading(button, true, "查询中");
  try {
    const response = await api("/api/progress/query", {
      method: "POST",
      body: JSON.stringify({ query_code: queryCode }),
    });
    renderProgressResult(response.progress);
  } catch (error) {
    $("#progress-result").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

function renderProgressResult(progress) {
  const demand = progress.demand || {};
  const list = progress.progress || [];
  $("#progress-result").innerHTML = `
    <div class="progress-card">
      <div class="progress-card-head">
        <div>
          <span class="muted-label">查询码</span>
          <strong>${escapeHtml(progress.query_code || "-")}</strong>
        </div>
        <span class="status-pill">${escapeHtml(progress.status || "-")}</span>
      </div>
      <div class="progress-summary">
        ${detailRow("提交时间", progress.created_at || "-")}
        ${detailRow("最近更新", progress.updated_at || "-")}
        ${detailRow("匹配需求", demand.name || "-")}
        ${detailRow("匹配分", demand.score ? `${demand.score}%` : "-")}
        ${detailRow("平台说明", progress.public_note || progress.promise || "-")}
      </div>
      <div class="public-progress">
        ${list.map(renderPublicProgressStep).join("")}
      </div>
    </div>
  `;
  refreshIcons();
}

function renderPublicProgressStep(step) {
  return `
    <div class="progress-step ${step.done ? "done" : ""}">
      <span class="progress-dot">${step.done ? "✓" : ""}</span>
      <div>
        <strong>${escapeHtml(step.label || "-")}</strong>
        <p>${escapeHtml(step.updated_at || (step.done ? "" : "待推进"))}</p>
        ${step.public_note ? `<p>${escapeHtml(step.public_note)}</p>` : ""}
      </div>
    </div>
  `;
}

async function loadStats() {
  try {
    const stats = await api("/api/stats");
    updateStats(stats);
  } catch (error) {
    toast(error.message);
  }
}

function renderPublicDemandCard(item) {
  return `
    <article class="public-demand-card">
      <div class="public-demand-head">
        <div>
          <span class="demand-number">${escapeHtml(item.demand_no || item.demand_id || "技术需求")}</span>
          <h2>${escapeHtml(item.name || "未命名技术需求")}</h2>
        </div>
        ${item.intended_price ? `<span class="price-chip">意向投入 ${escapeHtml(item.intended_price)}</span>` : ""}
      </div>
      <div class="tags">
        ${tag(item.tech_field)}
        ${tag(item.demand_type)}
        ${tag(item.region)}
        ${tag(item.cooperation_mode)}
      </div>
      <p>${escapeHtml(item.detail_summary || "暂无需求详情")}</p>
      <div class="public-demand-foot">
        <span><i data-lucide="shield-check"></i>需求方身份及联系方式由平台后台管理</span>
        <button class="btn small" data-view="submit"><i data-lucide="sparkles"></i>提交成果匹配</button>
      </div>
    </article>
  `;
}

async function loadPublicDemands(reset = false) {
  const list = $("#public-demand-list");
  const moreButton = $("#public-demand-more");
  if (reset) {
    state.publicDemandOffset = 0;
    list.innerHTML = `<div class="empty-state">正在读取技术需求...</div>`;
  }
  setButtonLoading(moreButton, true, reset ? "读取中" : "加载中");
  const params = new URLSearchParams({
    offset: String(state.publicDemandOffset),
    limit: "18",
  });
  try {
    const response = await api(`/api/public/demands?${params.toString()}`);
    const items = response.items || [];
    state.publicDemandTotal = Number(response.total || 0);
    state.publicDemandOffset += items.length;
    $("#public-demand-count").textContent = state.publicDemandTotal.toLocaleString("zh-CN");
    const cards = items.map(renderPublicDemandCard).join("");
    if (reset) list.innerHTML = cards || `<div class="empty-state">没有找到符合条件的技术需求。</div>`;
    else list.insertAdjacentHTML("beforeend", cards);
    list.dataset.loaded = "1";
    moreButton.hidden = state.publicDemandOffset >= state.publicDemandTotal;
    $all('[data-view="submit"]', list).forEach((button) => {
      button.addEventListener("click", () => showView("submit"));
    });
    refreshIcons();
  } catch (error) {
    if (reset) list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    toast(error.message);
  } finally {
    setButtonLoading(moreButton, false);
  }
}

async function loadAdmin() {
  try {
    const session = await api("/api/admin/session");
    state.adminCsrfToken = session.csrf_token || "";
    setAdminView(session.authenticated, session.username || "");
    if (!session.authenticated) {
      resetAdminData();
      return;
    }
    const intentQuery = intentFilterQuery();
    const matchQuery = matchFilterQuery();
    const [stats, intents, matches] = await Promise.all([
      api("/api/stats"),
      api(`/api/intents${intentQuery}`),
      api(`/api/matches${matchQuery}`),
    ]);
    updateStats(stats);
    state.adminStatuses = intents.statuses || [];
    renderIntentFilterOptions();
    renderIntentTable(intents.items || []);
    renderMatchFilter();
    renderMatchTable(matches.items || []);
    if (state.currentMatch?.match_id) {
      await loadMatchDetail(state.currentMatch.match_id);
    }
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

function matchFilterQuery() {
  const params = new URLSearchParams();
  if (state.matchFilters.keyword) params.set("keyword", state.matchFilters.keyword);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function renderMatchFilter() {
  $("#match-keyword").value = state.matchFilters.keyword || "";
}

function applyMatchFilters() {
  state.matchFilters.keyword = $("#match-keyword").value.trim();
  loadAdmin();
}

function clearMatchFilters() {
  state.matchFilters.keyword = "";
  $("#match-keyword").value = "";
  loadAdmin();
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
  state.currentMatch = null;
  $("#match-table").innerHTML = `<tr><td colspan="7">登录后显示匹配记录</td></tr>`;
  $("#match-detail").className = "match-detail empty-state";
  $("#match-detail").textContent = "登录后查看需求方信息和对接进度。";
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
    state.adminCsrfToken = response.csrf_token || "";
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
  state.adminCsrfToken = "";
  $("#demand-preview").dataset.loaded = "";
  state.currentMatch = null;
  $("#match-table").innerHTML = `<tr><td colspan="7">请先登录后台</td></tr>`;
  $("#match-detail").className = "match-detail empty-state";
  $("#match-detail").textContent = "请选择一条匹配记录查看详情。";
  $("#intent-table").innerHTML = `<tr><td colspan="8">请先登录后台</td></tr>`;
  $("#intent-detail").className = "intent-detail empty-state";
  $("#intent-detail").textContent = "请选择左侧线索查看详情。";
  toast("已退出后台");
}

function renderMatchTable(items) {
  const table = $("#match-table");
  if (!items.length) {
    table.innerHTML = `<tr><td colspan="7">暂无匹配记录</td></tr>`;
    return;
  }
  table.innerHTML = items
    .map((item) => {
      const submission = item.submission || {};
      const results = item.results || [];
      return `
        <tr>
          <td>${escapeHtml(item.created_at || "-")}</td>
          <td>
            <span class="status-pill">${escapeHtml(item.match_mode_label || "-")}</span>
            ${item.ai_message ? `<p class="table-muted">${escapeHtml(item.ai_message)}</p>` : ""}
          </td>
          <td>
            <strong>匿名技术匹配</strong>
            <p class="table-muted">联系方式在申请对接后采集</p>
          </td>
          <td>
            <strong>${escapeHtml(submission.title || "技术内容自动分析")}</strong>
            <div class="tags compact-tags">
              ${tag(submission.tech_field)}
              ${tag(submission.region)}
              ${tag(submission.maturity)}
              ${tag(submission.cooperation)}
              ${tag(submission.client_source)}
            </div>
            ${submission.application_scene ? `<p class="table-muted">场景：${escapeHtml(submission.application_scene)}</p>` : ""}
          </td>
          <td class="match-summary">
            ${escapeHtml(submission.achievement_text || submission.summary || submission.advantage || submission.advantages || submission.problem || "-")}
          </td>
          <td>
            <div class="mini-match-results">
              ${
                results.length
                  ? results
                      .slice(0, 3)
                      .map(
                        (result) => `
                          <div>
                            <strong>${escapeHtml(result.name || "-")}</strong>
                            <span class="score-text score-${scoreLevel(result.score)}">${escapeHtml(result.score || "-")}%</span>
                          </div>
                        `,
                      )
                      .join("")
                  : "暂无匹配结果"
              }
            </div>
          </td>
          <td><button class="btn" data-view-match="${escapeHtml(item.match_id)}"><i data-lucide="contact-round"></i>查看/跟进</button></td>
        </tr>
      `;
    })
    .join("");
  $all("[data-view-match]").forEach((button) => {
    button.addEventListener("click", () => loadMatchDetail(button.dataset.viewMatch));
  });
  refreshIcons();
}

function matchFollowupStatusOptions(current) {
  const statuses = state.matchFollowupStatuses.length
    ? state.matchFollowupStatuses
    : ["待联系成果方", "已联系成果方", "待联系需求方", "已联系需求方", "双方沟通中", "已安排会议", "已发送材料", "已签约", "已成交", "暂停跟进", "不再跟进"];
  return statuses
    .map((status) => `<option value="${escapeHtml(status)}" ${status === current ? "selected" : ""}>${escapeHtml(status)}</option>`)
    .join("");
}

async function loadMatchDetail(matchId) {
  const box = $("#match-detail");
  box.className = "match-detail empty-state";
  box.textContent = "正在读取需求方信息和对接进度...";
  try {
    const response = await api(`/api/matches/detail?match_id=${encodeURIComponent(matchId)}`);
    state.matchFollowupStatuses = response.statuses || [];
    renderMatchDetail(response.match || {});
  } catch (error) {
    box.textContent = error.message;
    toast(error.message);
  }
}

function renderMatchDetail(item) {
  state.currentMatch = item;
  const submission = item.submission || {};
  const results = item.results || [];
  const box = $("#match-detail");
  box.className = "match-detail";
  box.innerHTML = `
    <div class="match-detail-summary">
      <div>
        <span class="muted-label">匹配阶段技术内容</span>
        <h3>${escapeHtml(submission.title || "匿名技术成果")}</h3>
        <p>${escapeHtml(submission.achievement_text || submission.summary || "联系方式将在申请对接后采集")}</p>
      </div>
      <span class="status-pill">${escapeHtml(item.match_mode_label || "匹配记录")}</span>
    </div>
    <div class="match-candidate-list">
      ${results.map(renderMatchCandidateFollowup).join("") || '<div class="empty-state">该记录没有可跟进的匹配需求。</div>'}
    </div>
  `;
  $all("[data-save-match-followup]", box).forEach((button) => {
    button.addEventListener("click", () => saveMatchFollowup(button));
  });
  refreshIcons();
}

function renderMatchCandidateFollowup(item) {
  const followup = item.followup || {};
  const demandId = escapeHtml(item.demand_id || "");
  const sourceUrl = safeHttpUrl(item.source_url);
  return `
    <article class="match-candidate-card">
      <div class="match-candidate-head">
        <div>
          <span class="muted-label">${escapeHtml(item.demand_no || item.demand_id || "技术需求")}</span>
          <h3>${escapeHtml(item.name || "未命名需求")}</h3>
        </div>
        <span class="score-text score-${scoreLevel(item.score)}">${escapeHtml(item.score || "-")}%</span>
      </div>
      <div class="private-demand-grid">
        ${detailRow("发布方", item.publisher || "未抓取到")}
        ${detailRow("需求方联系方式", item.contact || "未抓取到")}
        ${detailRow("所在地区", item.region || "-")}
        ${detailRow("合作方式", item.cooperation_mode || "-")}
        ${detailRow("技术领域", item.tech_field || "-")}
        ${detailRow("需求类型", item.demand_type || "-")}
      </div>
      <div class="private-demand-detail">
        <strong>完整需求信息</strong>
        <p>${escapeHtml(item.full_detail || item.detail_summary || "暂无详情")}</p>
        ${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer"><i data-lucide="external-link"></i>打开原始需求页面</a>` : ""}
      </div>
      <div class="match-followup-editor">
        <label>对接状态<select data-match-followup-status="${demandId}">${matchFollowupStatusOptions(followup.status || "待联系成果方")}</select></label>
        <label>联系记录<textarea data-match-contact-note="${demandId}" placeholder="例如：电话联系需求方，对方希望先看技术参数。">${escapeHtml(followup.contact_note || "")}</textarea></label>
        <label>项目对接进度<textarea data-match-project-progress="${demandId}" placeholder="填写当前进展、待办事项和下一步计划。">${escapeHtml(followup.project_progress || "")}</textarea></label>
        <div class="followup-save-row">
          <span>${followup.updated_at ? `最近更新：${escapeHtml(followup.updated_at)}` : "尚未保存对接记录"}</span>
          <button class="btn primary" data-save-match-followup="${demandId}"><i data-lucide="save"></i>保存对接进度</button>
        </div>
      </div>
    </article>
  `;
}

async function saveMatchFollowup(button) {
  if (!state.currentMatch) return;
  const demandId = button.dataset.saveMatchFollowup;
  const status = $(`[data-match-followup-status="${CSS.escape(demandId)}"]`).value;
  const contactNote = $(`[data-match-contact-note="${CSS.escape(demandId)}"]`).value.trim();
  const projectProgress = $(`[data-match-project-progress="${CSS.escape(demandId)}"]`).value.trim();
  setButtonLoading(button, true, "保存中");
  try {
    const response = await api("/api/matches/followup", {
      method: "POST",
      body: JSON.stringify({
        match_id: state.currentMatch.match_id,
        demand_id: demandId,
        status,
        contact_note: contactNote,
        project_progress: projectProgress,
      }),
    });
    state.matchFollowupStatuses = response.statuses || state.matchFollowupStatuses;
    renderMatchDetail(response.match || {});
    toast("对接进度已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    if (button.isConnected) setButtonLoading(button, false);
  }
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
          <td>${escapeHtml(selected.name || "-")}<br><span class="muted-label">${escapeHtml(item.query_code || "-")}</span></td>
          <td><span class="score-text score-${scoreLevel(selected.score)}">${escapeHtml(selected.score || "-")}%</span></td>
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
  state.currentIntent = item;
  const contact = item.contact || {};
  const selected = item.selected_result || {};
  const logs = item.status_logs || [];
  const progress = item.progress || [];
  const box = $("#intent-detail");
  box.className = "intent-detail";
  box.innerHTML = `
    <div class="detail-section">
      <h3>来访者</h3>
      ${detailRow("查询码", item.query_code || "-")}
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
      ${detailRow("对外说明", item.public_note || "-")}
      <div class="log-list">
        ${logs.length ? logs.map(renderStatusLog).join("") : '<div class="log-item">暂无状态变更记录</div>'}
      </div>
    </div>
    <div class="detail-section admin-progress-editor">
      <h3>后台进度表</h3>
      <div class="form-grid compact-form">
        <label>
          当前状态
          <select id="detail-status">${statusOptions(item.status || "待审核")}</select>
        </label>
        <label class="full">
          内部备注
          <textarea id="detail-note" placeholder="只在后台显示">${escapeHtml(item.followup_note || "")}</textarea>
        </label>
        <label class="full">
          对外进度说明
          <textarea id="detail-public-note" placeholder="用户输入查询码后可见">${escapeHtml(item.public_note || "")}</textarea>
        </label>
      </div>
      <div class="progress-editor">
        ${progress.map(renderAdminProgressStep).join("")}
      </div>
      <div class="form-grid compact-form">
        <label>
          成交金额
          <input id="detail-deal-amount" value="${escapeHtml(item.deal_amount || "")}" placeholder="仅后台可见" />
        </label>
        <label>
          成交备注
          <input id="detail-deal-note" value="${escapeHtml(item.deal_note || "")}" placeholder="仅后台可见" />
        </label>
      </div>
      <button class="btn primary" data-save-intent-detail="${escapeHtml(item.intent_id)}"><i data-lucide="save"></i>保存进度</button>
    </div>
  `;
  const saveButton = $("[data-save-intent-detail]", box);
  if (saveButton) {
    saveButton.addEventListener("click", () => saveIntentDetail(saveButton));
  }
  refreshIcons();
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

function renderAdminProgressStep(step) {
  const key = escapeHtml(step.key);
  return `
    <div class="progress-edit-row">
      <label class="check-row">
        <input type="checkbox" data-progress-done="${key}" ${step.done ? "checked" : ""} />
        <span>${escapeHtml(step.label || "-")}</span>
      </label>
      <input data-progress-public-note="${key}" value="${escapeHtml(step.public_note || "")}" placeholder="对外说明，可留空" />
      <input data-progress-note="${key}" value="${escapeHtml(step.note || "")}" placeholder="内部备注，可留空" />
    </div>
  `;
}

function collectProgressFromDetail() {
  const current = state.currentIntent?.progress || [];
  return current.map((step) => {
    const key = step.key;
    const doneInput = $(`[data-progress-done="${CSS.escape(key)}"]`);
    const publicInput = $(`[data-progress-public-note="${CSS.escape(key)}"]`);
    const noteInput = $(`[data-progress-note="${CSS.escape(key)}"]`);
    const wasDone = Boolean(step.done);
    const done = Boolean(doneInput?.checked);
    return {
      ...step,
      done,
      updated_at: done ? (wasDone ? step.updated_at || "" : new Date().toLocaleString("zh-CN", { hour12: false })) : "",
      public_note: publicInput?.value.trim() || "",
      note: noteInput?.value.trim() || "",
    };
  });
}

function statusOptions(current) {
  const statuses = state.adminStatuses.length
    ? state.adminStatuses
    : ["待审核", "已联系成果方", "已联系需求方", "撮合中", "已签中介协议", "合作成功", "合作失败"];
  return statuses
    .map((status) => `<option value="${escapeHtml(status)}" ${status === current ? "selected" : ""}>${escapeHtml(status)}</option>`)
    .join("");
}

async function saveIntentDetail(button) {
  if (!state.currentIntent) return;
  setButtonLoading(button, true, "保存中");
  try {
    const response = await api("/api/intents/status", {
      method: "POST",
      body: JSON.stringify({
        intent_id: state.currentIntent.intent_id,
        status: $("#detail-status").value,
        note: $("#detail-note").value,
        public_note: $("#detail-public-note").value,
        progress: collectProgressFromDetail(),
        deal_amount: $("#detail-deal-amount").value,
        deal_note: $("#detail-deal-note").value,
      }),
    });
    renderIntentTable(response.items || []);
    renderIntentDetail(response.intent);
    toast("进度已保存");
  } catch (error) {
    if (error.status === 401) setAdminView(false, "");
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
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
            ${tag(item.publisher ? `发布方 ${item.publisher}` : "")}
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
  $("#progress-query").addEventListener("click", () => queryProgress($("#progress-query")));
  $("#public-demand-more").addEventListener("click", () => loadPublicDemands(false));
  $("#copy-query-code").addEventListener("click", async () => {
    const code = $("#success-query-code").textContent.trim();
    if (!code || code === "-") {
      toast("暂无可复制的查询码");
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      toast(`查询码 ${code} 已复制`);
    } catch {
      toast(`查询码：${code}`);
    }
  });
  $("#admin-refresh").addEventListener("click", loadAdmin);
  $("#match-refresh").addEventListener("click", loadAdmin);
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
  $("#match-filter").addEventListener("click", applyMatchFilters);
  $("#match-clear-filter").addEventListener("click", clearMatchFilters);
  $("#match-keyword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyMatchFilters();
    }
  });
  $("#demand-search").addEventListener("click", () => loadDemandPreview($("#demand-keyword").value.trim()));
  $("#demand-keyword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadDemandPreview($("#demand-keyword").value.trim());
    }
  });
  $("#progress-query-code").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      queryProgress($("#progress-query"));
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  setMatchMode("ai");
  loadStats();
  refreshIcons();
  if (window.location.pathname === "/admin") {
    showView("admin");
  }
});
