# GEOHub for Shopify — Phase 0 PoC

把 GEO SEO Hub 的网站 GEO 诊断引擎（八维评分 + 离线可视化报告）包成 Shopify 嵌入式应用的阶段 0 骨架。

## 架构

```
Shopify Admin
  └─ 嵌入式 Remix 应用 (frontend/, 官方模板)
       │  OAuth / session token / App Bridge / Polaris UI
       │  服务端转发（X-App-API-Key 共享密钥，密钥不出浏览器）
       ├─ GET/POST  /api/jobs/*          ─┐
       ├─ GET       /api/jobs/:id/report  │ HTTP
       └─ POST      /webhooks/*_redact    │ (本地: localhost:8000)
                                            ▼
       FastAPI 后端 (backend/)
         ├─ JobManager: 线程池 + 每任务独立 runs root
         │    └─ geo_seo_hub.site_diagnose()  ← 评分引擎原样复用，零改动
         ├─ Shopify session token 验证 (JWT HS256)
         ├─ GDPR 强制 webhooks（直收或经 Remix 转发，HMAC/服务密钥双通道）
         └─ data/jobs/*.json + data/runs/<job_id>/<run_id>/…
```

关键设计决策：

- **每个任务独立 runs root**（`data/runs/<job_id>/`），从根上规避了库的确定性 run_id 在并发/多租户下的目录冲突，核心库零改动。
- **报告渲染零改动**：`report.html` 由库直接生成（本地打包 ECharts、无 CDN），FastAPI 用 `FileResponse` 原样返回，Remix iframe 展示。
- **双通道 webhook**：Shopify → Remix（HMAC 验证）→ 后端（服务密钥）；未来也可让 Shopify 直连后端（后端自带 HMAC 验证）。`shop/redact` 真正删除该店铺全部任务与报告。
- **认证双通道**：浏览器侧 Shopify session token（后端可独立验证）；服务侧共享密钥。`GEOHUB_APP_DEV_MODE=1` 时放开认证供本地开发。

## 后端

要求 Python 3.11–3.14（本机用 Homebrew 的 python3.12）。

```bash
cd shopify-app/backend
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -e ../.. '.[dev]'   # geo-seo-hub（仓库根）+ 后端自身

# 环境变量（本地开发）
export GEOHUB_APP_DEV_MODE=1        # 本地放开 API 认证
# 生产/联调时改为：
#   SHOPIFY_API_KEY / SHOPIFY_API_SECRET   —— 与 frontend/.env 相同的值
#   GEOHUB_APP_API_KEY                     —— openssl rand -hex 32，前后端一致

.venv/bin/python -m uvicorn app.main:app --port 8000
```

- 本地预览（无需 Shopify）：打开 http://localhost:8000/demo ，勾选 "Offline demo data" 提交即可全链路体验（离线 fixture，不抓真实网站）。
- 真实诊断：填店铺前台 URL（如 `https://your-store.myshopify.com`），不勾 demo。JS 渲染壳的站点会尝试 Playwright 浏览器渲染——需要 `pip install -e '../../.[render]'` 并安装 Chromium（未装时自动降级为 HTTP 模式并在报告中记录证据缺口）。
- 测试（完全离线）：`.venv/bin/python -m pytest` — 22 个用例覆盖 jobs API、认证、HMAC/GDPR webhooks、shop/redact 数据删除。

## 前端

官方 [Shopify Remix app 模板](https://github.com/Shopify/shopify-app-template-remix)（React Router 7 + Polaris + App Bridge + Prisma/SQLite）。

```bash
cd shopify-app/frontend
cp .env.example .env      # 填 GEOHUB_APP_API_KEY
npm install               # .npmrc 已设 legacy-peer-deps + 项目本地 cache
npx prisma generate       # 若 shopify app dev 未自动执行
npm run dev               # 即 shopify app dev，首次会引导创建/关联 Partner 应用
```

`shopify app dev` 写入 `.env` 的 `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET` 需同步给后端（session token 验证与 webhook HMAC 都要用同一个 secret）。

已完成的改造：

- `app/routes/app._index.tsx`：GEO 诊断仪表盘（默认目标 = 店铺主域名，来自 GraphQL Admin API；任务历史；八维分数 + AI 爬虫徽章；报告 iframe；运行中轮询）。
- `app/routes/api.jobs.$jobId(.report).tsx`：带会话认证的资源路由，代理后端。
- `app/routes/webhooks.customers.*.tsx` / `webhooks.shop.redact.tsx`：GDPR 合规 webhook 验证并转发后端（`shopify.app.toml` 已启用三个 compliance 订阅）。
- scopes 收敛为 `read_products`（阶段 0 只读店铺元信息）。

## 距离上架还差什么（阶段 1 清单）

- [ ] Billing API 套餐（免费起步也建议先接，避免二次过审改动）
- [ ] 生产化存储：runs 产物同步对象存储 + Postgres 记录任务/趋势（现为本地 FS）
- [ ] 任务队列 + Playwright worker 池（现线程池，浏览器渲染需进程隔离与硬超时）
- [ ] Shopify 数据深化：产品/集合/页面的 Admin API 信号（比爬取更权威的评分输入）
- [ ] 报告英文优先文案与 listing 素材（禁夸大宣传），演示视频
- [ ] 许可证：仓库 AGPL-3.0-only，商用 SaaS 形态需版权人（作者本人）出具双重许可说明
