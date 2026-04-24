const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    articles: [],
    categories: [
      { key: '', label: '全部' },
      { key: 'market', label: '市场热点' },
      { key: 'opinion', label: '原创观点' },
      { key: 'strategy', label: '策略分析' },
      { key: 'tutorial', label: '量化教程' },
    ],
    activeCategory: '',
  },

  onShow() {
    this.loadArticles()
  },

  switchCategory(e) {
    this.setData({ activeCategory: e.currentTarget.dataset.key })
    this.loadArticles()
  },

  async loadArticles() {
    try {
      const cat = this.data.activeCategory || undefined
      const res = await api.getArticles(cat)
      this.setData({ articles: res?.articles || [] })
    } catch (e) {
      console.error('加载文章失败', e)
    }
  },

  goArticle(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/article-detail/article-detail?id=${id}` })
  },
})
