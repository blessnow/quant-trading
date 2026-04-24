const api = require('../../utils/api')

Page({
  data: { article: null },

  onLoad(options) {
    if (options.id) this.loadArticle(options.id)
  },

  async loadArticle(id) {
    try {
      const article = await api.getArticle(id)
      article.created_at_slice = (article.created_at || '').slice(0, 10)
      this.setData({ article })
    } catch (e) {
      console.error('加载文章失败', e)
    }
  },
})
