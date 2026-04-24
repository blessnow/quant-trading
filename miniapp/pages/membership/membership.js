const api = require('../../utils/api')
const app = getApp()

Page({
  data: { plan: 'yearly', paying: false },

  selectPlan(e) {
    this.setData({ plan: e.currentTarget.dataset.plan })
  },

  async handlePay() {
    if (this.data.paying) return
    this.setData({ paying: true })

    try {
      const order = await api.createOrder(this.data.plan)

      if (order.test_mode) {
        // 测试模式：直接确认
        const result = await api.confirmTestOrder()
        if (result.success) {
          app.globalData.isMember = true
          app.globalData.memberExpireAt = result.member_expire_at
          wx.setStorageSync('isMember', 'true')
          wx.setStorageSync('memberExpireAt', result.member_expire_at)

          wx.showToast({ title: '会员已激活', icon: 'success' })
          setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 1500)
        }
      } else if (order.pay_params) {
        // 正式模式：调用微信支付
        wx.requestPayment({
          ...order.pay_params,
          success: () => {
            app.globalData.isMember = true
            wx.setStorageSync('isMember', 'true')
            wx.showToast({ title: '支付成功', icon: 'success' })
            setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 1500)
          },
          fail: () => wx.showToast({ title: '取消支付', icon: 'none' })
        })
      }
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    } finally {
      this.setData({ paying: false })
    }
  }
})
