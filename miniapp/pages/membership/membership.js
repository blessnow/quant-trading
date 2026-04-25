const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    plan: 'yearly',
    paying: false,
    memberExpireAt: ''
  },

  onLoad() {
    // 检查会员状态
    this.checkMemberStatus()
  },

  async checkMemberStatus() {
    try {
      const profile = await api.getUserProfile()
      if (profile.is_member) {
        this.setData({ memberExpireAt: profile.member_expire_at })
        app.globalData.isMember = true
        app.globalData.memberExpireAt = profile.member_expire_at
      }
    } catch (e) {
      console.error('获取用户信息失败', e)
    }
  },

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
        wx.showLoading({ title: '激活会员...', mask: true })
        const result = await api.confirmTestOrder()
        wx.hideLoading()

        if (result.success) {
          app.globalData.isMember = true
          app.globalData.memberExpireAt = result.member_expire_at
          wx.setStorageSync('isMember', 'true')
          wx.setStorageSync('memberExpireAt', result.member_expire_at)

          wx.showModal({
            title: '支付成功',
            content: `会员已激活\n有效期至: ${result.member_expire_at}`,
            showCancel: false,
            success: () => {
              wx.switchTab({ url: '/pages/index/index' })
            }
          })
        }
      } else if (order.pay_params) {
        // 正式模式：调用微信支付
        wx.requestPayment({
          ...order.pay_params,
          success: async () => {
            wx.showLoading({ title: '确认支付...', mask: true })

            // 调用后端确认支付状态（支付回调可能延迟）
            try {
              const status = await api.checkPaymentStatus(order.order_no)
              wx.hideLoading()

              if (status.status === 'paid') {
                app.globalData.isMember = true
                app.globalData.memberExpireAt = status.member_expire_at
                wx.setStorageSync('isMember', 'true')
                wx.setStorageSync('memberExpireAt', status.member_expire_at)

                wx.showModal({
                  title: '支付成功',
                  content: `会员已激活\n有效期至: ${status.member_expire_at}`,
                  showCancel: false,
                  success: () => {
                    wx.switchTab({ url: '/pages/index/index' })
                  }
                })
              } else {
                // 支付成功但状态未更新，稍后刷新
                wx.showModal({
                  title: '支付成功',
                  content: '会员正在激活中，请稍后刷新查看',
                  showCancel: false,
                  success: () => {
                    wx.switchTab({ url: '/pages/index/index' })
                  }
                })
              }
            } catch (e) {
              wx.hideLoading()
              wx.showModal({
                title: '支付成功',
                content: '会员正在激活中，请稍后刷新查看',
                showCancel: false,
                success: () => {
                  wx.switchTab({ url: '/pages/index/index' })
                }
              })
            }
          },
          fail: (err) => {
            if (err.errMsg && err.errMsg.includes('cancel')) {
              wx.showToast({ title: '已取消支付', icon: 'none' })
            } else {
              wx.showModal({
                title: '支付失败',
                content: '请重试或联系客服',
                confirmText: '重试',
                success: (res) => {
                  if (res.confirm) {
                    this.handlePay()
                  }
                }
              })
            }
          }
        })
      }
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    } finally {
      this.setData({ paying: false })
    }
  }
})
