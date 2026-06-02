const api = require("../../utils/api");

function prepareProgress(progress) {
  const demand = progress.demand || {};
  return {
    ...progress,
    demand: {
      name: demand.name || "-",
      score_text: demand.score ? `${demand.score}%` : "-"
    },
    progress: progress.progress || []
  };
}

Page({
  data: {
    queryCode: "",
    loading: false,
    progress: null,
    qrcode: "/assets/wechat-official-qrcode.jpg"
  },

  onLoad(options) {
    const code = decodeURIComponent(options.code || getApp().globalData.lastQueryCode || "");
    if (code) {
      this.setData({ queryCode: code });
    }
  },

  inputCode(event) {
    this.setData({ queryCode: event.detail.value });
  },

  query() {
    const code = String(this.data.queryCode || "").trim();
    if (!code) {
      wx.showToast({ title: "请输入查询码", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    wx.showLoading({ title: "查询中", mask: true });
    api.queryProgress(code)
      .then((response) => {
        this.setData({ progress: response.progress ? prepareProgress(response.progress) : null });
      })
      .catch((error) => {
        this.setData({ progress: null });
        wx.showToast({ title: error.message || "未找到查询码", icon: "none", duration: 3000 });
      })
      .finally(() => {
        wx.hideLoading();
        this.setData({ loading: false });
      });
  },

  previewQr() {
    wx.previewImage({
      urls: [this.data.qrcode],
      current: this.data.qrcode
    });
  }
});
