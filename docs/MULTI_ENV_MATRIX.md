# SM-ERP 多环境差异矩阵（Multi-Env Matrix）

> 版本 v1.0 ｜ 服务：SM-ERP（sm-erp，端口 8003）｜ 数据库：sm_erp

| 维度 | dev | staging | prod |
| --- | --- | --- | --- |
| 命名空间 | sm-dev | sm-staging | sm-prod |
| 副本数 | 1 | 2 | 3 |
| HPA 最小/最大 | 1 / 3 | 2 / 5 | 3 / 10 |
| CPU request/limit | 50m / 200m | 100m / 500m | 200m / 1 |
| 内存 request/limit | 64Mi / 128Mi | 128Mi / 256Mi | 256Mi / 512Mi |
| 镜像 tag | dev | staging | appVersion（2.1.0） |
| 日志级别 | debug | info | warn |
| 数据库 | dev 实例（sm_erp） | staging 实例 | 生产主从（sm_erp） |
| Ingress 域名 | sm-erp.dev.sm.example.com | sm-erp.staging.sm.example.com | sm-erp.sm.example.com |
| TLS | 无 | sm-staging-tls | sm-tls |
| 密钥来源 | 本地/开发 Vault | staging Vault | 生产 Vault（ExternalSecret） |
| 故障演练 | 不启用 | 启用（chaos） | 严禁启用 |
| 发布方式 | 自动 | 自动+回归 | 人工审批+窗口 |
