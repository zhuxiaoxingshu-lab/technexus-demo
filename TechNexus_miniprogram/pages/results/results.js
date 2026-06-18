const { prepareResult } = require("../../utils/format");

function modeMeta(mode) {
  if (mode === "quick") {
    return {
      title: "快速匹配结果",
      copy: "不调用外部 API，先用本地规则筛出大致方向，适合快速初判。"
    };
  }
  return {
    title: "AI 智能匹配结果",
    copy: "调用 DeepSeek API 对候选需求做精排，并给出更细的匹配理由与建议。"
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
  }
});
