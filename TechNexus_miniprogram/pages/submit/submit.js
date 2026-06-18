const api = require("../../utils/api");

function hasUsefulContent(payload) {
  return [
    payload.title,
    payload.tech_field,
    payload.summary,
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

    const app = getApp();
    app.globalData.matchMode = this.data.matchMode;
    app.globalData.submission = payload;
    this.setData({ loading: true });
    wx.showLoading({
      title: this.data.matchMode === "quick" ? "快速匹配中" : "AI匹配中",
      mask: true
    });

    api.matchDemands(payload)
      .then((response) => {
        app.globalData.submissionId = response.submission_id || "";
        app.globalData.results = response.results || [];
        wx.navigateTo({ url: "/pages/results/results" });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || "匹配失败", icon: "none", duration: 3000 });
      })
      .finally(() => {
        wx.hideLoading();
        this.setData({ loading: false });
      });
  }
});
