const { prepareResult } = require("../../utils/format");

function modeMeta(mode) {
  if (mode === "quick") {
    return {
      title: "快速匹配结果",
      copy: "不调用外部 API，按技术标的、核心问题、技术路线和指标约束完成快速初判。"
    };
  }
  return {
    title: "AI 智能匹配结果",
    copy: "先生成成果能力画像，再调用 DeepSeek 对需求技术任务进行可行性精排。"
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
    this.setData({
      results,
      matchMode,
      modeTitle: meta.title,
      modeCopy: meta.copy,
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
