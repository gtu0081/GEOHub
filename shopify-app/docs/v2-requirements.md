# AI Commerce Readiness 2.0 — 需求规划

> 依据文档：《Shopify AI Commerce App 重构升级实施报告》（下称《实施报告》，产品总规范）+
> 《iannuttall/seo 对 Shopify AI Commerce App 的参考价值评审》（下称《引擎评审》，工程范式来源）。
> 本文将两份文档合并为统一需求集，对照 1.0 PoC 现状给出复用/重写/删除结论、决策点与里程碑。
> 日期：2026-09-02 · 状态：待确认

---

## 0. 最高优先级结论（两文档交汇点）

```text
旧主轴（1.0 PoC）：网页抓取 → 启发式 GEO 八维分 → 问题地图/内容/观测
新主轴（2.0）    ：Shopify Admin 商品真数据（全量）
                  → 类目感知的购买决策属性审计（Ontology）
                  → 证据对齐的结构化补全（可审核/可回滚）
                  → Catalog representation 一致性检查
                  → Storefront Catalog buyer-intent 检索闭环（修复前后可复验）
```

两条铁律（贯穿全部需求）：
1. **诚实度量**：`unknown / not_applicable` 不得计为 `fail`；无证据不生成事实；检索提升只表述为"本店 Storefront Catalog 命中变化"，绝不表述为"ChatGPT 排名"（文档一的 claim-contract + 文档二 §6.1/§13）。
2. **纵向闭环优先**：宁可 5 个商品完整走通「审计→建议→确认→写入→复测」，不做 10 个浅功能（文档二 §23 最小黄金路径）。

## 1. 决策点（开工前必须确认）

| # | 决策 | 选项 | 结论 |
|---|---|---|---|
| D1 | **AGPL 合规路径** | A. ~~版权人书面自授权~~（**已排除：团队并非 GEOHub 版权人**）；B. clean-room 全新核心重写 | **确定 B：clean-room 重写**。GEOHub 代码、模板、prompt、schema、测试夹具及一切调用（含 import 链接）均不得进入闭源版本；发布阻断直至重写完成 |
| D2 | 仓库策略 | 新私有仓库 / `app-v2/` 目录 | 新私有仓库（干净 provenance，旧仓库打只读归档标签） |
| D3 | iannuttall/seo 代码复用 | 先做 2 天兼容性 Spike（固定 commit `52f1001`，3 店 20–50 商品页）再决策 | 做 Spike；无论是否复用代码，其 EvidenceEnvelope/规则注册表/diff 范式直接进设计 |
| D4 | Shopify API 版本 | 固定 `2026-07`（或实现时最新稳定版，ADR 记录） | 实现时以官方最新稳定版固定，禁用 `latest` |
| D5 | 1.0 六技能的去留 | 降级为 P1 web-audit bounded context | discover/knowledge 的思路并入 Ontology/属性体系；diagnosis/compare 并入 P1 Web 审计层；measure（人工观测）被 R5 检索闭环取代；content 被 R4 evidence-only 生成取代 |

### D1 确定后的 clean-room 纪律（对 AI 编程助手的强制约束）

1. 2.0 核心实现只允许依据：本规划、《实施报告》、Shopify 官方文档、公开标准、团队原创需求；**不得参考 GEOHub 源码表达进行"翻译式重写"**（文档二 §4.1 明确"让 AI 重写一次"不解决许可证问题）。
2. 已深度阅读过 GEOHub 源码的 AI 助手，在 2.0 核心模块（规则引擎、评分、审计、爬虫）中只能采用**通用工程模式**（如任务队列、原子写入、租户隔离这类行业通行做法），不得复现其具体数据结构、命名、算法组织和文案表达。
3. 1.0 PoC 仅作**黑盒行为参考**（确认商家必需的功能清单与验收口径），不从中迁移代码；黑盒对照输出限于功能列表。
4. iannuttall/seo（Apache-2.0）与 GEOHub（AGPL）代码**严禁混入同一模块**；Apache 部分需 provenance/SPDX 标注。
5. 仓库建立 `LICENSE_POLICY.md`、`THIRD_PARTY_NOTICES.md` 与 CI 许可证扫描；任何来源不明文件按 BLOCK 处理。

## 2. 需求集（R0–R7）

