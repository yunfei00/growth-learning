# Changelog

## Unreleased - Phase 13

- 统一全部汉字入口为同一单字学习页：明确来源返回、确定性上一个/下一个、语音控件，以及桌面首屏左右布局；系统路径按 current catalog 的全局顺序跨组连续导航 1200 字。
- “识字记录”改为基于 `LearningSession/LearningRecord` 的学习时间轴；仅测评产生的 mastery 状态不再冒充已学习历史，同一汉字多次学习的证据完整保留。
- 系统汉字课程改为单组目录定位和单字入口，不再一次渲染 1200 字；孩子端身份、栏目和家长模式压缩为同一行 Header。
- 完成后的科学实验升级为可长期维护的实验档案：私有媒体持久查看、添加、删除、替换，以及现象、孩子回答和家长备注修订；`completed` 和 `completed_at` 保持不变。
- 五类识字总览可进入具体汉字列表并排序；新增儿童大字号汉字详情页，课程路径中的汉字可点击并恢复返回位置。
- 今日任务完成后仍可查看、朗读和自由练习，重复访问不重复完成、不追加无意义证据、不直接修改掌握度。
- 汉字目录新增人工维护的 `parent_tip`，并复用现有 OpenAI-compatible Provider 提供非权威汉字讲解和实验家长建议。
- Nginx 保持媒体经鉴权 API 访问，放宽私有实验媒体上传体积并关闭代理请求缓冲。

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
