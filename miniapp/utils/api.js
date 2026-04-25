const app = getApp()

function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBase}${url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Authorization': `Bearer ${app.globalData.token}`,
        'Content-Type': 'application/json',
        ...options.header
      },
      success: (resp) => {
        if (resp.statusCode === 401) {
          // 登录过期，重新登录
          app.login().then(() => {
            request(url, options).then(resolve).catch(reject)
          })
          return
        }
        resolve(resp.data)
      },
      fail: reject
    })
  })
}

module.exports = {
  get: (url) => request(url),
  post: (url, data) => request(url, { method: 'POST', data }),
  put: (url, data) => request(url, { method: 'PUT', data }),

  // 业务API
  getPortfolioSummary: () => request('/api/portfolio/summary'),
  getEquityCurve: (days = 90, market = '') => request(`/api/portfolio/equity-curve?days=${days}${market ? '&market=' + market : ''}`),
  getPositions: (market) => request(`/api/portfolio/positions${market ? '?market=' + market : ''}`),
  getStrategies: () => request('/api/strategies'),
  getStrategyRanking: (period = 'month') => request(`/api/strategies/ranking?period=${period}`),
  toggleStrategy: (id, active) => request(`/api/strategies/${id}/toggle`, { method: 'PUT', data: { is_active: active } }),
  getTrades: (limit = 100) => request(`/api/trades?limit=${limit}`),
  getMarketStatus: () => request('/api/market/status'),
  getUserProfile: () => request('/api/wechat/profile'),
  createOrder: (plan) => request('/api/pay/create-order', { method: 'POST', data: { plan } }),
  confirmTestOrder: () => request('/api/pay/confirm-test', { method: 'POST' }),
  checkPaymentStatus: (orderNo) => request(`/api/pay/check-status?order_no=${orderNo}`),
  getOrders: () => request('/api/pay/orders'),

  // 收益曲线（策略级+基准）
  getBestStrategyCurve: (days = 90) => request(`/api/portfolio/best-strategy?days=${days}`),
  getStrategyCurve: (id, days = 90) => request(`/api/portfolio/equity-curve?strategy_id=${id}&days=${days}`),
  getBenchmarks: (market, days = 90) => request(`/api/portfolio/benchmarks?market=${market}&days=${days}`),

  // 文章
  getArticles: (category, limit = 20) => request(`/api/articles${category ? '?category=' + category : '&limit=' + limit}`),
  getArticle: (id) => request(`/api/articles/${id}`),
}
