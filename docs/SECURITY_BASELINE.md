# SM-ERP 安全基线（Security Baseline）

> 版本 v1.0 ｜ 适用服务：SM-ERP（sm-erp，端口 8003）｜ 数据库：sm_erp
> 本文件依据 TEMPLATE_SPEC.md 要求编制，覆盖等保 2.0 三级、ISO 27001、数据分类分级与 RBAC 矩阵。

## 1. 安全基线概述

SM-ERP 是企业核心业务微服务之一，承载敏感业务数据的读写与对外 API 服务。安全基线以"最小权限、纵深防御、全程审计"为原则，从网络、身份、数据、运行时四个层面建立控制：

- 网络层：NetworkPolicy 限制入站仅同命名空间与 Ingress-NGINX，出站仅 DNS 与必要后端。
- 身份层：ServiceAccount 关闭 automountToken，Pod 以非 root（UID 1000）运行，禁止提权。
- 数据层：敏感配置经 ExternalSecret 从 Vault 注入，不落 Git；SM4 字段级加密。
- 运行时：只读根文件系统、drop ALL capabilities、liveness/readiness 探针保障自愈。

## 2. 等保 2.0 三级控制映射表

| 控制点 | 要求 | 实现方式 | 证据 |
| --- | --- | --- | --- |
| 身份鉴别 | 口令/多因素认证 | IAM 统一签发 JWT，服务间 mTLS + Internal API Key | argocd/sm-erp-application.yaml、deploy/externalsecret |
| 访问控制 | 最小权限 RBAC | K8s RBAC + 业务层角色矩阵（见第 5 节） | docs/SECURITY_BASELINE.md |
| 安全审计 | 审计日志留存≥6个月 | 全量访问日志经 Promtail→Loki，审计中心归档 | deploy/promtail/promtail-config.yaml |
| 入侵防范 | 边界访问控制 | NetworkPolicy 入/出站白名单 | helm/sm-erp/templates/networkpolicy.yaml |
| 恶意代码防范 | 镜像漏洞扫描 | Trivy 扫描 + SBOM（syft）+ 镜像签名 | .trivyignore、sbom.json |
| 数据完整性 | 传输完整性 | HTTPS/TLS1.2+，Ingress ssl-redirect | helm/sm-erp/templates/ingress.yaml |
| 数据保密性 | 存储保密性 | SM4 字段加密，数据库 TDE | Vault 路径 secret/sm/erp/sm4-key |
| 备份恢复 | 数据备份 | PG 每日全量 + WAL 持续归档 | docs/DR_RUNBOOK.md |

## 3. ISO 27001 控制映射表

| 控制域 | 关键控制 | 实现 |
| --- | --- | --- |
| A.5 组织安全 | 访问策略、职责分离 | CAB 审批 + 变更窗口（OPERATIONS.md） |
| A.6 人员安全 | 入职/离职权限回收 | IAM 账号生命周期联动 HR |
| A.8 资产管理 | 数据分类分级 | 见第 4 节 |
| A.9 访问控制 | 最小权限、特权账号管理 | RBAC 矩阵 + Vault 动态密钥 |
| A.10 密码学 | 加密与密钥管理 | SM4 字段加密、TLS、KMS 轮换 |
| A.12 运营安全 | 日志、监控、漏洞管理 | Promtail/Loki + 漏洞扫描流水线 |
| A.13 通信安全 | 网络隔离 | NetworkPolicy + 命名空间隔离 |
| A.16 事件管理 | 安全事件响应 | INCIDENT_RESPONSE.md + on-call 升级 |
| A.17 业务连续性 | 容灾备份 | DR_RUNBOOK.md 跨可用区切换 |
| A.18 合规 | 合规审计 | 等保测评 + 内审证据留存 |

## 4. 数据分类分级表

| 级别 | 定义 | 本服务典型字段 | 处置要求 |
| --- | --- | --- | --- |
| 公开 | 可对外公开 | 服务元数据、版本号 | 无特殊要求 |
| 内部 | 仅限企业内部 | 业务配置、非敏感统计 | 内网访问，禁止外发 |
| 机密 | 需授权访问 | 业务单据、客户/供应商信息 | RBAC 鉴权 + SM4 加密 + 审计 |
| 绝密 | 极高敏感 | 凭证、密钥、个人敏感信息 | Vault 托管 + 字段级加密 + 严格审计 |

## 5. RBAC 权限矩阵

| 角色 | 资源 | 操作 | 权限 |
| --- | --- | --- | --- |
| 匿名用户 | /health、/readyz | GET | 允许（探针） |
| 已认证员工 | 业务只读接口 | GET | 允许 |
| 业务运营 | 业务读写接口 | GET/POST/PUT | 允许 |
| 管理员 | 全部业务接口 + 配置 | * | 允许（需审批） |
| 系统服务（mTLS） | 内部 API | GET/POST | 允许（限白名单服务） |
| 外部合作方 | 开放 API | GET（限流） | 允许（配额限制） |

## 6. 认证与授权机制说明

- 用户认证：统一由 SM-IAM 完成，签发短期 JWT（SM-ERP 仅 IAM 持有 SM_JWT_SECRET 用于验签）。
- 服务间认证：调用方携带 SM_INTERNAL_API_KEY，被调方校验白名单。
- 授权：业务层基于角色矩阵鉴权，K8s 层基于 ServiceAccount + RBAC。

## 7. 审计日志要求

- 记录：时间、身份、源 IP、操作、资源、结果、trace_id。
- 留存：在线 30 天，归档 ≥ 6 个月，审计中心只读。
- 告警：特权操作、批量导出、异常时段访问触发告警。

## 8. 漏洞管理流程

1. 依赖/镜像漏洞由 Trivy + Dependabot 自动扫描，阻断高危（CVSS≥7.0）发布。
2. 每月一次全量漏洞复盘，CAB 评审修复优先级。
3. 应急漏洞 24 小时内出缓解方案，72 小时内修复。
