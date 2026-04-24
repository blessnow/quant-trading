const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    isMember: false,
    nickname: '用户',
    memberExpire: '',
  },

  onShow() {
    this.setData({
      isMember: app.globalData.isMember,
      memberExpire: (app.globalData.memberExpireAt || '').slice(0, 10),
    })
    this.loadData()
  },

  async loadData() {
    try {
      const profile = await api.getUserProfile()
      this.setData({
        nickname: profile.nickname || profile.id || '用户',
        isMember: profile.is_member,
        memberExpire: (profile.member_expire_at || '').slice(0, 10),
      })
      app.globalData.isMember = profile.is_member
      wx.setStorageSync('isMember', profile.is_member ? 'true' : 'false')
    } catch (e) {
      // 未登录等
    }
  },

  goMembership() {
    wx.navigateTo({ url: '/pages/membership/membership' })
  }
})
