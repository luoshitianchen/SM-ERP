# 企业安全基线

本项目按企业内部系统默认安全要求维护，适用于本地、服务器和容器化部署。

## 访问控制

- 业务接口不得信任客户端传入的用户身份。
- 管理接口应接入 IAM、ERP 或企业 SSO。
- 默认启用角色、部门、岗位和数据范围授权模型。

## 网络暴露

- 默认仅建议绑定内网地址或由 API Gateway 统一转发。
- 生产环境必须配置允许访问的域名或网关地址。
- 不建议服务直接裸露到公网入口。

## 安全响应头

服务应保持以下响应头：

- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: no-referrer
- Permissions-Policy
- Content-Security-Policy
- X-Request-Id

## 审计与日志

- 管理操作、登录、权限变更、数据导入导出必须记录审计日志。
- 日志中不得写入密码、Token、Cookie、密钥、身份证号等敏感信息。
- 每个请求应带有追踪 ID，便于跨服务排查。

## 依赖与供应链

- 依赖固定在 equirements.txt。
- 部署快照记录在 equirements.lock。
- GitHub Actions 使用最新主版本。
- 建议开启 Dependabot、CodeQL、Gitleaks、依赖漏洞扫描。

## 发布要求

- 每次正式发布必须更新 VERSION 和 CHANGELOG.md。
- Release 包应由 CI 自动生成。
- 生产部署前必须通过测试、依赖扫描和 Secret 扫描。
