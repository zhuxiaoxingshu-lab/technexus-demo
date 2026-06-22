const api = require("../../utils/api");

const PAGE_SIZE = 20;

Page({
  data: {
    demands: [],
    total: 0,
    totalText: "-",
    loading: false,
    error: "",
    hasMore: true
  },

  onLoad() {
    this.loadDemands(true);
  },

  onPullDownRefresh() {
    this.loadDemands(true).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    this.loadDemands(false);
  },

  loadMore() {
    this.loadDemands(false);
  },

  loadDemands(reset) {
    if (this.data.loading) return Promise.resolve();

    const offset = reset ? 0 : this.data.demands.length;
    if (!reset && !this.data.hasMore) return Promise.resolve();

    this.setData({ loading: true, error: reset ? "" : this.data.error });
    return api.getPublicDemands(offset, PAGE_SIZE)
      .then((response) => {
        const incoming = Array.isArray(response.items) ? response.items : [];
        const demands = reset ? incoming : this.data.demands.concat(incoming);
        const total = Number(response.total || 0);
        this.setData({
          demands,
          total,
          totalText: total.toLocaleString("zh-CN"),
          hasMore: demands.length < total,
          error: ""
        });
      })
      .catch((error) => {
        this.setData({
          error: error.message || "需求加载失败，请稍后重试。"
        });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },

  retry() {
    this.loadDemands(true);
  },

  goSubmit() {
    wx.navigateTo({ url: "/pages/submit/submit" });
  }
});
