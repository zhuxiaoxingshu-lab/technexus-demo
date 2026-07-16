const api = require("../../utils/api");

function hasUsefulContent(payload) {
  return [
    payload.title,
    payload.achievement_text,
    payload.tech_field,
    payload.summary,
    payload.technical_route,
    payload.indicators,
    payload.evidence,
    payload.application_scene,
    payload.advantages,
    payload.problem
  ].some((value) => String(value || "").trim());
}

Page({
  data: {
    matchMode: "ai",
    loading: false
  },

  chooseMode(event) {
    this.setData({ matchMode: event.currentTarget.dataset.mode || "ai" });
  },

  submitForm(event) {
    const payload = {
      ...event.detail.value,
      match_mode: this.data.matchMode,
      client_source: "微信小程序"
    };
    if (!String(payload.name || "").trim() || !String(payload.phone || "").trim() || !String(payload.company || "").trim()) {
      wx.showToast({ title: "姓名、手机号、单位必填", icon: "none" });
      return;
    }
    if (!hasUsefulContent(payload)) {
      wx.showToast({ title: "请至少填写一项成果信息", icon: "none" });
      return;
    }
    if (!String(payload.title || "").trim()) {
      wx.showToast({ title: "请填写成果名称", icon: "none" });
      return;
    }
    const fullText = String(payload.achievement_text || "").trim();
    if (fullText.length < 50 && !String(payload.summary || payload.technical_route || "").trim()) {
      wx.showToast({ title: "请粘贴较完整的成果材料", icon: "none" });
      return;
    }

    const app = getApp();
    app.globalData.matchMode = this.data.matchMode;
    app.globalData.submission = payload;
    this.setData({ loading: true });
    wx.showLoading({
      title: this.data.matchMode === "quick" ? "快速匹配中" : "AI拆解成果中",
      mask: true
    });
    const progressTimer = this.data.matchMode === "ai"
      ? setTimeout(() => {
          wx.showLoading({ title: "正在生成画像", mask: true });
        }, 10000)
      : null;

    const request = this.data.matchMode === "ai"
      ? api.analyzeAchievement(payload).then((analysis) => {
          app.globalData.capabilityProfile = analysis.capability_profile || {};
          wx.showLoading({ title: "正在匹配需求", mask: true });
          return api.matchDemands({
            ...payload,
            capability_profile: analysis.capability_profile || {},
            structured_tags: analysis.structured_tags || {},
            analysis_source: analysis.source || "local"
          });
        })
      : api.matchDemands(payload);

    request
      .then((response) => {
        app.globalData.submissionId = response.submission_id || "";
        app.globalData.matchMeta = response.ai_meta || {};
        app.globalData.results = response.results || [];
        wx.navigateTo({ url: "/pages/results/results" });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || "匹配失败", icon: "none", duration: 3000 });
      })
      .finally(() => {
        if (progressTimer) clearTimeout(progressTimer);
        wx.hideLoading();
        this.setData({ loading: false });
      });
  }
});
