# GEOHub for Shopify — Phase 0 PoC

把 GEO SEO Hub 的六个技能包成 Shopify 嵌入式应用：网站 GEO 诊断（site-diagnose）、AI 问题地图（discover）、内容草稿（content）、AI 引用观测（measure）、品牌事实卡（knowledge）、竞品对比（diagnose），外加数据保留引擎（retention）。左侧导航由 App Bridge NavMenu 提供。

## 技能矩阵

| 导航入口 | 引擎技能 | kind | 商家故事 |
|---|---|---|---|
| Diagnosis | geo-site-diagnose | diagnosis | 体检：八维评分 + 修复建议 + 页面钻取 + 可视化报告 |
| Question map | geo-discover | discover | 发现该赢的 AI 搜索问题与内容机会 |
| Content drafts | geo-content（3 模式） | content | 从主题到证据对齐的页面蓝图/解释文/改写 |
| AI citations | geo-measure | measure | 商家提交观测，跟踪品牌被 AI 引用的比率 |
| Brand facts | geo-knowledge | knowledge | 从最新诊断提取品牌表述，标记跨页冲突 |
| Competitors | geo-diagnose | compare | 自己页面 vs 最多 4 个竞品的信号对比 |
| （无 UI） | data_retention | — | L2=30 天保留，后台每日清理，`/api/retention` 预览/执行 |

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

### 本地启动顺序（2026-09-01 实测通过）

本机 CLI 内置的 Cloudflare 隧道会卡在 "Requesting new quick Tunnel"（quick tunnel 有创建频率限制），所以用手动隧道 + `--tunnel-url` 的方式：

```bash
# 1) 后端（端口 8000，凭证从 backend/.env 自动加载）
cd shopify-app/backend
.venv/bin/python -m uvicorn app.main:app --port 8000

# 2) 手动隧道（指向 CLI proxy 端口 50280；域名每次重启会变）
cd shopify-app/frontend
node_modules/@shopify/cli/bin/cloudflared tunnel --url http://localhost:50280
#   → 从输出中拿 https://<random-words>.trycloudflare.com

# 3) dev 服务器（tunnel-url 的端口就是 CLI proxy 的监听端口，必须带）
node_modules/.bin/shopify app dev --store jie-dev.myshopify.com \
  --tunnel-url https://<random-words>.trycloudflare.com:50280
```

踩坑记录（已修复，供以后参考）：

- 模板的 `shopify.web.toml.liquid` 不会被 CLI 4.x 即时渲染，导致 vite 根本不启动——仓库里已提交渲染好的 `shopify.web.toml`。
- CLI 4.x 要求 `shopify.app.toml` 新 schema（`[auth] redirect_urls`、`application_url`、`embedded`、`[webhooks.privacy_compliance]`），已按新格式重写。
- CLI 需要登录：设备码流程在终端给出 URL，浏览器完成授权即可（遇 hCaptcha 手动点一下）。
- 系统 npm 缓存有损坏文件时用项目本地缓存（`.npmrc` 已配 `cache=../.npm-cache`）。

已完成的改造：

- `app/routes/app._index.tsx`：GEO 诊断仪表盘，按 Polaris 设计标准实现——主操作走 TitleBar + `Modal` 表单、空状态用 `EmptyState`、运行历史用 `IndexTable`、进行中用 `Banner`、无结果引导；侧栏是 Polaris annotated content（评分说明 + AI 爬虫访问矩阵）。默认诊断目标来自 GraphQL Admin API 的店铺主域名。
- `app/routes/app.diagnosis.$jobId.tsx`：诊断详情页（面包屑返回、八维分数条形图 `ProgressBar`、按优先级排序的修复建议表、报告 iframe、原始产物 JSON 下载）。
- `app/components/`：`ScoreSnapshot` / `CrawlerAccessCard` / `DiagnosisModal` / `JobStatusBadge` 复用组件，类型与色调映射在 `app/lib/jobs.ts`。
- `app/routes/api.jobs.$jobId(.report/.artifacts.$name).tsx`：带会话认证的资源路由，代理后端。
- `app/routes/webhooks.customers.*.tsx` / `webhooks.shop.redact.tsx`：GDPR 合规 webhook 验证并转发后端（`shopify.app.toml` 已启用三个 compliance 订阅）。
- scopes 收敛为 `read_products`（阶段 0 只读店铺元信息）。

### 浏览器渲染（真实站点验证）

Shopify 主题是 JS 渲染的，`render=auto` 会在检测到 JS 壳时用 Playwright Chromium 渲染。安装方式：

```bash
cd shopify-app/backend
.venv/bin/python -m pip install -e '/path/to/geohub[render]'
.venv/bin/python -m playwright install chromium
```

已实测（React 渲染的沙盒站点 `quotes.toscrape.com/js/`，3 页上限）：诊断成功，run 的 `input/sources/` 同时落盘 `-http.html` 与 `-browser.html` 双快照，报告含渲染后内容。未安装 Playwright 时自动降级 HTTP 模式并在报告中记录证据缺口，不会失败。

## 距离上架还差什么（阶段 1 清单）

- [ ] Billing API 套餐（免费起步也建议先接，避免二次过审改动）
- [ ] 生产化存储：runs 产物同步对象存储 + Postgres 记录任务/趋势（现为本地 FS）
- [ ] 任务队列 + Playwright worker 池（现线程池，浏览器渲染需进程隔离与硬超时）
- [ ] Shopify 数据深化：产品/集合/页面的 Admin API 信号（比爬取更权威的评分输入）
- [ ] 报告英文优先文案与 listing 素材（禁夸大宣传），演示视频
- [ ] 许可证：仓库 AGPL-3.0-only，商用 SaaS 形态需版权人（作者本人）出具双重许可说明
