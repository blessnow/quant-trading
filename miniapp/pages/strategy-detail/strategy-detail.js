const api = require('../../utils/api')

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
    strategy: null,
    curveData: [],
    benchmarkData: [],
    benchmarkName: '',
    trades: [],
    positions: [],
    timeRanges: TIME_RANGES,
    activeRangeIdx: 2,
    strategyMeta: {
      LimitUpPredictor: '14:40扫描接近涨停股，多因子评分选最佳',
      MultiFactorDaily: '资金流入+聪明钱+量价背离，每日盘前选股',
      EventArbitrage: '监控新闻事件，LLM分析生成交易信号',
      MomentumBreakout: '20日新高+放量突破，5日最大持有',
      MeanReversion: 'RSI超卖+Bollinger下轨反弹',
      GapScanner: '隔夜跳空>3%的回补交易',
    },
  },

  onLoad(options) {
    this._strategyId = options.id
    if (this._strategyId) this.loadData()
  },

  switchRange(e) {
    this.setData({ activeRangeIdx: Number(e.currentTarget.dataset.idx) })
    this.loadCurveAndBenchmarks()
  },

  async loadData() {
    try {
      const id = this._strategyId
      const [strategies, tradesRes, posRes] = await Promise.all([
        api.getStrategies(),
        api.getTrades(20),
        api.getPositions(),
      ])

      const strategy = (strategies?.strategies || []).find(s => s.id === Number(id))
      if (!strategy) return

      if (strategy.performance) {
        strategy.win_rate_pct = (strategy.performance.win_rate * 100).toFixed(1)
        strategy.sharpe_str = strategy.performance.sharpe_ratio != null
          ? strategy.performance.sharpe_ratio.toFixed(2) : '-'
        strategy.max_dd_str = (strategy.performance.max_drawdown_pct
          ? (strategy.performance.max_drawdown_pct * 100).toFixed(1) : '0.0')
        const pnl = Number(strategy.performance.total_pnl) || 0
        const absPnl = Math.abs(pnl)
        const sign = pnl > 0 ? '+' : ''
        if (absPnl >= 10000) {
          strategy.total_pnl_str = sign + (pnl / 10000).toFixed(1) + '万'
        } else if (absPnl >= 100) {
          strategy.total_pnl_str = sign + Math.round(pnl)
        } else {
          strategy.total_pnl_str = sign + pnl.toFixed(1)
        }
        strategy.total_pnl_class = pnl > 0 ? 'pnl-up' : pnl < 0 ? 'pnl-down' : ''
      }

      // 策略持仓
      const allPositions = posRes?.positions || []
      const positions = allPositions.filter(p => p.strategy_id === Number(id))

      this.setData({
        strategy,
        trades: (tradesRes?.trades || []).filter(t => t.strategy_id === Number(id)).map(t => ({
          ...t,
          executed_at_slice: (t.executed_at || '').slice(5, 16),
          price: t.price?.toFixed(2),
          pnl: t.pnl != null ? Math.round(t.pnl) : null,
        })),
        positions,
      })

      await this.loadCurveAndBenchmarks()
    } catch (e) {
      console.error('加载策略详情失败', e)
    }
  },

  async loadCurveAndBenchmarks() {
    const id = this._strategyId
    const days = TIME_RANGES[this.data.activeRangeIdx].days
    const strategy = this.data.strategy

    const [curveRes, bmRes] = await Promise.all([
      api.getStrategyCurve(id, days),
      strategy?.market ? api.getBenchmarks(strategy.market, days) : Promise.resolve(null),
    ])

    const bm0 = (bmRes?.benchmarks || [])[0]
    this.setData({
      curveData: curveRes?.curve || [],
      benchmarkData: bm0?.curve || [],
      benchmarkName: bm0?.name || '',
    })
    this.drawChart()
  },

  drawChart() {
    const { curveData, benchmarkData } = this.data
    if (!curveData || curveData.length < 2) return

    const query = wx.createSelectorQuery()
    query.select('#detailChart').fields({ node: true, size: true }).exec((res) => {
      if (!res[0]) return
      const canvas = res[0].node
      const ctx = canvas.getContext('2d')
      const dpr = wx.getWindowInfo().pixelRatio
      canvas.width = res[0].width * dpr
      canvas.height = res[0].height * dpr
      ctx.scale(dpr, dpr)

      const w = res[0].width
      const h = res[0].height
      const pad = { x: 48, y: 12, bottom: 36 }
      const chartH = h - pad.y - pad.bottom
      const chartW = w - 2 * pad.x

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
      for (let i = 0; i <= 4; i++) {
        const val = yMin + (i / 4) * yTotal
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
      ctx.strokeStyle = '#ccc'
      ctx.lineWidth = 0.8
      ctx.beginPath()
      ctx.moveTo(pad.x, toY(0))
      ctx.lineTo(w - pad.x, toY(0))
      ctx.stroke()

      // X轴日期
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = '#aaa'
      ctx.font = '16px sans-serif'
      const totalPts = curveData.length
      const xTickCount = Math.min(5, totalPts)
      for (let i = 0; i < xTickCount; i++) {
        const idx = Math.round(i * (totalPts - 1) / Math.max(xTickCount - 1, 1))
        const dateStr = (curveData[idx].date || '').slice(5)
        ctx.fillText(dateStr, toX(idx / Math.max(totalPts - 1, 1)), h - pad.bottom + 8)
      }

      // 策略线
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
})
