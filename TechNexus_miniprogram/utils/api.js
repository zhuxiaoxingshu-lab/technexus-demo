const API_BASE = "https://technexus-demo.onrender.com";

function request(path, options = {}) {
  const app = getApp();
  const base = app && app.globalData && app.globalData.apiBase ? app.globalData.apiBase : API_BASE;
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${base}${path}`,
      method: options.method || "GET",
      data: options.data || {},
      timeout: options.timeout || 60000,
      header: {
        "content-type": "application/json"
      },
      success(res) {
        const data = res.data || {};
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(data);
          return;
        }
        reject(new Error(data.message || `请求失败：${res.statusCode}`));
      },
      fail(error) {
        const message = error.errMsg || "网络请求失败";
        if (message.includes("url not in domain list")) {
          reject(new Error("服务器域名未加入小程序 request 合法域名，请先在微信公众平台配置后台域名。"));
          return;
        }
        reject(new Error(message));
      }
    });
  });
}

function getStats() {
  return request("/api/stats");
}

function getPublicDemands(offset = 0, limit = 20) {
  return request(`/api/public/demands?offset=${offset}&limit=${limit}`);
}

function matchDemands(payload) {
  return request("/api/match", {
    method: "POST",
    data: payload,
    timeout: 90000
  });
}

function submitIntent(payload) {
  return request("/api/intents", {
    method: "POST",
    data: payload
  });
}

function queryProgress(queryCode) {
  return request("/api/progress/query", {
    method: "POST",
    data: {
      query_code: queryCode
    }
  });
}

module.exports = {
  getPublicDemands,
  getStats,
  matchDemands,
  queryProgress,
  submitIntent
};
