const { prepareResult } = require("../../utils/format");

function modeMeta(mode) {
  if (mode === "quick") {
    return {
      title: "快速匹配结果",
      copy: "不调用外部 API，按技术标的、核心问题、所需功能、技术路线和指标约束完成快速初判。"
    };
  }
  return {
    title: "AI 智能匹配结果",
    copy: "读取预拆解的需求画像完成候选召回，再由 DeepSeek 复核前 6 条需求。"
  };
}

Page({
  data: {
    results: [],
    matchMode: "ai",
    modeTitle: "AI 智能匹配结果",
    modeCopy: "",
    resultCountText: "0"
  },

  onShow() {
    const app = getApp();
    const results = (app.globalData.results || []).map((item, index) => prepareResult(item, index));
    const matchMode = app.globalData.matchMode || "ai";
    const meta = modeMeta(matchMode);
    const matchMeta = app.globalData.matchMeta || {};
    this.setData({
      results,
      matchMode,
      modeTitle: meta.title,
      modeCopy: matchMeta.message || meta.copy,
      resultCountText: String(results.length || 0)
    });
  },

  goSubmit() {
    wx.navigateBack({
      fail() {
        wx.navigateTo({ url: "/pages/submit/submit" });
      }
    });
  },

  chooseIntent(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const app = getApp();
    app.globalData.selectedResult = app.globalData.results[index];
    wx.navigateTo({ url: "/pages/intent/intent" });
  },

  toggleDemandDetail(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const item = this.data.results[index];
    if (!item) return;
    this.setData({
      [`results[${index}].detail_expanded`]: !item.detail_expanded
    });
  }
});
