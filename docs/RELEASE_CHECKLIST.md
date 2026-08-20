# Growth Learning V1 发布清单

`v1.0.0` 只能在一个唯一 `RELEASE_SHA` 上完成以下门禁。任何代码或文档修改都会产生新候选 SHA，并要求重新运行受影响门禁。标签和 GitHub Release 永远是最后一步。

## 自动门禁

- Backend：Ruff、format、完整 pytest。
- PostgreSQL：空库升级到唯一 Alembic head；Phase 2 fixture additive upgrade。
- Frontend：ESLint、TypeScript、Next.js production build。
- Infrastructure：shell syntax、Compose config、带 revision label 的前后端镜像。
- Repository：tracked-file secret scan；无 export、backup、数据库、媒体或构建缓存。

## 生产门禁

- 服务器 checkout、前后端 image revision、健康响应 revision 均等于 `RELEASE_SHA`。
- `alembic current == alembic heads`，PostgreSQL、Redis、MinIO、backend、frontend healthy。
- `/growth`、`/growth/status`、`/growth/api/health`、`/growth/api/docs` 正常。
- 家庭、识字/复习/周月测、课程、阅读、科学、老师、成长档案、Child Mode 和成就执行 scoped E2E。
- Role/Privacy Matrix、cross-family IDOR、兄弟隔离、Teacher revocation、System Admin household privacy 通过。
- V1 export 的 manifest、JSON/CSV/media、checksums/counts 与 secret exclusion 通过。
- `gl-backup` 新备份通过 checksum；PostgreSQL dump 和 MinIO 对象归档在隔离 namespace 恢复成功。
- 关键 API 重复测量并记录范围；390/768/1280 页面与内部 accessibility sanity 通过。
- scoped acceptance 数据安全清理，真实历史不因清理被修改。

## 发布与回滚

1. 确认 `main` clean、CI green，部署同一 SHA 并完成全部门禁。
2. 创建并推送不可移动的 `v1.0.0` 标签，发布 `Growth Learning v1.0.0`。
3. 标签后再次烟测公网、登录、Parent/Child Home、只读课程和五服务健康。
4. 应用回滚使用已验证旧镜像与 commit；先备份，绝不盲目 `alembic downgrade` 或删除 volume。
5. 发布后缺陷进入普通 bug 与未来 `v1.0.1`；不移动 `v1.0.0`，不创建 Phase 13。

准确的 Release SHA、CI run、生产测量、备份 artifact 与恢复结果记录在 Issue #12 的最终发布证据中，不在仓库伪造动态结果。
