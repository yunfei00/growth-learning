# 生产备份与恢复演练

`gl-backup` 为 PostgreSQL 和私有对象存储生成可审计的备份材料，不停止现有服务，不删除 volume，也不执行 Docker prune。

## 创建备份

在部署目录运行：

```bash
gl-backup
```

默认写入 `/opt/backups/growth-learning/<UTC timestamp>/`：

- PostgreSQL custom-format dump；
- MinIO bucket 的对象清单（键、大小、ETag、时间）；
- Compose 服务状态；
- SHA-256 校验文件和备份 manifest。

保留天数由 `GROWTH_LEARNING_BACKUP_RETENTION_DAYS` 控制，默认 7 天。清理只允许发生在已验证的 `/opt/backups/growth-learning` 子目录中。

对象清单不是二进制媒体副本。生产环境必须同时对 MinIO named volume 做主机快照，或用 `mc mirror` 镜像到独立、受访问控制且加密的备份存储。没有对象副本的数据库 dump 不能恢复家庭照片、视频和导出文件。

## 恢复前检查

1. 记录目标环境 commit、Alembic revision 和 Compose 状态。
2. 先对目标环境做一次新的可恢复备份。
3. 在隔离目录执行 `sha256sum --check checksums.sha256`。
4. 检查 dump 的对象列表，不要把不可信 ZIP/SQL 直接导入生产。
5. 确认 MinIO 对象副本与 manifest 的 bucket、键和大小一致。
6. 先在隔离 PostgreSQL/MinIO 环境演练，再安排生产维护窗口。

## PostgreSQL 恢复演练

恢复操作是显式的人工运维流程，不由 Web API 或 `gl-update` 自动执行：

```bash
pg_restore --list postgres.dump > restore.list
createdb growth_learning_restore_drill
pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname growth_learning_restore_drill postgres.dump
```

随后在隔离实例验证 `alembic_version`、核心表数量、外键、应用健康检查和随机抽样家庭边界。只有演练通过并有维护窗口时，才按照 PostgreSQL 官方流程切换生产数据库；禁止在运行中的生产库直接使用清库参数。

## MinIO 恢复演练

将对象副本恢复到隔离 bucket，按备份 manifest 校验对象数量、大小和抽样 SHA/ETag，再使用隔离应用确认附件只能通过家庭鉴权 API 读取。不要把 MinIO 端口或 bucket 设置为公网公开。

## 恢复后的验收

- `alembic current` 与部署代码一致；
- PostgreSQL、Redis、MinIO、backend、frontend 全部 healthy；
- `/growth/api/health` 正常；
- 家庭、孩子、学习证据、成长档案与媒体数量符合 manifest；
- 跨家庭和系统管理员隐私测试仍然拒绝；
- 记录演练时间、操作者、备份 ID、结果和差异。
