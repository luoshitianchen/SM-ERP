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

访问 `http://127.0.0.1:8100/`。初始账号：`admin`，初始密码：`admin`。

知识库对接地址：`POST /api/auth/login`，请求体：

```json
{"username":"ERP账号","password":"ERP密码"}
```

响应包含 `id`、`name`、`department`、`role`。
