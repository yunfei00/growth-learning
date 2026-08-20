# Changelog

## 1.0.0 - 2026-08-20

Growth Learning V1 提供以下基于真实、可追溯证据的家庭学习与成长闭环：

- Family：成人账号、家庭、孩子、Family Admin / Companion 与多孩子隔离。
- Learning：canonical KnowledgePoint、1,200 字 versioned catalog、统一学习记录与可重算掌握状态。
- Review / Assessment：1/3/7/14/30/60/90 天自适应复习、今日计划、周测/月测、受控 unseen sampling 和 catalog-bounded 识字估算。
- Reading：掌握度约束的结构化 AI 故事 pipeline、程序覆盖率分析、不可变 StoryVersion、可恢复阅读与理解题；Provider 可选。
- Science：家庭材料推荐、版本化实验、孩子原话、可恢复 session、私有媒体与成长卡。
- Growth Archive：统一时间线、不可变报告/成长书、浏览器打印和 `growth-learning-export-v1` 私有导出。
- Teacher：家长逐孩子授权/即时撤销、轻量班级、任务、canonical evidence、原文观察和无排名统计。
- Courses：通用 Course → Unit → Activity → KnowledgePoint、系统/家庭/老师/教材参考课程和只复制路径的兄弟配置。
- Child Experience：Parent/Child 双模式、统一 Today、真实成长树、版本化成就与正向-only 星星账本。
- Privacy：后端 IDOR 防护、Teacher/System Admin 最小权限、私有 MinIO、HttpOnly session 与短期私有导出。
- Operations：幂等 migration/import/deploy、带 revision 的健康信息、PostgreSQL + 私有对象备份、隔离恢复手册。

自托管升级必须先备份，在 CI 生成的同一 revision 镜像上执行 `alembic upgrade head`，并按 `docs/BACKUP_RESTORE.md` 验证恢复。AI 故事生成需要单独的服务器运行时 Provider 配置。
