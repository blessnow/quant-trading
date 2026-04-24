const api = require('../../utils/api')
const app = getApp()

const TIME_RANGES = [
  { label: '近1周', days: 7 },
  { label: '近1月', days: 30 },
  { label: '近3月', days: 90 },
  { label: '近6月', days: 180 },
  { label: '近1年', days: 365 },
  { label: '近3年', days: 1095 },
]

Page({
  data: {
    summary: {},
    aShareTotal: '500,000',
    aSharePnl: 0,
    usStockTotal: '500,000',
    usStockPnl: 0,
    aShareOpen: false,
    usStockOpen: false,
    strategies: [],
    isMember: false,
    // 收益曲线
    curveMode: 'best',
    timeRanges: TIME_RANGES,
    activeRangeIdx: 2, // 默认近3月
    bestStrategy: null,
    bestLabel: '',
    benchmarkLabel: '',
    curveData: [],
    benchmarkData: [],
  },

  onLoad() {
    this.loadData()
  },

  onShow() {
    this.setData({ isMember: app.globalData.isMember })
    // 盘中自动刷新：每30秒
    if (!this._refreshTimer) {
      this._refreshTimer = setInterval(() => {
        if (this.data.aShareOpen || this.data.usStockOpen) {
          this.refreshRealtime()
        }
      }, 30000)
    }
  },

  onHide() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer)
      this._refreshTimer = null
    }
  },

  onUnload() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer)
      this._refreshTimer = null
    }
  },

  onPullDownRefresh() {
    this.loadData().then(() => wx.stopPullDownRefresh())
  },

  switchCurve(e) {
    this.setData({ curveMode: e.currentTarget.dataset.mode })
    this.loadCurve()
  },

  switchRange(e) {
    this.setData({ activeRangeIdx: Number(e.currentTarget.dataset.idx) })
    this.loadCurve()
  },

  getActiveDays() {
    return TIME_RANGES[this.data.activeRangeIdx].days
  },

  async loadData() {
    try {
      const [summary, marketStatus, strategies] = await Promise.all([
        api.getPortfolioSummary(),
        api.getMarketStatus(),
        api.getStrategies(),
      ])

      const s = summary || {}
      const aShare = s.markets?.A_SHARE || {}
      const usStock = s.markets?.US_STOCK || {}

      this.setData({
        summary: s,
        aShareTotal: this.fmt(aShare.total || 500000),
        aSharePnl: Math.round(aShare.total_pnl || 0),
        usStockTotal: this.fmt(usStock.total || 500000),
        usStockPnl: Math.round(usStock.total_pnl || 0),
        aShareOpen: marketStatus?.a_share?.is_open || false,
        usStockOpen: marketStatus?.us_stock?.is_open || false,
        strategies: (strategies?.strategies || []).map(st => ({
          ...st,
          win_rate_pct: st.performance ? (st.performance.win_rate * 100).toFixed(1) : '0.0',
        })),
      })

      this.loadCurve()
    } catch (e) {
      console.error('加载数据失败', e)
    }
  },

  async refreshRealtime() {
    try {
      const summary = await api.getPortfolioSummary()
      const s = summary || {}
      const aShare = s.markets?.A_SHARE || {}
      const usStock = s.markets?.US_STOCK || {}
      this.setData({
        summary: s,
        aShareTotal: this.fmt(aShare.total || 500000),
        aSharePnl: Math.round(aShare.total_pnl || 0),
        usStockTotal: this.fmt(usStock.total || 500000),
        usStockPnl: Math.round(usStock.total_pnl || 0),
      })
    } catch (e) {
      // 静默失败
    }
  },

  async loadCurve() {
    const mode = this.data.curveMode
    const days = this.getActiveDays()
    try {
      if (mode === 'best') {
        const res = await api.getBestStrategyCurve(days)
        const st = res.strategy
        const bestLabel = st
          ? `${st.display_name} ${st.daily_return_pct >= 0 ? '+' : ''}${Number(st.daily_return_pct).toFixed(2)}%`
          : '暂无数据'
        const bm0 = (res.benchmarks || [])[0]
        const benchmarkLabel = bm0
          ? `${bm0.name} ${(bm0.curve[bm0.curve.length - 1]?.return_pct || 0).toFixed(2)}%`
          : ''
        this.setData({
          bestStrategy: st, bestLabel, benchmarkLabel,
          curveData: res.curve || [],
          benchmarkData: (res.benchmarks || [])[0]?.curve || [],
        })
      } else {
        const curve = await api.getEquityCurve(days, mode)
        const bm = await api.getBenchmarks(mode, days)
        const marketName = mode === 'A_SHARE' ? 'A股组合' : '美股组合'
        const bm0 = (bm.benchmarks || [])[0]
        this.setData({
          bestStrategy: null, bestLabel: marketName,
          benchmarkLabel: bm0 ? bm0.name : '',
          curveData: curve?.curve || [],
          benchmarkData: bm0?.curve || [],
        })
      }
      this.drawChart(this.data.curveData, this.data.benchmarkData)
    } catch (e) {
      console.error('加载曲线失败', e)
    }
  },

  fmt(n) {
    return (n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
  },

  drawChart(curveData, benchmarkData) {
    if (!curveData || curveData.length < 2) return

    const query = wx.createSelectorQuery()
    query.select('#equityChart').fields({ node: true, size: true }).exec((res) => {
      if (!res[0]) return
      const canvas = res[0].node
      const ctx = canvas.getContext('2d')
      const dpr = wx.getWindowInfo().pixelRatio
      canvas.width = res[0].width * dpr
      canvas.height = res[0].height * dpr
      ctx.scale(dpr, dpr)

      const w = res[0].width
      const h = res[0].height
      // 留出左/右/上/下边距，底部多留空间给日期
      const pad = { x: 48, y: 12, bottom: 36 }

      const chartH = h - pad.y - pad.bottom
      const chartW = w - 2 * pad.x

      // 归一化收益率
      const firstVal = curveData[0].total_value
      const points = curveData.map((d, i) => ({
        date: d.date,
        x_ratio: i / Math.max(curveData.length - 1, 1),
        return_pct: firstVal > 0 ? ((d.total_value - firstVal) / firstVal * 100) : 0,
      }))

      let bmPoints = []
      if (benchmarkData && benchmarkData.length >= 2) {
        const bmFirst = benchmarkData[0].return_pct || 0
        bmPoints = benchmarkData.map((d, i) => ({
          date: d.date,
          x_ratio: i / Math.max(benchmarkData.length - 1, 1),
          return_pct: (d.return_pct || 0) - bmFirst,
        }))
      }

      const allVals = [...points.map(p => p.return_pct), ...bmPoints.map(p => p.return_pct)]
      const minY = Math.min(...allVals, 0)
      const maxY = Math.max(...allVals, 0)
      const yRange = (maxY - minY) || 1
      const yPad = yRange * 0.1
      const yMin = minY - yPad
      const yMax = maxY + yPad
      const yTotal = yMax - yMin

      function toX(ratio) { return pad.x + ratio * chartW }
      function toY(val) { return pad.y + (1 - (val - yMin) / yTotal) * chartH }

      ctx.clearRect(0, 0, w, h)

      // Y轴网格线 + 标签
      ctx.textAlign = 'right'
      ctx.textBaseline = 'middle'
      ctx.font = '18px sans-serif'
      const yTicks = 4
      for (let i = 0; i <= yTicks; i++) {
        const val = yMin + (i / yTicks) * yTotal
        const y = toY(val)
        ctx.strokeStyle = '#f0f0f0'
        ctx.lineWidth = 0.5
        ctx.beginPath()
        ctx.moveTo(pad.x, y)
        ctx.lineTo(w - pad.x, y)
        ctx.stroke()
        ctx.fillStyle = '#aaa'
        ctx.fillText(val.toFixed(1) + '%', pad.x - 4, y)
      }

      // 零线
      const zeroY = toY(0)
      ctx.strokeStyle = '#ccc'
      ctx.lineWidth = 0.8
      ctx.beginPath()
      ctx.moveTo(pad.x, zeroY)
      ctx.lineTo(w - pad.x, zeroY)
      ctx.stroke()

      // X轴日期标签 — 最多显示5个
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = '#aaa'
      ctx.font = '16px sans-serif'
      const totalPts = curveData.length
      const xTickCount = Math.min(5, totalPts)
      for (let i = 0; i < xTickCount; i++) {
        const idx = Math.round(i * (totalPts - 1) / Math.max(xTickCount - 1, 1))
        const dateStr = (curveData[idx].date || '').slice(5) // MM-DD
        const x = toX(idx / Math.max(totalPts - 1, 1))
        ctx.fillText(dateStr, x, h - pad.bottom + 8)
      }

      // 策略收益线
      ctx.beginPath()
      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 2
      points.forEach((p, i) => {
        const x = toX(p.x_ratio)
        const y = toY(p.return_pct)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.stroke()

      // 基准虚线
      if (bmPoints.length >= 2) {
        ctx.beginPath()
        ctx.strokeStyle = '#999'
        ctx.lineWidth = 1.5
        ctx.setLineDash([6, 4])
        bmPoints.forEach((p, i) => {
          const x = toX(p.x_ratio)
          const y = toY(p.return_pct)
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
        })
        ctx.stroke()
        ctx.setLineDash([])
      }
    })
  },

  goMembership() {
    wx.navigateTo({ url: '/pages/membership/membership' })
  },

  goStrategyDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/strategy-detail/strategy-detail?id=${id}` })
  }
})
