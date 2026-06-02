const api = require("../../utils/api");
const { prepareResult } = require("../../utils/format");

Page({
  data: {
    selected: null,
    agreement: false,
    loading: false,
    success: false,
    queryCode: "",
    qrcode: "/assets/wechat-official-qrcode.jpg"
  },

  onShow() {
    const selected = getApp().globalData.selectedResult;
    this.setData({
      selected: selected ? prepareResult(selected, 0) : null
    });
  },

  agreementChange(event) {
    this.setData({
      agreement: (event.detail.value || []).includes("agree")
    });
  },

  submitForm(event) {
    const app = getApp();
    const form = event.detail.value || {};
    if (!app.globalData.selectedResult) {
      wx.showToast({ title: "请先选择一个匹配需求", icon: "none" });
      return;
    }
    if (!this.data.agreement) {
      wx.showToast({ title: "请先阅读并同意协议", icon: "none" });
      return;
    }
    if (!form.name || !form.phone || !form.company) {
      wx.showToast({ title: "姓名、手机号、单位必填", icon: "none" });
      return;
    }

    const payload = {
      submission_id: app.globalData.submissionId,
      agreement: true,
      contact: {
        name: form.name,
        phone: form.phone,
        company: form.company,
        technology_summary: app.globalData.submission.summary || app.globalData.submission.title || ""
      },
      message: form.message || "",
      extra_note: app.globalData.submission.extra_note || "",
      selected_result: app.globalData.selectedResult
    };

    this.setData({ loading: true });
    wx.showLoading({ title: "提交中", mask: true });
    api.submitIntent(payload)
      .then((response) => {
        const intent = response.intent || {};
        const code = intent.query_code || "";
        app.globalData.lastQueryCode = code;
        this.setData({
          success: true,
          queryCode: code
        });
        wx.showToast({ title: "已提交", icon: "success" });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || "提交失败", icon: "none", duration: 3000 });
      })
      .finally(() => {
        wx.hideLoading();
        this.setData({ loading: false });
      });
  },

  copyCode() {
    if (!this.data.queryCode) return;
    wx.setClipboardData({ data: this.data.queryCode });
  },

  goProgress() {
    const code = this.data.queryCode || "";
    wx.navigateTo({ url: `/pages/progress/progress?code=${encodeURIComponent(code)}` });
  },

  previewQr() {
    wx.previewImage({
      urls: [this.data.qrcode],
      current: this.data.qrcode
    });
  }
});
