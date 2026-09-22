# SM-ERP 运维手册（Operations）

> 版本 v1.0 ｜ 服务：SM-ERP（sm-erp，端口 8003）｜ 数据库：sm_erp

## 1. 服务概述与依赖

SM-ERP 基于 Python（FastAPI/uvicorn）构建，对外提供业务 API。运行依赖：

- PostgreSQL（sm_erp）：主从高可用，8003 端口对外服务。
- SM-IAM：身份认证与 JWT 验签。
- SM-Event-Bus：异步事件（如启用）。
- 基础设施：Ingress-NGINX、External-Secrets/Vault、Loki/Promtail、Prometheus。

## 2. SLO 定义

| 指标 | 目标 | 测量窗口 |
| --- | --- | --- |
| 可用性 | ≥ 99.9% | 30 天滚动 |
| P99 延迟 | < 1000ms（/api/overview） | 1 分钟粒度 |
| 错误率（5xx） | < 0.1% | 1 分钟粒度 |

可用性 99.9% 对应月度不可用 ≤ 约 43 分钟。

## 3. 错误预算公式与消耗跟踪

- 月度错误预算 = 总请求量 × (1 - 99.9%) = 总请求量 × 0.1%。
- 跟踪：Grafana 看板展示剩余预算；预算消耗 > 50% 触发预警，> 90% 冻结非紧急变更。
- 消耗完毕后：优先稳定性修复，冻结新功能发布，直至下一窗口或经 CAB 特批。

## 4. 变更管理流程（CAB 审批、变更窗口）

- 变更分级：标准变更（预授权）、常规变更（CAB 审批）、紧急变更（事后补审）。
- 变更窗口：工作日 10:00–16:00，避免大促/月末结账高峰。
- 所有变更需关联变更单号，记录：变更内容、回滚方案、影响面、值班人。

## 5. 发布审批流程（dev→staging→prod 门禁）

1. dev：合并 main 自动部署，冒烟通过即可。
2. staging：自动部署 staging 镜像，回归测试 + 故障演练（chaos）通过。
3. prod：人工审批（发布经理 + 服务负责人），在变更窗口内通过 ArgoCD 同步。
- 门禁：单测通过率 100%、覆盖率 ≥ 阈值、无高危漏洞、SBOM 生成。

## 6. 回滚流程（步骤、RTO、验证）

1. `kubectl -n sm-prod rollout undo deploy/sm-erp` 或 ArgoCD 回退至历史版本。
2. 确认 Pod 就绪、/health 与 /readyz 通过。
3. RTO 目标 ≤ 10 分钟；回滚后观察 30 分钟监控与错误率。
4. 记录事故单并复盘。

## 7. 值班与告警响应（on-call、升级路径）

- 主值班 → 备份值班 → 服务负责人 → 平台负责人，逐级升级（5/15/30 分钟）。
- P0：立即响应并拉起作战群；P1：30 分钟内响应；P2：工作时间处理。
- 告警通道：PagerDuty/飞书机器人，按严重性分级。

## 8. 日常运维操作手册

- 查看日志：`kubectl -n sm-prod logs -l app.kubernetes.io/name=sm-erp --tail=200`。
- 扩缩容：优先通过 HPA；手动 `kubectl -n sm-prod scale deploy/sm-erp --replicas=N`。
- 配置变更：修改 helm values → PR → 评审 → ArgoCD 同步，禁止直接改线上 ConfigMap。
- 密钥轮换：在 Vault 更新后 ExternalSecret 1 小时内自动刷新，必要时重启 Pod。
