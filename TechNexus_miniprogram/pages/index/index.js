const api = require("../../utils/api");

Page({
  data: {
    stats: {
      demand_count: "-",
      ai_mode: "-"
    },
    avatar: "/assets/wechat-official-avatar.jpg",
    qrcode: "/assets/wechat-official-qrcode.jpg"
  },

  onLoad() {
    this.loadStats();
  },

  loadStats() {
    api.getStats()
      .then((stats) => {
        this.setData({
          stats: {
            demand_count: Number(stats.demand_count || 0).toLocaleString("zh-CN"),
            ai_mode: stats.ai_mode || "-"
          }
        });
      })
      .catch(() => {
        this.setData({
          stats: {
            demand_count: "-",
            ai_mode: "待连接"
          }
        });
      });
  },

  goSubmit() {
    wx.navigateTo({ url: "/pages/submit/submit" });
  },

  goProgress() {
    wx.navigateTo({ url: "/pages/progress/progress" });
  },

  previewQr() {
    wx.previewImage({
      urls: [this.data.qrcode],
      current: this.data.qrcode
    });
  }
});
