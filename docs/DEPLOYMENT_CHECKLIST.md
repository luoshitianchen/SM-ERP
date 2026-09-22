# SM-ERP 上线检查清单（Deployment Checklist）

> 版本 v1.0 ｜ 服务：SM-ERP（sm-erp，端口 8003）｜ 数据库：sm_erp

## 1. 上线前检查

- [ ] 代码评审（≥1 名 reviewer approve）
- [ ] 单元测试全部通过，覆盖率 ≥ 团队阈值
- [ ] 安全扫描：Trivy 无高危漏洞，SBOM（sbom.json）已生成
- [ ] 性能基准：P99 与错误率符合 SLO（见 OPERATIONS.md）
- [ ] 变更单号已创建，回滚方案已准备
- [ ] 数据库迁移脚本（alembic）已评审并可回滚

## 2. 配置检查

- [ ] ConfigMap 非敏感项正确（SM_ENV/SM_LOG_LEVEL/SM_DATABASE_*）
- [ ] 敏感项均来自 Vault（ExternalSecret），未硬编码进 Git
- [ ] 数据库连接指向正确环境（sm_erp）
- [ ] 资源 requests/limits 经压测验证
- [ ] 探针路径 /health、/readyz 可用

## 3. 部署步骤

1. 合并代码，CI 构建镜像并推送 ghcr.io/luoshitianchen/sm-erp
2. 在 staging 部署并完成回归
3. 变更窗口内，ArgoCD 同步 prod（helm/sm-erp，values.yaml + values-prod.yaml）
4. 观察 rollout：`kubectl -n sm-prod rollout status deploy/sm-erp`

## 4. 验证步骤

- [ ] 冒烟：curl /health、/readyz 返回 200
- [ ] 监控：Pod Ready、CPU/内存正常、无 5xx 突增
- [ ] 业务：核心接口走查通过，日志无报错
- [ ] 告警：无持续触发的 P0/P1 告警

## 5. 回滚触发条件与步骤

- 触发：错误率 > 0.1% 持续 5 分钟、核心接口不可用、数据异常。
- 步骤：ArgoCD 回退历史版本 或 `kubectl -n sm-prod rollout undo deploy/sm-erp`。
- 验证：探针通过 + 业务恢复 + 观察 30 分钟。

## 6. SBOM 与供应链策略

- 依赖锁定：requirements.lock 固定版本。
- 漏洞扫描：Trivy（容器+依赖）、Dependabot 月度更新。
- 镜像签名：使用 cosign 签名，部署侧校验签名。
- SBOM：每次构建生成 sbom.json（SPDX），随发布物归档。