需求编号规则：`R<域>.<序号>`；每条标注来源（实施报告 § / 引擎评审 §）与验收标准（AC）。

### R0 基础与合规（对应 Phase 0–1）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R0.1 | 仓库审计报告：文件树、依赖清单、provenance 三分类（FIRST_PARTY_SAFE / THIRD_PARTY_PERMISSIVE / AGPL_OR_UNCLEAR） | 实施报告 §4.3、§22 | `REPOSITORY_AUDIT.md`、`LICENSE_INVENTORY.md`、`KEEP_REWRITE_DELETE.md` 产出并经确认 |
| R0.2 | 新仓库骨架：官方 Shopify app 模板 + Prisma/Postgres + Postgres-backed 队列 + Web/Worker 分进程 | 实施报告 §10 | install/uninstall/reinstall 自动化通过；无跨店数据泄露测试通过 |
| R0.3 | 合规 webhook（app/uninstalled、customers/*、shop/redact）+ 卸载数据清理 + token 撤销 | 实施报告 §9.3、§16 | 沿用 1.0 的店铺隔离协议与卸载清理**模式**（bind_shop/authorize_job/tombstone，团队原创设计），代码随新栈重写 |
| R0.4 | 最小 scope：`read_products`（+实现 write 面后 `write_products`）；codegen 验证每个字段 | 实施报告 §9.1 | scope 申请有逐字段依据；无静默扩权 |
| R0.5 | CI：typecheck/lint/unit/build + 许可证扫描 + SBOM | 实施报告 §18 | CI 红灯阻断合并 |

### R1 数据地基：Admin truth（Phase 2）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R1.1 | 全量商品同步：Admin GraphQL Bulk Operations，嵌套 variants/media/category/options/必要 metafields，JSONL 流式解析 | 实施报告 §9.2 | 20k products / 80k variants 内存有界、可恢复、幂等（shop+GID 唯一键） |
| R1.2 | ProductSnapshot/VariantSnapshot 不可变版本 + contentFingerprint + deletedAt | 实施报告 §11.1 | 快照可重建、可 diff；Apply 前用 fingerprint 做 stale 检测 |
| R1.3 | 增量同步：products/create/update/delete、bulk finish、shop/update webhook；幂等/乱序/退避/dead-letter/定时 reconcile | 实施报告 §9.3 | E2E：webhook 重复、乱序、bulk 超时全部恢复 |
| R1.4 | 同步 UI：progressive 进度、计数、错误 | 实施报告 §5.1 | 大店不等待全量完成即可见部分结果 |

### R2 审计引擎：规则注册表（Phase 3）

采用《引擎评审》的范式作为引擎骨架（D3 无论结论如何）：

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R2.1 | **Versioned Rule Registry**：每条规则 = id/version/layer/targetType/applicability/evidenceRequirements/derive/severity(仅 triage)/verification | 引擎评审 增补2、实施报告 §6.1 | 规则独立可测；禁止巨型 calculateScore() |
| R2.2 | **六态结果**：PASS/WARN/FAIL/**UNKNOWN/NOT_APPLICABLE/NOT_EVALUATED**；unknown/N/A 不进分母 | 引擎评审 §3.2、实施报告 §6.1 | 每条规则单测覆盖六态；分数公式 = Σ(passed)/Σ(measurable applicable) |
| R2.3 | **EvidenceEnvelope 统一外层**：sourceKind/sourceRef/observedAt/scope/completeness/limits/observations/findings/actions/verification，覆盖 Web/Admin/Catalog/Retrieval 四层 | 引擎评审 增补1 | 所有 run 产物落此契约；「没看到 ≠ 不存在」 |
| R2.4 | **scope fingerprint**：shop/API 版本/规则集版本/market/locale/currency/选品/crawl seed/query-set 版本；只有 fingerprint 兼容的 run 可比 | 引擎评审 增补3 | before/after 比较强制校验 fingerprint |
| R2.5 | P0 规则目录落地：ELIG（8 条）/ DATA（14 条）/ CONV（10 条）/ CATALOG（7 条）/ RETRIEVAL（4 条） | 实施报告 §6.3 | 每条规则 + 测试 + severity + automatable 标注；受影响对象清单（扩展 target：STORE/PRODUCT/VARIANT/COLLECTION/MARKET/LOCALE/URL/QUERY） |
| R2.6 | 六维评分与展示：Catalog Eligibility 20 / Product Data 25 / Conversational Attributes 20 / Catalog Representation 15 / PDP Web Trust 10 / Agent Retrieval 10；**无总分**，显示 coverage/median/P10/critical 数 | 实施报告 §6.2 | Storefront Catalog 不可用时 Agent Retrieval = Not measured，其余维度重归一化并明示 |
| R2.7 | 禁止低质量规则（字数阈值、词频、任意 JSON-LD 即合格、当前年份判新鲜等） | 实施报告 §6.4 | 规则评审清单逐条过 |

### R3 类目 Ontology（Phase 3）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R3.1 | 三层回退：精确类目 → 垂直行业 → 通用层；无法识别类目时只用通用层并要求商家选择 | 实施报告 §7.2 | 单测覆盖三级 fallback；不强套类目属性 |
| R3.2 | 首批 5 垂直 + 1 通用：Apparel/Footwear、Electronics accessories、Home & Kitchen、Beauty、Sports/Outdoor、Generic | 实施报告 §7.4 | 每条属性含 importance(必需/推荐/条件/高风险)/allowed_sources/infer_from_image=false/证据要求 |
| R3.3 | 版本化 ontology（YAML + 单测）；高风险属性（防水/认证/适用年龄/兼容型号）require_explicit_evidence: true | 实施报告 §7.3、§8.3 | 高风险 gate：无证据 → 输出 unknown，不生成 |
| R3.4 | 写入策略核实与优先级：标准 category metafield > 商家已有定义 > app-owned（`$app:ai_commerce`）> 改 description | 实施报告 §7.5 | 写入前逐字段核实 Shopify 标准 metafield 清单（ADR 记录），不重复造同义字段 |

### R4 生成 · 审核 · 写入 · 回滚（Phase 4）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R4.1 | AI Provider 适配层（业务层不见具体 SDK）；结构化 JSON 输出（attributeKey/proposedValue/confidence/evidence/risk/target） | 实施报告 §8.2、§10.4 | schema 不合法进 retry/dead-letter，绝不写半成品 |
| R4.2 | 事实约束：无证据=unknown；图片仅可描述可见视觉事实；医疗/过敏/儿童/防火防水/认证/兼容必须有来源；低 temperature；prompt 模板版本化 | 实施报告 §8.3 | claim-contract eval 集（引擎评审 增补4 七条断言）入库并在选定模型上跑出实测通过率 |
| R4.3 | **fix/review 双队列**：机械修复（fixed/deferred/not-needed）与需商家判断（changed/no-change/deferred）分离；禁止"无预览全自动覆盖" | 引擎评审 §3.5、实施报告 §5.2E | 状态机 detected→…→verified 全事件留痕 |
| R4.4 | Apply 管线：immutable writePlan/diff 预览 → 商家显式确认 → stale fingerprint 检测 → 逐批写入（metafieldsSet userErrors 处理）→ before/after 快照 → 按批次回滚 | 实施报告 §11.3、§12 | E2E：应用前商品被商家修改 → 暂停并要求重新预览 |
| R4.5 | 成本控制：deterministic 规则先行、fingerprint 缓存、小批次(默认 20/最大 100)、store/day 预算、token/cost/latency 台账 | 实施报告 §8.4 | UsageLedger 落库；超预算降级 |

### R5 检索闭环：Storefront Catalog（Phase 5）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R5.1 | Capability detection：canonical domain → `/api/ucp/mcp` → App 托管的 UCP agent profile → tools/list 确认 search_catalog/lookup_catalog/get_product；保存状态与失败原因 | 实施报告 §9.4 | 暂时限流 ≠ 永久不可用；UI capability warning |
| R5.2 | QuerySet 版本化：每商品 5–12 条 buyer-intent query（category+feature/audience/use case/compatibility/material/constraint/variant intent）+ intent tags + 商家可编辑 | 实施报告 §13.1 | immutable QuerySetVersion；baseline/verify 强制同版本 |
| R5.3 | 检索运行：search/lookup/get_product 三类合同测试；上下文 country/language/currency/intent；遵守 rate limit | 实施报告 §9.4 | contract tests 过；断点续跑 |
| R5.4 | 指标与合规存储：Query Hit Rate、Target Recall@K、Correct Variant Rate、Median Target Rank、Coverage Delta；**不持久化完整搜索结果/图片**，仅存派生事实（run time/query hash/target IDs/命中/名次/variant 正确性/error class/evidence hash） | 实施报告 §13.2、§9.4 | 存储层审计确认无原始响应落盘 |
| R5.5 | Before/After 报告：同 fingerprint 对比、Catalog processing delay 宽限、两次稳定结果才 verified、小样本显示样本数不营销 | 实施报告 §13.3 | ≥3 个 dev store 完成可重复 before/after；文案含"不等于 ChatGPT 排名"免责 |

### R6 商家 UX（Phase 3–6 渐进）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R6.1 | 八页面：Dashboard / Products / Product Detail（四列：Source data、Catalog representation、Issues、Recommendations）/ Issues（规则中心批量）/ Optimize Queue / Retrieval Tests / Web & Trust(P1) / Settings | 实施报告 §5.2 | 首装 10 分钟内见 Top 3 blockers；沿用 1.0 的 Polaris 组件模式（IndexTable/Banner/EmptyState/Modal/轮询，团队原创） |
| R6.2 | Dashboard：同步状态、eligibility 状态、六分项、Product coverage 分布、Top 3 blockers、retrieval baseline、唯一主 CTA `Fix highest-impact products` | 实施报告 §5.2A | 不显示单一神秘总分 |
| R6.3 | Product Detail 示例格式落地：`CONV.COMPATIBILITY.MISSING` + 规则解释 + 受影响 query 数 + 需商家确认 | 实施报告 §5.2C | 禁止"Improve description"式空泛建议 |
| R6.4 | Empty/partial/error 状态 + capability warning + 手机窄屏基本可用 | 实施报告 §15.4 | 1.0 的 loader 错误透出（backendError Banner）与轮询终止模式迁移复用 |

### R7 产品化与 Beta（Phase 6–7）

| ID | 需求 | 来源 | 验收标准 |
|---|---|---|---|
| R7.1 | Billing：Free（只读审计+3–5 query）/ Growth $14–19 / Pro $39–59 / Scale $99+；usage ledger 预留；付费点="生成·应用·验证"，llms/agents 文件不设付费 | 实施报告 §20 | Shopify Billing API 接入；免费层完整走通首次审计 |
| R7.2 | 运营：OTel 结构化日志（token/描述脱敏）、kill switch（停写保读）、feature flags、5–10 家真实 Beta 店 | 实施报告 §16 | Beta 商家无开发者协助完成一次闭环（DoD） |
| R7.3 | agents.md/llms.txt 检测（P0 只读：可访问性 + 是否被主题覆盖 + "Shopify 已默认生成"提示，不生成不收费） | 实施报告 §9.6 | 无自动生成/覆盖入口 |

### P1/P2（2.0 不做或验证后做）

- P1：PDP 分层抽样 Web 审计（iannuttall 引擎或自研，D3 决定）、JSON-LD 深度一致性、conflict-safe Theme App Extension、GSC/Bing/IndexNow、Web Pixel 归因、多语言/Markets、Billing 正式化
- P2：跨平台 prompt 监测（取代 1.0 measure）、Share of Voice、agency 白标、自动化 Catalog Mapping（仅官方稳定 API 后）、多触点归因
- 明确不做：自建搜索引擎、字数/关键词密度类分数、自动高风险声称、改主题源代码、把 Shopify 免费能力包装收费

## 3. 1.0 资产处置清单

> D1=clean-room 前提下的分类。判定标准：代码是否由团队原创且**不链接、不派生** GEOHub。

| 1.0 资产 | 处置 | 依据 |
|---|---|---|
| Remix 壳：OAuth/session/AppProvider/NavMenu/合规 webhook 转发路由 | **保留迁移**（基于 Shopify 官方模板的团队原创，无 GEOHub 派生） | 实施报告 §4.2 第 5 条 |
| 店铺隔离授权（bind_shop/authorize_job/x-shop-domain 协议） | **保留迁移**（团队原创） | R0.3 |
| Polaris UI 模式（IndexTable/Banner/EmptyState/Modal/轮询终止/错误透出） | **保留复用**（团队原创） | R6 |
| FastAPI 后端的 config/security/webhooks 层 | **设计保留、代码按新架构重写**（2.0 为 TS 统一栈；session token/HMAC/bind_shop 的实现思路是通用工程模式） | R0.2 |
| JobManager 多 kind 任务框架（Python） | **重写**：调用 `geo_seo_hub` 引擎 = 继续链接 AGPL，不可迁移；2.0 按 Postgres 队列 + TS worker 重建（多租户隔离、幂等、tombstone 为通用模式可沿用思路） | D1 纪律第 2 条 |
| GEOHub 六技能引擎调用（site-diagnose/diagnose/discover/content/measure/knowledge） | **BLOCK**：2.0 全部不用。功能归宿见 D5；等价能力由 R1–R5 重新实现 | D1 |
| data_retention 引擎（分级保留/回收站/冷静期） | **重写**：属 GEOHub 库；数据保留/可恢复删除的**策略设计**（L0–L3 分级、宽限期）作为需求保留，代码重新实现 | D1 |
| 离线测试夹具（site-diagnose-demo fixture、demo fixture fetcher） | **BLOCK**：GEOHub 测试夹具；2.0 测试数据另行构造 | 实施报告 §0 第 2 条 |
| `reports/examples` 可视化报告与报告资产 | **归档不下迁**（GEOHub 产物，且 2.0 无总分报告形态） | R2.6 |
| 1.0 的 GraphQL shop 查询、dev 工具链（.npmrc/启动流程） | **保留迁移**（团队原创） | R0.2 |

## 4. 里程碑（clean-room 路径，约 13–15 周）

| Phase | 周 | 交付 | Gate |
|---|---|---|---|
| 0 审计与决策 | 1 周 | R0.1 三份文档（含 GEOHub 派生面全量清单：引擎调用、fixture、报告）+ D2–D5 决议 + ADR | BLOCK 项全部有处置结论；clean-room 纪律入仓（LICENSE_POLICY/CI 扫描） |
| 1 骨架 | 2 周 | R0.2–R0.5（TS 全栈新仓库） | install/reinstall 自动化 + 隔离测试 |
| 2 数据地基 | 3–4 周 | R1 全部 + 20k 压测 | 同步可恢复/幂等/内存有界 |
| 3 规则与 Ontology | 5–7 周 | R2.1–R2.7 + R3 + Dashboard/Products/Issues 首版（规则引擎从零实现，仅依据本规划与官方文档） | 每条规则有测试；任意分数可点开解释 |
| 4 生成与写入 | 8–10 周 | R4 全部 + Optimize Queue | 任何 Shopify 写入经确认且可按批回滚 |
| 5 检索闭环 | 11–12 周 | R5 全部 + Retrieval Tests + before/after 报告 | ≥3 dev store 可重复对比 + 免责文案 |
| 6 产品化 | 13 周 | R6 收尾 + R7.3 + Beta 准备 | 真实商家无协助完成闭环 |
| 7 P1 | 14 周+ | Web 审计层（含 D3 决议执行）+ Billing | 按需 |

每个 Phase 开始/结束执行《实施报告》§18 的提交协议（阶段前输出计划与风险，阶段后输出测试证据与 rollback 方法）。

## 5. Definition of Done（验收总表）

直接采用《实施报告》§19 全部检查项，另加三条 2.0 特有项：

- [ ] claim-contract evals（七条"不能声称"断言）在选定模型上跑通并记录实测通过率；
- [ ] iannuttall/seo 若有代码复用：固定 commit、provenance/SPDX 标注、Apache attribution 完成，且未与 AGPL 模块混入；
- [ ] 1.0 的六个技能入口在 2.0 信息架构中有明确归宿（迁移或下线），无孤儿路由。

---

### 附：北极星与配套指标（实施报告 §1.4）

**北极星**：已完成修复的商品中，Storefront Catalog Buyer-intent Retrieval Coverage 获得可测提升的商品占比。
配套：首次扫描完成率 / 发现→首次 Apply 时间 / 建议确认率 / query hit rate·recall·correct-variant 前后变化 / 7·30 日复扫率 / 回滚率 / 免费扫描→付费修复转化率。
