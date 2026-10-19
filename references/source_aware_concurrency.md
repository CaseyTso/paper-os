# 源感知并发下载策略 (Source-Aware Concurrency)

在批量下载学术论文时，不同的数据源对并发请求与风控机制的容忍度具有显著差异。本策略用于指导主 Agent 在调度多任务时的并发分配与限流控制。

---

## 1. 来源分级与并发权重

| 来源级别 | 数据源类型 | 并发上限 | 风控机制与应对 |
|---|---|---|---|
| **Tier 1: 开放获取 (Open Access)** | PMC, Europe PMC, PubMed Linkout, Unpaywall | **3–5 并发** | 无严格风控，正常 HTTP 抓取，高并发安全。 |
| **Tier 2: 机构访问 (Institution)** | EasyConnect / aTrust 代理隧道 | **2–3 并发** | 取决于本地校园网隧道承载能力，建议适度并发。 |
| **Tier 3: Sci-Hub** | Clash 代理 + 官方镜像 | **2–3 并发** | 遇 ALTCHA 算力挑战由 CLI 自动计算；若失败触发 `challenge_required`，由子 Agent 记录 URL，不阻塞其它任务。 |
| **Tier 4: 科研通 (ableSci)** | Chrome Cookie / HTTP API / Webdriver | **严格 1 并发 (串行排队)** | **极度敏感**。多请求并发共用 Cookie 极易触发阿里云 WAF 验证码或拉黑 IP。必须串行执行，每篇请求间隔 $\ge 5$ 秒。 |

---

## 2. 调度执行算法

1. **分流探测**：
   - 优先通过 DOI / PMID 在 Europe PMC 与 PubMed 开放接口检索是否有公开全文本（Open Access）；
   - 若具备 OA 链接，直接并发发起下载；
2. **敏感队列缓冲 (Queue Buffer)**：
   - 若某篇文献确认进入付费/机构/ableSci 链路，将其推入单工作队列；
   - 保证同一时刻只有一个子 Agent 调用 ableSci 接口；
3. **静默失败与集中呈报**：
   - 遇到验证码或需要登录态时，子 Agent 不尝试盲目重试，立即返回结构化阻断信息；
   - 主 Agent 在批次完成后汇总展示人工处理入口。
