const api = require("../../utils/api");

Page({
  data: {
    stats: {
      demand_count: "-",
      ai_mode: "-"
    },
    avatar: "/assets/wechat-official-avatar.jpg",
    qrcode: "/assets/wechat-official-qrcode.jpg",
    heroImage: "/assets/jiangsu_nanjing_cbd.jpg",
    labImage: "/assets/suzhou_lab_cleanroom.jpg",
    factoryImage: "/assets/jiangsu_industrial_workshop.jpg",
    previewResults: [
      {
        name: "半导体用高导热有机硅热界面管理材料",
        tags: ["新材料", "半导体封装", "江苏省 / 无锡市"],
        score: 92,
        level: "excellent"
      },
      {
        name: "高性能石墨烯-石墨研发在能源器件中应用及产业化",
        tags: ["新能源", "能源器件", "江苏省 / 盐城市"],
        score: 86,
        level: "high"
      }
    ],
    processSteps: [
      {
        index: "1",
        title: "提交成果",
        copy: "填写成果摘要、应用场景、成熟度等核心信息。"
      },
      {
        index: "2",
        title: "智能分析",
        copy: "系统抽取技术领域、产业方向和关键要点。"
      },
      {
        index: "3",
        title: "提交意向",
        copy: "确认服务协议后，把合作意向送入后台。"
      },
      {
        index: "4",
        title: "人工撮合",
        copy: "平台审核、联系双方、安排沟通并跟进。"
      },
      {
        index: "5",
        title: "查询进度",
        copy: "用查询码随时查看当前推进状态。"
      }
    ]
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

  goDemands() {
    wx.navigateTo({ url: "/pages/demands/demands" });
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
