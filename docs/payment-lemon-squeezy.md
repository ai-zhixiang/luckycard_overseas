# Lucky Card — Lemon Squeezy 支付集成方案

**创建日期：** 2026-05-25  
**状态：** 待实现（等待用户 Lemon Squeezy 开户 + 提供 API Key）

---

## 方案选型

| 候选方案 | 结论 |
|---------|------|
| Stripe 个人 | 需香港银行账户，复杂 |
| PayPal 个人 | 税率自己扛，不省心 |
| USDT 加密 | 用户门槛高 |
| **Lemon Squeezy** | ✅ 个人护照即可，代缴全球税，MoR 模式 |

**最终选择：Lemon Squeezy** — 个人护照验证 + 全球 VAT/GST/Sales Tax 全包。

---

## 定价方案（建议）

| 产品 | 价格 | 内容 |
|------|------|------|
| 100 Credits | $0.99 | 约 10 张贺卡 |
| 500 Credits | $3.99 | 约 50 张贺卡 + 解锁高级诗风 |
| 2000 Credits | $9.99 | 约 200 张 + 全部风格 + 优先队列 |

---

## 技术实现

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/api/payment.py` | 重写 | Lemon Squeezy Checkout + Webhook |
| `app/models.py` | 添加 | `CreditTransaction` 表 |
| `static/forms/card-create.html` | 修改 | 加 Credits 余额显示 + 充值入口 |
| `.env` | 添加 | `LEMON_SQUEEZY_API_KEY` + `LEMON_SQUEEZY_STORE_ID` + `LEMON_SQUEEZY_WEBHOOK_SECRET` |

### 数据流

```
用户点击 "Buy Credits"
    │
    ▼
POST /api/payment/checkout  { product_id, user_id }
    │
    ▼
Lemon Squeezy API → 创建 Checkout
    │
    ▼
返回 checkout_url → 用户跳转 Lemon Squeezy 支付页
    │
    ▼
支付成功 → Lemon Squeezy 回调 Webhook
    │
    ▼
POST /api/payment/webhook  ← Lemon Squeezy
    │
    ▼
验签 → 写入 credit_transactions → 更新用户余额
```

### 新增数据库表

```sql
CREATE TABLE credit_transactions (
    id VARCHAR(12) PRIMARY KEY,
    user_id VARCHAR(12) NOT NULL,
    amount INTEGER NOT NULL,           -- 购买的 credits 数量
    price_cents INTEGER NOT NULL,       -- 支付金额（美分）
    ls_order_id VARCHAR(100),           -- Lemon Squeezy 订单号
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/payment/products` | GET | 返回可用产品列表 |
| `/api/payment/checkout` | POST | 创建 Lemon Squeezy Checkout，返回 URL |
| `/api/payment/webhook` | POST | Lemon Squeezy 回调（验签 + 充值） |
| `/api/payment/credits` | GET | 查询用户 Credits 余额 |

---

## 前置条件

- [ ] 用户在 [lemonsqueezy.com](https://lemonsqueezy.com) 注册 + 护照验证
- [ ] 创建 Store 和产品
- [ ] 获取 API Key → 提供给开发者
- [ ] 设置 Webhook URL → `https://hicard.world/api/payment/webhook`

---

## 实施步骤

1. 用户提供 API Key
2. 写入 `.env`
3. 重写 `app/api/payment.py`（Checkout + Webhook）
4. `models.py` 加 `CreditTransaction`
5. 数据库迁移（建表）
6. 前端加 Credits 显示 + 购买按钮
7. 部署 + 测试沙箱环境
8. 切生产环境
