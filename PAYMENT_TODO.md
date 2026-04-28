# 支付 & 短信真实接入任务

## 已完成

- [x] 阿里云短信 SDK 已安装 (`alibabacloud-dysmsapi20170525`)
- [x] `backend/services/sms.py` 已创建 — 阿里云短信发送 + mock模式
- [x] `backend/api/phone_auth.py` 已重构 — 使用 `services.sms` 统一发送/验证
- [x] `backend/wechat/pay.py` — 微信支付 **APIv3**（Native / JSAPI、回调验签+AES-GCM 解密、平台证书拉取缓存）；`WX_MCH_ID` 为空仍为 mock
- [x] `backend/config.py` — `WX_MCH_SERIAL_NO`、`WX_API_V3_KEY`、`WX_MCH_PRIVATE_KEY_PATH`
- [x] `backend/api/wechat_pay.py` — 回调改为 V3 JSON 应答；订单查询修正 `status` 列
- [x] `backend/requirements.txt` — `cryptography`、`alibabacloud-dysmsapi20170525`
- [x] `backend/.env.example` — 模板变量
- [x] `frontend/app/membership/page.tsx` — 生产构建不展示模拟支付按钮；真实支付依赖轮询 `checkPayment`；开发环境 mock 时保留「本地开发：模拟确认支付」

## 商户侧配置（需自行在微信商户平台完成）

1. 登录 https://pay.weixin.qq.com 注册商户号
2. 「API安全」下载商户 API 证书 → `apiclient_key.pem` 与证书序列号
3. 设置 **APIv3 密钥**（32 位）
4. 绑定 APPID（小程序/公众号）
5. `.env` 填写：`WX_MCH_ID`、`WX_MCH_SERIAL_NO`、`WX_API_V3_KEY`、`WX_MCH_PRIVATE_KEY_PATH`、`WX_PAY_NOTIFY_URL`（须 HTTPS 公网可达）

## 关键文件路径

| 文件 | 说明 |
|------|------|
| `backend/wechat/pay.py` | 微信支付 V3 |
| `backend/api/wechat_pay.py` | 支付 API 路由 |
| `backend/services/sms.py` | 短信服务 |
| `backend/config.py` | 配置项 |
| `frontend/app/membership/page.tsx` | 会员购买页 |
