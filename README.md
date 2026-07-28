# SM ERP

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

复制 `.env.example` 后，先设置随机的 `ERP_SM4_KEY_HEX` 与 `ERP_BOOTSTRAP_PASSWORD`，再启动服务。系统没有内置默认密钥或默认管理员密码。

知识库对接地址：`POST /api/auth/login`，请求体：

```json
{"username":"ERP账号","password":"ERP密码"}
```

响应包含 `id`、`name`、`department`、`role`。

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
