const { prepareResult } = require("../../utils/format");

Page({
  data: {
    results: [],
    matchMode: "ai"
  },

  onShow() {
    const app = getApp();
    const results = (app.globalData.results || []).map((item, index) => prepareResult(item, index));
    this.setData({
      results,
      matchMode: app.globalData.matchMode || "ai"
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
