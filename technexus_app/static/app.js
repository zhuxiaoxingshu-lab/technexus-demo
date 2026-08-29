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
  managerAuthenticated: false,
  manager: null,
  managerCsrfToken: "",
  managerProjects: [],
  managerSettlements: [],
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
  currentAdminManager: null,
  currentAdminManagerProject: null,
  managerVerificationStatuses: [],
  managerProjectStatuses: [],
  managerUnlockStatuses: [],
  managerFeeStatuses: [],
  settlementTypes: [],
  settlementStatuses: [],
  adminManagers: [],
  adminManagerProjects: [],
};

const titleMap = {
  home: ["技术成果找需求", "提交技术成果，AI 匹配真实技术需求，合作意向由平台人工审核撮合。"],
  demands: ["技术需求大厅", "浏览真实需求样本，提交成果后由 AI 从完整需求库精准匹配。"],
  submit: ["成果提交", "粘贴一段完整技术内容，系统自动分析并匹配。"],
  results: ["匹配结果", "展示匹配分数、具体技术需求和合作建议，不展示需求方身份及联系方式。"],
  intent: ["申请对接", "选中需求后填写联系方式并确认协议，进入平台人工审核。"],
  progress: ["进度查询", "输入查询码，查看技术撮合对接进度。"],
  manager: ["技术经理人中心", "上传企业技术需求，选择平台委托或自主对接，并跟踪项目与结算。"],
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
  if (id === "manager") {
    loadManager();
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
    const legacyAdminPaths = new Set(["/api/intents/status", "/api/matches/followup"]);
    const isAdminWrite = path.startsWith("/api/admin/") && path !== "/api/admin/login";
    const isManagerWrite =
      path.startsWith("/api/manager/") && !["/api/manager/login", "/api/manager/register"].includes(path);
    if (method !== "GET" && state.adminCsrfToken && (isAdminWrite || legacyAdminPaths.has(path))) {
      headers["X-CSRF-Token"] = state.adminCsrfToken;
    }
    if (method !== "GET" && state.managerCsrfToken && isManagerWrite) {
      headers["X-CSRF-Token"] = state.managerCsrfToken;
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
  $("#result-status").hidden = false;
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
      $("#result-status").hidden = false;
    }
    renderResults(state.results);
    updateStats(response);
    showView("results");
    toast(`${response.ai_meta?.used_ai ? "DeepSeek AI 已精排" : currentMatchModeLabel() + "已完成"}，生成 ${state.results.length} 条结果`);
  } catch (error) {
    $("#result-status").textContent = error.message;
    $("#result-status").hidden = false;
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
    status.hidden = false;
    list.innerHTML = "";
    return;
  }
  status.hidden = true;
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
      <progress class="bar" max="100" value="${safe}" aria-label="${escapeHtml(name)} ${safe} 分"></progress>
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

function setManagerView(authenticated, manager = null) {
  state.managerAuthenticated = Boolean(authenticated);
  state.manager = manager || null;
  $("#manager-auth-panel").hidden = Boolean(authenticated);
  $("#manager-content").hidden = !authenticated;
  if (authenticated && manager) {
    $("#manager-display-name").textContent = `${manager.real_name || "-"} · ${manager.organization || "-"}`;
    $("#manager-verification-badge").textContent = manager.verification_status || "待认证";
    $("#manager-verification-badge").className = `status-pill manager-status-${
      manager.verification_status === "已认证" ? "approved" : manager.verification_status === "认证未通过" ? "rejected" : "pending"
    }`;
  }
}

function renderManagerWorkbench(data) {
  const manager = data.manager || state.manager || {};
  const stats = data.stats || {};
  state.manager = manager;
  state.managerProjects = data.projects || [];
  state.managerSettlements = data.settlements || [];
  setManagerView(true, manager);
  $("#manager-project-count").textContent = stats.project_count ?? 0;
  $("#manager-active-count").textContent = stats.active_count ?? 0;
  $("#manager-unlocked-count").textContent = stats.unlocked_count ?? 0;
  $("#manager-settled-share").textContent = stats.settled_share || "0.00";

  const verified = manager.verification_status === "已认证";
  const notice = $("#manager-verification-notice");
  notice.className = `manager-notice ${verified ? "approved" : manager.verification_status === "认证未通过" ? "rejected" : "pending"}`;
  notice.innerHTML = verified
    ? `<i data-lucide="badge-check"></i><div><strong>认证已通过</strong><span>你可以上传企业需求，并在工作台跟踪审核、解锁与结算。</span></div>`
    : manager.verification_status === "认证未通过"
      ? `<i data-lucide="shield-alert"></i><div><strong>认证资料需要补充</strong><span>${escapeHtml(manager.verification_note || "请联系平台补充或更正认证信息。")}</span></div>`
      : `<i data-lucide="clock-3"></i><div><strong>认证审核中</strong><span>平台审核通过后即可提交企业技术需求；当前可先查看工作台。</span></div>`;
  $all("input, textarea, button", $("#manager-project-form")).forEach((field) => {
    field.disabled = !verified;
  });
  renderManagerProjects(state.managerProjects);
  renderManagerSettlements(state.managerSettlements);
  refreshIcons();
}

function renderManagerProjects(items) {
  const list = $("#manager-project-list");
  if (!items.length) {
    list.innerHTML = `<div class="empty-state">暂无项目。认证通过后，可在上方粘贴企业技术需求并选择服务方式。</div>`;
    return;
  }
  list.innerHTML = items
    .map((item) => {
      const contact = item.counterpart_contact || {};
      const unlocked = Boolean(contact.unlocked);
      const hasCounterpart = Boolean(item.has_counterpart_contact);
      const canReportSelfService =
        item.service_mode === "self_service" &&
        item.status !== "待平台审核" &&
        !["已成交", "已关闭", "审核未通过"].includes(item.status);
      return `
        <article class="manager-project-card">
          <div class="manager-project-head">
            <div><span class="project-no">${escapeHtml(item.project_no || "-")}</span><strong>${escapeHtml(item.service_mode_label || "-")}</strong></div>
            <span class="status-pill">${escapeHtml(item.status || "-")}</span>
          </div>
          <p class="manager-demand-summary">${escapeHtml(item.enterprise_demand_text || "-")}</p>
          <div class="project-stage-grid">
            <div><span>平台审核</span><strong>${escapeHtml(item.audit_note || (item.status === "待平台审核" ? "等待审核" : "已处理"))}</strong></div>
            <div><span>匹配 / 对接进展</span><strong>${escapeHtml(item.match_summary || "暂无进展记录")}</strong></div>
            <div><span>服务费</span><strong>${escapeHtml(item.service_fee_status || "-")}</strong></div>
            <div><span>${hasCounterpart ? "联系方式" : "对接方"}</span><strong>${escapeHtml(hasCounterpart ? item.contact_unlock_status || "未解锁" : "未登记")}</strong></div>
          </div>
          ${hasCounterpart ? `<div class="counterpart-card ${unlocked ? "unlocked" : "locked"}">
            <i data-lucide="${unlocked ? "contact-round" : "lock-keyhole"}"></i>
            <div>
              <strong>${escapeHtml(contact.organization || "对接方信息受保护")}<small>${escapeHtml(item.counterpart_contact_source_label || "")}</small></strong>
              <span>${escapeHtml(contact.name || "审核通过后可见")} · ${escapeHtml(contact.phone || "•••••••••••")}${contact.email ? ` · ${escapeHtml(contact.email)}` : ""}</span>
            </div>
          </div>` : ""}
          ${canReportSelfService ? `<details class="self-service-progress-panel">
            <summary><span><i data-lucide="clipboard-pen-line"></i>登记自主对接进展</span><small>已找到技术资源后填写</small></summary>
            <form class="self-service-progress-form" data-project-id="${escapeHtml(item.project_id)}">
              <label>进展状态<select name="status">
                <option value="已建立技术对接" ${item.status === "已建立技术对接" ? "selected" : ""}>已建立技术对接</option>
                <option value="对接中" ${item.status === "对接中" ? "selected" : ""}>对接中</option>
              </select></label>
              <label>技术对接方单位<input name="organization" value="${escapeHtml(contact.organization || "")}" placeholder="高校、科研院所或技术团队" required /></label>
              <label>联系人<input name="name" value="${escapeHtml(contact.name || "")}" placeholder="真实联系人姓名" required /></label>
              <label>手机号<input name="phone" value="${escapeHtml(contact.phone || "")}" inputmode="tel" placeholder="手机号或座机" /></label>
              <label>邮箱<input name="email" value="${escapeHtml(contact.email || "")}" type="email" placeholder="手机号和邮箱至少填一项" /></label>
              <label class="full">本阶段进展<textarea name="progress_summary" minlength="10" placeholder="例如：已与技术团队完成首次电话沟通，双方确认下周交换技术指标和样品测试条件。" required>${escapeHtml(item.match_summary || "")}</textarea></label>
              <p class="self-service-fee-note full">登记进入实质对接后，平台服务费状态转为“待确认”，具体金额仍由双方按约定人工确认。</p>
              <button class="btn primary full" type="submit"><i data-lucide="save"></i>保存自主对接进展</button>
            </form>
          </details>` : ""}
          <footer><span>提交于 ${escapeHtml(item.created_at || "-")}</span><span>更新于 ${escapeHtml(item.updated_at || "-")}</span></footer>
        </article>`;
    })
    .join("");
  $all(".self-service-progress-form", list).forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveManagerSelfServiceProgress(form, $("button[type='submit']", form));
    });
  });
  refreshIcons();
}

