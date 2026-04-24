const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    isMember: false,
    strategies: [],
    rankings: [],
    strategyMeta: {
      LimitUpPredictor: '14:40扫描接近涨停股，多因子评分选最佳',
      MultiFactorDaily: '资金流入+聪明钱+量价背离，每日盘前选股',
      EventArbitrage: '监控新闻事件，LLM分析生成交易信号',
      MomentumBreakout: '20日新高+放量突破，5日最大持有',
      MeanReversion: 'RSI超卖+Bollinger下轨反弹',
      GapScanner: '隔夜跳空>3%的回补交易',
    },
    strategySchedule: {
      LimitUpPredictor: '调度: 14:40 CST',
      MultiFactorDaily: '调度: 09:00 CST',
      EventArbitrage: '调度: 每30分钟',
      MomentumBreakout: '调度: 09:45 ET',
      MeanReversion: '调度: 12:00 ET',
      GapScanner: '调度: 09:35 ET',
    }
  },

  onShow() {
    this.setData({ isMember: app.globalData.isMember })
    if (app.globalData.isMember) this.loadData()
  },

  async loadData() {
    const [strategies, ranking] = await Promise.all([
      api.getStrategies(),
      api.getStrategyRanking(),
    ])
    const rawStrategies = strategies?.strategies || []
    const rawRankings = ranking?.rankings || []
    this.setData({
      strategies: rawStrategies.map(s => ({
        ...s,
        win_rate_pct: s.performance ? (s.performance.win_rate * 100).toFixed(1) : '0.0',
        sharpe_str: s.performance && s.performance.sharpe_ratio != null ? s.performance.sharpe_ratio.toFixed(2) : '-',
      })),
      rankings: rawRankings.map(r => ({
        ...r,
        win_rate_pct: r.win_rate != null ? (r.win_rate * 100).toFixed(0) : '0',
        market: r.market || 'A_SHARE',
      })),
    })
  },

  goMembership() {
    wx.navigateTo({ url: '/pages/membership/membership' })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/strategy-detail/strategy-detail?id=${id}` })
  }
})
