# Phase 14 平台账号准入与安全

Growth Learning 生产环境默认 `REGISTRATION_MODE=invite_only`。公开注册页面仍可访问，但没有有效平台邀请码时，后端事务不会创建 User。`closed` 会完全关闭新账号创建；`approval` 与 `open` 仅保留配置枚举，其中生产当前不启用。

## 邀请码

- `PlatformInvitation` 只服务 `purpose=create_account`；家庭加入邀请留给 Phase 15。
- 创建时使用 `secrets.token_bytes(15)` 产生 120 bit 随机值，再编码为 `GL-...`。
- 数据库只保存使用 `INVITATION_CODE_SECRET`（未配置时使用 `AUTH_SECRET`）计算的 HMAC-SHA256、不可逆提示前缀和使用边界。
- 完整邀请码只出现在创建成功响应和 CLI 输出中一次；列表永不返回完整值或 `code_hash`。
- 注册通过 `SELECT ... FOR UPDATE` 锁定邀请码行，在同一事务中校验状态、邮箱、创建 User、增加 `used_count` 和写审计。User 唯一约束失败会回滚整个事务，不消费邀请码。
- 状态由后端返回：`active`、`used`、`exhausted`、`expired`、`revoked`。前端显示不是安全判断来源。

## User 生命周期与会话

`account_status` 是唯一权威状态：`active`、`suspended`、`disabled`。兼容字段 `is_active` 由所有写操作同步，数据库约束要求两者一致。迁移将已有 User 标记为 `active + legacy`，不建立伪造的邀请码关系。

JWT Cookie 携带 `session_version`。每个受保护请求仍从数据库读取 User，并同时验证：

1. `account_status == active`
2. token version 等于 User `session_version`

暂停、禁用、修改密码、管理员重置密码和“退出所有设备”都会增加版本。暂停后的旧 Cookie 下一次请求立即返回 401；改密会给当前设备签发新版本 Cookie，其他设备失效。

## 管理员边界与审计

System Admin 可查看账号元数据、家庭数量，搜索/分页用户，暂停/恢复/禁用账号，并创建/撤销平台邀请码。它不会获得 FamilyMember，因此不能读取孩子、学习、故事、实验、照片或成长档案。

`platform_audit_logs` 至少保存邀请创建/撤销、注册、暂停/恢复、改密和退出全部设备。metadata 禁止包含密码、邀请码明文、JWT 或运行时 secret。

## 限流与恢复 CLI

登录和注册使用 Redis 固定窗口计数；Redis 短暂异常时使用有界进程内计数并记录服务错误，不记录凭据。默认每个客户端 15 分钟内登录 10 次、注册 5 次。

服务器镜像安装 `gl-admin`：

```bash
gl-admin list-users [--search TEXT] [--status active|suspended|disabled]
gl-admin suspend-user --email user@example.com
gl-admin activate-user --email user@example.com
gl-admin create-invitation --created-by-email admin@example.com \
  --expires-days 7 --max-uses 1 [--email invited@example.com]
gl-admin reset-password --email admin@example.com
```

密码从隐藏终端输入或标准输入读取，不允许命令行密码参数。管理员密码重置增加 `session_version`，旧会话全部失效。当前没有邮件系统，因此页面不展示虚假的邮件找回密码功能。

## 生产配置

```dotenv
REGISTRATION_MODE=invite_only
INVITATION_CODE_SECRET=至少32字符的独立随机密钥
AUTH_RATE_LIMIT_WINDOW_SECONDS=900
AUTH_LOGIN_RATE_LIMIT=10
AUTH_REGISTRATION_RATE_LIMIT=5
```

首次部署前由服务器运维生成密钥并只写入 `.env`。已有生产环境可暂时复用 `AUTH_SECRET` 作为 HMAC key，但应在创建第一枚邀请码前配置独立密钥；更换该密钥会使尚未使用的邀请码失效。
