# 家长授权的老师协作

Phase 9 提供的是家庭学习平台中的有限教学协作，不是学校管理系统。老师身份、家庭身份和平台管理员身份彼此独立；任何老师访问具体孩子前，都必须由该孩子家庭的 `FamilyMember.admin` 明确授权。

## 身份与授权

- 登录用户主动开启教师模式后创建 `TeacherProfile`。教师模式本身不授予任何孩子权限。
- `teacher_code` 和 `class_code` 使用加密安全随机数生成，opaque、唯一且不可预测；公开查询只返回老师显示名、可选机构与简介，不支持按邮箱搜索。
- 家长输入连接码、查看最少必要资料并确认后，服务端才创建 `TeacherChildRelation`。输入班级码还会创建该孩子的 `ClassroomMembership`。
- 只有 Family Admin 能授权、撤销、加入或退出班级。Companion 可以陪孩子完成已发布任务，但不能改变授权。
- 撤销是持久化的实时状态。每个教师 API 请求都重新验证 active relation，不依赖延迟缓存；历史任务、原始 evidence 和观察保留给家庭。
- System Admin 不自动成为老师，也不因平台权限获得家庭、孩子、故事、科学媒体、成长册、报告或导出的读取权。

## 教师可见范围

教师专用 DTO 只包含：孩子显示名/昵称、粗粒度年龄段、该老师任务涉及的汉字掌握状态、该老师任务进度与结果、该老师自己的观察。

明确排除：家庭成员与邮箱、兄弟姐妹、家庭手工成长记录、完整时间线、完整故事书、科学私人媒体、成长报告、成长册、家庭导出以及其他老师的班级和任务。只授权一个孩子不会推导同家庭其他孩子的权限。

## 班级与任务

`Classroom` 是老师拥有的轻量分组。没有学校、年级、排课、考勤、收费、批量学生导入或共享教师团队。孩子只能由家长确认加入。

任务支持：

- `character_learning`：使用规范 `KnowledgePoint`，完成时写入现有 `LearningSession` / `LearningRecord`，source 为 `teacher_assignment`。
- `character_review`：同样复用学习 evidence，不创建教师专属掌握度。
- `recognition_check`：复用 `AssessmentSession` / `AssessmentItem`，逐项保存 `correct`、`hinted_correct`、`uncertain`、`incorrect`，evaluator 为实际操作用户。
- `reading`：复用已经完成且属于该孩子的 `ReadingSession`；不会绕过故事覆盖分析、内容安全或隐私流程。
- `freeform_instruction`：保存线下任务完成状态，不伪造识字 evidence。

`TeacherAssignmentProgress` 保存 pending / in_progress / completed，并根据 due time 派生 overdue。恢复请求返回同一 canonical session；逐项 evidence 的既有唯一约束与事务保证重复提交不会新增重复条目。`ChildKnowledgeState` 仍只由统一、版本化 mastery 算法根据原始 evidence 更新，老师没有直接修改掌握度的接口。

## 教学观察与成长档案

`TeacherObservation` 保存老师原文、分类、时间和可选的班级、任务、KnowledgePoint 关联。分类限制为 recognition、reading、expression、learning_habit、participation、other，不生成智力、人格、心理或综合能力分数。

观察在同一事务中投影为 `GrowthEvent(source_type=teacher)`，便于家长在成长时间线查看。该投影是单向的：老师不会因此获得完整家庭时间线权限。

## 班级统计

任务结果只提供总人数、pending、in progress、completed、overdue、四类 outcome 数和常见错误字。API 固定返回 `ranking_enabled=false`，不提供儿童排名、总分或全局能力分。

## 保留边界

本阶段不包含邮件邀请、学校组织结构、课程编辑器、聊天、直播、视频会议、排行榜、数学或英语模块。所有外键采用限制删除或保留历史的生命周期状态；没有面向用户的物理删除 API。