function renderManagerSettlements(items) {
  const table = $("#manager-settlement-table");
  if (!items.length) {
    table.innerHTML = `<tr><td colspan="7">暂无结算记录</td></tr>`;
    return;
  }
  table.innerHTML = items
    .map((item) => {
      const project = state.managerProjects.find((candidate) => candidate.project_id === item.project_id) || {};
      return `<tr>
        <td>${escapeHtml(item.updated_at || "-")}</td>
        <td>${escapeHtml(project.project_no || "-")}</td>
        <td>${escapeHtml(item.settlement_type || "-")}</td>
        <td>¥${escapeHtml(item.deal_amount || "0.00")}</td>
        <td>¥${escapeHtml(item.platform_fee || "0.00")}</td>
        <td>¥${escapeHtml(item.manager_share || "0.00")}</td>
        <td><span class="status-pill">${escapeHtml(item.status || "-")}</span></td>
      </tr>`;
    })
    .join("");
}

async function loadManager() {
  try {
    const session = await api("/api/manager/session");
    state.managerCsrfToken = session.csrf_token || "";
    if (!session.authenticated) {
      setManagerView(false, null);
      return;
    }
    const workbench = await api("/api/manager/workbench");
    renderManagerWorkbench(workbench);
  } catch (error) {
    if (error.status === 401) {
      state.managerCsrfToken = "";
      setManagerView(false, null);
      return;
    }
    toast(error.message);
  }
}

