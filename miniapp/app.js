App({
  globalData: {
    token: '',
    isMember: false,
    memberExpireAt: '',
    userId: null,
    apiBase: 'http://10.209.21.39:8000'
  },

  onLaunch() {
    // 检查本地登录态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.globalData.isMember = wx.getStorageSync('isMember') === 'true'
      this.globalData.memberExpireAt = wx.getStorageSync('memberExpireAt')
    }
  },

  login() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => {
          if (res.code) {
            wx.request({
              url: `${this.globalData.apiBase}/api/wechat/login`,
              method: 'POST',
              data: { code: res.code },
              success: (resp) => {
                if (resp.data.token) {
                  this.globalData.token = resp.data.token
                  this.globalData.isMember = resp.data.is_member
                  this.globalData.memberExpireAt = resp.data.member_expire_at
                  wx.setStorageSync('token', resp.data.token)
                  wx.setStorageSync('isMember', resp.data.is_member ? 'true' : 'false')
                  wx.setStorageSync('memberExpireAt', resp.data.member_expire_at || '')
                  resolve(resp.data)
                } else {
                  reject(new Error('登录失败'))
                }
              },
              fail: reject
            })
          }
        },
        fail: reject
      })
    })
  }
})
