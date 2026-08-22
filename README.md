# SM ERP

**正式版：** [v2.0.0 发布说明与源码下载](https://github.com/luoshitianchen/SM-ERP/releases/tag/v2.0.0)

独立的企业资源与身份管理系统，为 `SM Knowledge Bot` 提供 ERP 登录、员工、部门和角色信息。

## 启动

```powershell
git clone https://github.com/luoshitianchen/SM-ERP.git
cd SM-ERP
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

运行测试使用独立开发依赖：`pip install -r requirements-dev.txt && pytest tests -q`。

复制 `.env.example` 后，先设置随机的 `ERP_SM4_KEY_HEX` 与 `ERP_BOOTSTRAP_PASSWORD`，再启动服务。系统没有内置默认密钥或默认管理员密码。

知识库对接地址：`POST /api/auth/login`，请求体：

```json
{"username":"ERP账号","password":"ERP密码"}
```

响应包含 `id`、`name`、`department`、`role`。

### 集成密钥轮换

ERP 支持使用 `ERP_KNOWLEDGE_BOT_INTEGRATION_KEYS=新密钥,旧密钥` 进行短期双密钥轮换；知识库先切换到新密钥，确认认证请求稳定后，从 ERP 配置中移除旧密钥。密钥仅由部署平台或 KMS 注入，禁止写入仓库、日志或前端。

## 管理能力

- scrypt 密码哈希与账号停用；
- 部门与组织单元管理；
- 员工账号、部门与角色管理；
- 审计日志；
- 企业管理工作台。

## 国密安全

- 账号口令使用 SM3 迭代盐化派生，不保存明文；
- 审计详情使用 SM4-CBC 加密，并以 SM3 完整性校验保护；
- 在 `.env` 配置 `ERP_SM4_KEY_HEX`，缺失密钥或管理员初始化密码时系统会拒绝启动；生产环境应由 KMS/HSM 或部署平台的密钥管理能力注入。

## 生产部署清单

管理员审计查询支持分页和筛选：`GET /api/audit-logs?limit=50&offset=0&action=auth.login&since=2026-01-01T00:00:00Z`。接口只返回管理员可见的审计记录，单页最多 100 条。

1. 复制 `.env.example` 为 `.env`，填入 KMS/HSM 提供的 SM4 密钥、强管理员密码和集成密钥。
2. 将 `ERP_ENV` 保持为 `production`，生产启动会拒绝示例密钥与示例初始化密码。
3. 使用反向代理提供 HTTPS，并设置受信任代理来源；应用容器默认以非 root 用户运行。
4. 执行 `docker compose up --build -d`，通过 `/health` 监控实例状态。

## 网络暴露控制

Docker 默认仅监听 `127.0.0.1:8100`，不会直接暴露到公网。对外访问应通过企业 VPN、零信任网关或反向代理，并设置 IP 白名单、TLS 与身份认证。生产环境保持 `ERP_ENABLE_DOCS=false`，并将实际域名加入 `ERP_ALLOWED_HOSTS`。

仓库提供 [内网 Nginx + mTLS 示例](deploy/nginx/internal.conf.example)：它同样只监听回环地址，并要求企业 CA 签发的客户端证书。替换示例域名和证书路径后，先通过 `nginx -t` 校验，再由企业网络团队将 VPN/零信任入口转发至该监听地址；不要直接开放应用容器端口或 Nginx 监听端口到公网。

## 备份与恢复

执行 `./backup.ps1` 可在 `backup/` 目录生成 SQLite 一致性备份。备份目录不纳入 Git；应将备份转存到加密、受访问控制的企业备份存储，并定期进行恢复演练。

## v2.1 企业维护升级
- 统一版本提升到 `2.1.0`，提供 `/health` 与 `/readyz` 运维探针。
- 国密能力保持 SM3 口令派生、SM4-CBC 敏感审计字段加密、SM3 MAC 完整性校验。
- 登录、集成认证、会话、CSRF、审计分页继续按企业最小权限模型执行。
- 推荐安装方式：

```powershell
git clone https://github.com/luoshitianchen/SM-ERP.git
cd SM-ERP
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

### v2.1 运维观测接口
管理员登录后可访问：

```powershell
Invoke-RestMethod http://127.0.0.1:8100/api/ops/metrics -WebSession $session
```

返回请求总量、错误总量、平均延迟，便于接入企业监控平台或桌面融合门户。

### v2.1 本地质量门禁
提交前推荐执行：

```powershell
.\quality.ps1
```

如只进行快速回归测试：

```powershell
.\quality.ps1 -SkipAudit
```

## v2.2 全量升级
- 服务版本统一提升到 `2.2.0`。
- Web 控制台登录后自动保存 CSRF Token，员工、部门、审计等受保护操作可完成会话校验。
- 新增“运行状态”菜单，直接展示 `/api/ops/metrics` 请求总量、错误总量和平均延迟。

## v2.3 安全防护增强
- 服务版本统一提升到 `2.3.0`。
- 新增全局 API 速率限制，登录与集成认证限流之外进一步保护普通接口。
- 速率限制命中后返回 `429` 和 `Retry-After`。
- CSP 增加 `connect-src`、`img-src`、`form-action`。
- 管理员审计查询默认不返回 `detail` 字段，并减少员工创建审计中的账号名暴露。


## v2.4 全量国密同步
- 核心服务同步升级并提供 `/api/crypto/status`。
- Knowledge Bot 额外提供 `/api/crypto/sm3` 摘要接口。
- 国密密钥通过环境变量或 KMS/HSM 注入。


## 2026-08-22 维护记录
- 完成源码编译检查、单元测试和工作区状态检查。
- 保持安全响应头、TrustedHost、限流、请求大小限制、国密 SM3/SM4 与内部令牌控制。
- 维护建议：生产环境通过 KMS/HSM 注入密钥，依赖项目全部启动后再执行融合门户整体健康检查。