async function loginManager(button) {
  const payload = formDataToObject($("#manager-login-form"));
  setButtonLoading(button, true, "正在登录");
  try {
    const response = await api("/api/manager/login", { method: "POST", body: JSON.stringify(payload) });
    state.managerCsrfToken = response.csrf_token || "";
    $("#manager-login-form").reset();
    toast("登录成功");
    await loadManager();
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function registerManager(button) {
  const payload = formDataToObject($("#manager-register-form"));
  if (payload.password !== payload.password_confirm) {
    toast("两次输入的密码不一致");
    return;
  }
  delete payload.password_confirm;
  setButtonLoading(button, true, "正在提交");
  try {
    const response = await api("/api/manager/register", { method: "POST", body: JSON.stringify(payload) });
    state.managerCsrfToken = response.csrf_token || "";
    $("#manager-register-form").reset();
    toast("认证申请已提交");
    await loadManager();
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function logoutManager() {
  try {
    await api("/api/manager/logout", { method: "POST", body: JSON.stringify({}) });
  } catch {
    // 会话失效时也应返回登录界面。
  }
  state.managerCsrfToken = "";
  state.managerProjects = [];
  state.managerSettlements = [];
  setManagerView(false, null);
  toast("已退出经理人中心");
}

async function submitManagerProject(button) {
  const payload = formDataToObject($("#manager-project-form"));
  if (String(payload.enterprise_demand_text || "").trim().length < 30) {
    toast("请至少填写 30 个字的企业技术需求");
    return;
  }
  setButtonLoading(button, true, "正在提交");
  try {
    const response = await api("/api/manager/projects", { method: "POST", body: JSON.stringify(payload) });
    $("#manager-project-form").reset();
    const defaultMode = $('input[name="service_mode"][value="entrusted"]');
    if (defaultMode) defaultMode.checked = true;
    syncServiceModeCards();
    renderManagerWorkbench(response);
    toast(`企业需求 ${response.project?.project_no || ""} 已提交`);
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function saveManagerSelfServiceProgress(form, button) {
  const values = formDataToObject(form);
  const payload = {
    project_id: form.dataset.projectId,
    status: values.status,
    progress_summary: values.progress_summary,
    counterpart_contact: {
      organization: values.organization,
      name: values.name,
      phone: values.phone,
      email: values.email,
    },
  };
  setButtonLoading(button, true, "正在保存");
  try {
    const response = await api("/api/manager/projects/self-service-progress", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderManagerWorkbench(response);
    toast("自主对接进展已保存，平台后台已同步");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

function syncServiceModeCards() {
  $all(".service-mode-card").forEach((card) => {
    const input = $("input", card);
    card.classList.toggle("active", Boolean(input?.checked));
  });
}

function optionMarkup(values, current) {
  return (values || [])
    .map((value) => `<option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${escapeHtml(value)}</option>`)
    .join("");
}

function renderAdminManagers(items) {
  const table = $("#admin-manager-table");
  if (!items.length) {
    table.innerHTML = `<tr><td colspan="7">暂无认证申请</td></tr>`;
    return;
  }
  table.innerHTML = items
    .map(
      (item) => `<tr>
        <td>${escapeHtml(item.created_at || "-")}</td>
        <td><strong>${escapeHtml(item.real_name || "-")}</strong><p class="table-muted">${escapeHtml(item.phone || "-")}</p></td>
        <td>${escapeHtml(item.organization || "-")}</td>
        <td>${escapeHtml(item.credential_no || "-")}</td>
        <td>${Number(item.project_count || 0)}</td>
        <td><span class="status-pill">${escapeHtml(item.verification_status || "-")}</span></td>
        <td><button class="btn" data-admin-manager="${escapeHtml(item.manager_id)}"><i data-lucide="badge-check"></i>审核</button></td>
      </tr>`,
    )
    .join("");
  $all("[data-admin-manager]").forEach((button) => {
    button.addEventListener("click", () => showAdminManager(button.dataset.adminManager));
  });
  refreshIcons();
}

function showAdminManager(managerId) {
  const item = state.adminManagers.find((manager) => manager.manager_id === managerId);
  if (!item) return;
  state.currentAdminManager = item;
  const box = $("#admin-manager-detail");
  box.className = "manager-review-form";
  box.innerHTML = `
    <div class="detail-section">
      ${detailRow("姓名 / 手机", `${item.real_name || "-"} · ${item.phone || "-"}`)}
      ${detailRow("所在机构", item.organization || "-")}
      ${detailRow("证书 / 说明", item.credential_no || "-")}
    </div>
    <label>认证状态<select id="admin-manager-status">${optionMarkup(state.managerVerificationStatuses, item.verification_status)}</select></label>
    <label>审核意见<textarea id="admin-manager-note" placeholder="认证通过依据，或需要补充的资料">${escapeHtml(item.verification_note || "")}</textarea></label>
    <button class="btn primary" id="admin-manager-save"><i data-lucide="save"></i>保存认证结果</button>`;
  $("#admin-manager-save").addEventListener("click", saveAdminManagerVerification);
  refreshIcons();
}

async function saveAdminManagerVerification() {
  if (!state.currentAdminManager) return;
  const button = $("#admin-manager-save");
  setButtonLoading(button, true, "正在保存");
  try {
    const response = await api("/api/admin/managers/verify", {
      method: "POST",
      body: JSON.stringify({
        manager_id: state.currentAdminManager.manager_id,
        verification_status: $("#admin-manager-status").value,
        verification_note: $("#admin-manager-note").value.trim(),
      }),
    });
    state.adminManagers = response.items || [];
    renderAdminManagers(state.adminManagers);
    state.currentAdminManager = response.manager;
    showAdminManager(response.manager.manager_id);
    toast("认证结果已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

function renderAdminManagerProjects(items) {
  const table = $("#admin-manager-project-table");
  if (!items.length) {
    table.innerHTML = `<tr><td colspan="8">暂无经理人项目</td></tr>`;
    return;
  }
  table.innerHTML = items
    .map(
      (item) => `<tr>
        <td>${escapeHtml(item.created_at || "-")}<p class="table-muted">${escapeHtml(item.project_no || "-")}</p></td>
        <td><strong>${escapeHtml(item.manager_name || "-")}</strong><p class="table-muted">${escapeHtml(item.manager_organization || "-")}</p></td>
        <td>${escapeHtml(item.service_mode_label || "-")}</td>
        <td class="admin-demand-cell">${escapeHtml(item.enterprise_demand_text || "-")}</td>
        <td><span class="status-pill">${escapeHtml(item.status || "-")}</span></td>
        <td>${escapeHtml(item.has_counterpart_contact ? item.counterpart_contact_source_label || item.contact_unlock_status || "-" : "未登记")}</td>
        <td>${escapeHtml(item.service_fee_status || "-")}</td>
        <td><button class="btn" data-admin-manager-project="${escapeHtml(item.project_id)}"><i data-lucide="settings-2"></i>处理</button></td>
      </tr>`,
    )
    .join("");
  $all("[data-admin-manager-project]").forEach((button) => {
    button.addEventListener("click", () => loadAdminManagerProject(button.dataset.adminManagerProject));
  });
  refreshIcons();
}

async function loadAdminManagerProject(projectId) {
  const box = $("#admin-manager-project-detail");
  box.className = "manager-project-admin-detail empty-state";
  box.textContent = "正在读取项目详情...";
  try {
    const response = await api(`/api/admin/manager-projects/detail?project_id=${encodeURIComponent(projectId)}`);
    state.managerProjectStatuses = response.project_statuses || state.managerProjectStatuses;
    state.managerUnlockStatuses = response.unlock_statuses || state.managerUnlockStatuses;
    state.managerFeeStatuses = response.fee_statuses || state.managerFeeStatuses;
    state.settlementTypes = response.settlement_types || state.settlementTypes;
    state.settlementStatuses = response.settlement_statuses || state.settlementStatuses;
    state.currentAdminManagerProject = response.project;
    renderAdminManagerProjectDetail(response.project);
  } catch (error) {
    box.textContent = error.message;
    toast(error.message);
  }
}

function renderAdminManagerProjectDetail(item) {
  const box = $("#admin-manager-project-detail");
  const contact = item.counterpart_contact || {};
  const settlement = (item.settlements || [])[0] || {};
  const defaultSettlementType = item.service_mode === "entrusted" ? "平台撮合分成" : "自主对接服务费";
  box.className = "manager-project-admin-detail";
  box.innerHTML = `
    <div class="manager-admin-summary">
      <div><span>项目编号</span><strong>${escapeHtml(item.project_no || "-")}</strong></div>
      <div><span>技术经理人</span><strong>${escapeHtml(`${item.manager_name || "-"} · ${item.manager_phone || "-"}`)}</strong></div>
      <div><span>机构</span><strong>${escapeHtml(item.manager_organization || "-")}</strong></div>
      <div><span>服务方式</span><strong>${escapeHtml(item.service_mode_label || "-")}</strong></div>
      <div><span>对接方来源</span><strong>${escapeHtml(item.has_counterpart_contact ? item.counterpart_contact_source_label || "平台登记" : "未登记")}</strong></div>
    </div>
    <div class="detail-section"><h3>企业技术需求</h3><p class="detail-text">${escapeHtml(item.enterprise_demand_text || "-")}</p></div>
    <div class="manager-admin-form-grid">
      <label>项目状态<select id="manager-project-status">${optionMarkup(state.managerProjectStatuses, item.status)}</select></label>
      <label>服务费状态<select id="manager-project-fee-status">${optionMarkup(state.managerFeeStatuses, item.service_fee_status)}</select></label>
      <label>联系方式<select id="manager-project-unlock-status">${optionMarkup(state.managerUnlockStatuses, item.contact_unlock_status)}</select></label>
      <label>对接方单位<input id="manager-counterpart-organization" value="${escapeHtml(contact.organization || "")}" placeholder="实际接洽的技术单位或团队" /></label>
      <label>联系人<input id="manager-counterpart-name" value="${escapeHtml(contact.name || "")}" /></label>
      <label>手机号<input id="manager-counterpart-phone" value="${escapeHtml(contact.phone || "")}" /></label>
      <label>邮箱<input id="manager-counterpart-email" value="${escapeHtml(contact.email || "")}" /></label>
      <label class="full">审核意见<textarea id="manager-project-audit-note" placeholder="对经理人可见">${escapeHtml(item.audit_note || "")}</textarea></label>
      <label class="full">匹配 / 对接进展<textarea id="manager-project-match-summary" placeholder="记录平台寻找技术资源或经理人自主对接的当前进展">${escapeHtml(item.match_summary || "")}</textarea></label>
    </div>
    <button class="btn primary" id="manager-project-admin-save"><i data-lucide="save"></i>保存项目状态</button>
    <div class="settlement-editor">
      <div><h3>人工结算登记</h3><p>金额单位：元。P0 先由后台依据协议人工核定。</p></div>
      <input type="hidden" id="manager-settlement-id" value="${escapeHtml(settlement.settlement_id || "")}" />
      <div class="manager-admin-form-grid">
        <label>结算类型<select id="manager-settlement-type">${optionMarkup(state.settlementTypes, settlement.settlement_type || defaultSettlementType)}</select></label>
        <label>结算状态<select id="manager-settlement-status">${optionMarkup(state.settlementStatuses, settlement.status || "待确认")}</select></label>
        <label>项目成交额<input id="manager-deal-amount" inputmode="decimal" value="${escapeHtml(settlement.deal_amount || "0.00")}" /></label>
        <label>平台费用<input id="manager-platform-fee" inputmode="decimal" value="${escapeHtml(settlement.platform_fee || "0.00")}" /></label>
        <label>经理人分成<input id="manager-share" inputmode="decimal" value="${escapeHtml(settlement.manager_share || "0.00")}" /></label>
        <label class="full">结算备注<textarea id="manager-settlement-note">${escapeHtml(settlement.note || "")}</textarea></label>
      </div>
      <button class="btn warning" id="manager-settlement-save"><i data-lucide="badge-dollar-sign"></i>保存结算记录</button>
    </div>
    <div class="project-log-list">
      <h3>操作记录</h3>
      ${(item.logs || []).map((log) => `<div><span>${escapeHtml(log.created_at || "-")}</span><strong>${escapeHtml(log.action || "-")}</strong><p>${escapeHtml(log.note || "")}</p></div>`).join("") || '<p class="table-muted">暂无记录</p>'}
    </div>`;
  $("#manager-project-admin-save").addEventListener("click", saveAdminManagerProject);
  $("#manager-settlement-save").addEventListener("click", saveAdminManagerSettlement);
  refreshIcons();
}

async function saveAdminManagerProject() {
  const item = state.currentAdminManagerProject;
  if (!item) return;
  const button = $("#manager-project-admin-save");
  setButtonLoading(button, true, "正在保存");
  try {
    const response = await api("/api/admin/manager-projects/update", {
      method: "POST",
      body: JSON.stringify({
        project_id: item.project_id,
        status: $("#manager-project-status").value,
        service_fee_status: $("#manager-project-fee-status").value,
        contact_unlock_status: $("#manager-project-unlock-status").value,
        audit_note: $("#manager-project-audit-note").value.trim(),
        match_summary: $("#manager-project-match-summary").value.trim(),
        counterpart_contact: {
          organization: $("#manager-counterpart-organization").value.trim(),
          name: $("#manager-counterpart-name").value.trim(),
          phone: $("#manager-counterpart-phone").value.trim(),
          email: $("#manager-counterpart-email").value.trim(),
        },
      }),
    });
    state.adminManagerProjects = response.items || [];
    renderAdminManagerProjects(state.adminManagerProjects);
    state.currentAdminManagerProject = response.project;
    renderAdminManagerProjectDetail(response.project);
    toast("经理人项目已更新");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
  }
}

async function saveAdminManagerSettlement() {
  const item = state.currentAdminManagerProject;
  if (!item) return;
  const button = $("#manager-settlement-save");
  setButtonLoading(button, true, "正在保存");
  try {
    const response = await api("/api/admin/manager-settlements/save", {
      method: "POST",
      body: JSON.stringify({
        settlement_id: $("#manager-settlement-id").value,
        project_id: item.project_id,
        settlement_type: $("#manager-settlement-type").value,
        status: $("#manager-settlement-status").value,
        deal_amount: $("#manager-deal-amount").value,
        platform_fee: $("#manager-platform-fee").value,
        manager_share: $("#manager-share").value,
        note: $("#manager-settlement-note").value.trim(),
      }),
    });
    state.currentAdminManagerProject = response.project;
    renderAdminManagerProjectDetail(response.project);
    toast("结算记录已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    setButtonLoading(button, false);
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
    const [stats, intents, matches, managers, managerProjects] = await Promise.all([
      api("/api/stats"),
      api(`/api/intents${intentQuery}`),
      api(`/api/matches${matchQuery}`),
      api("/api/admin/managers"),
      api("/api/admin/manager-projects"),
    ]);
    updateStats(stats);
    state.adminStatuses = intents.statuses || [];
    renderIntentFilterOptions();
    renderIntentTable(intents.items || []);
    renderMatchFilter();
    renderMatchTable(matches.items || []);
    state.adminManagers = managers.items || [];
    state.managerVerificationStatuses = managers.verification_statuses || [];
    state.adminManagerProjects = managerProjects.items || [];
    state.managerProjectStatuses = managerProjects.project_statuses || [];
    state.managerUnlockStatuses = managerProjects.unlock_statuses || [];
    state.managerFeeStatuses = managerProjects.fee_statuses || [];
    state.settlementTypes = managerProjects.settlement_types || [];
    state.settlementStatuses = managerProjects.settlement_statuses || [];
    $("#admin-manager-count").textContent = state.adminManagers.length.toLocaleString("zh-CN");
    $("#admin-manager-project-count").textContent = state.adminManagerProjects.length.toLocaleString("zh-CN");
    renderAdminManagers(state.adminManagers);
    renderAdminManagerProjects(state.adminManagerProjects);
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
  $("#admin-manager-count").textContent = "-";
  $("#admin-manager-project-count").textContent = "-";
  state.currentMatch = null;
  $("#match-table").innerHTML = `<tr><td colspan="7">登录后显示匹配记录</td></tr>`;
  $("#match-detail").className = "match-detail empty-state";
  $("#match-detail").textContent = "登录后查看需求方信息和对接进度。";
  $("#intent-table").innerHTML = `<tr><td colspan="8">登录后显示合作意向</td></tr>`;
  $("#intent-detail").className = "intent-detail empty-state";
  $("#intent-detail").textContent = "登录后查看线索详情。";
  state.adminManagers = [];
  state.adminManagerProjects = [];
  state.currentAdminManager = null;
  state.currentAdminManagerProject = null;
  $("#admin-manager-table").innerHTML = `<tr><td colspan="7">登录后显示认证申请</td></tr>`;
  $("#admin-manager-project-table").innerHTML = `<tr><td colspan="8">登录后显示经理人项目</td></tr>`;
  $("#admin-manager-detail").className = "empty-state";
  $("#admin-manager-detail").textContent = "请选择技术经理人申请。";
  $("#admin-manager-project-detail").className = "manager-project-admin-detail empty-state";
  $("#admin-manager-project-detail").textContent = "请选择一个经理人项目进行审核与结算。";
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
  state.adminManagers = [];
  state.adminManagerProjects = [];
  $("#admin-manager-table").innerHTML = `<tr><td colspan="7">请先登录后台</td></tr>`;
  $("#admin-manager-project-table").innerHTML = `<tr><td colspan="8">请先登录后台</td></tr>`;
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
      const hasInternalUnit = Boolean(submission.company);
      return `
        <tr>
          <td>${escapeHtml(item.created_at || "-")}</td>
          <td>
            <span class="status-pill">${escapeHtml(item.match_mode_label || "-")}</span>
            ${item.ai_message ? `<p class="table-muted">${escapeHtml(item.ai_message)}</p>` : ""}
          </td>
          <td>
            <strong>${escapeHtml(hasInternalUnit ? submission.company : "匿名技术匹配")}</strong>
            <p class="table-muted">${escapeHtml(
              hasInternalUnit
                ? `${submission.client_source || "后台单位信息"} · ${submission.name || "技术成果"}`
                : "联系方式在申请对接后采集",
            )}</p>
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
        ${submission.company ? `<p><strong>${escapeHtml(submission.company)}</strong> · ${escapeHtml(submission.name || "技术成果")}</p>` : ""}
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
  $("#admin-manager-refresh").addEventListener("click", loadAdmin);
  $("#admin-manager-project-refresh").addEventListener("click", loadAdmin);
  $("#admin-logout").addEventListener("click", logoutAdmin);
  $("#admin-login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loginAdmin($("#admin-login-submit"));
  });
  $("#manager-login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loginManager($("#manager-login-submit"));
  });
  $("#manager-register-form").addEventListener("submit", (event) => {
    event.preventDefault();
    registerManager($("#manager-register-submit"));
  });
  $("#manager-project-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitManagerProject($("#manager-project-submit"));
  });
  $("#manager-logout").addEventListener("click", logoutManager);
  $("#manager-refresh").addEventListener("click", loadManager);
  $all('input[name="service_mode"]').forEach((input) => input.addEventListener("change", syncServiceModeCards));
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
  } else if (window.location.pathname === "/manager") {
    showView("manager");
  }
});
