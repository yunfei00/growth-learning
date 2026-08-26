# V1 角色与隐私矩阵

本矩阵描述 Growth Learning V1 的后端授权边界。页面隐藏不是授权；每次私有资源请求都必须从当前会话重新验证 `FamilyMember`、`TeacherChildRelation` 或 `system_role`。`R`=读取，`W`=产生受控证据/内容，`M`=管理配置，`限`=仅下述范围，`—`=拒绝。

| 角色 | Child | Learning / Mastery | Story / Reading | Science / Media | Growth / Book | Teacher | Course | Family Export | 平台账号/邀请 | Admin Catalog |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 未登录 | — | — | — | — | — | — | — | — | 仅邀请码注册/登录 | — |
| 普通已登录、无家庭 | — | — | — | — | — | 可开启自己的教师档案 | 仅公共系统目录 | — | 仅自己的账号安全 | — |
| Family Admin | R/W/M | R/W/M（证据驱动） | R/W/M | R/W/M | R/W/M | 授权、撤销、查看 | 家庭路径与家庭课 M | R/W | 仅自己的账号安全 | — |
| Companion | R | R/W（陪伴） | R/W（陪伴） | R/W（陪伴） | R；按 API 追加家庭记录 | 不能授权/撤销 | R | — | 仅自己的账号安全 | — |
| Teacher、无授权 | — | — | — | — | — | 仅自己的教师资料/班级 | 仅自己的教师课程 | — | 仅自己的账号安全 | — |
| Teacher、active relation | 限 R | 限 R/W：自己的任务与逐项 evidence | 限任务阅读 | — | 仅写自己的原文观察；不能读全时间线 | 限自己的学生/班级/任务 | 限自己的教师课程 | — | 仅自己的账号安全 | — |
| Teacher、revoked | — | 历史仍归家庭，教师立即拒绝 | — | — | — | 仅自己的非孩子资料 | 仅自己的教师课程 | — | 仅自己的账号安全 | — |
| System Admin | — | — | — | — | — | 无隐式孩子权限 | 系统课程 M | — | 账号元数据/状态、家庭数量、平台邀请码 M | 系统字库/实验目录 M |

## 强制边界

- Teacher 是家庭外部、逐孩子授权角色，不是 `FamilyMember`；授权老大不代表授权兄弟姐妹。
- System Admin 只管理系统内容，不获得家庭、孩子、故事、实验、成长档案或导出读取权；若该账号同时是家庭成员，家庭权限仅来自对应 membership。
- System Admin 可知道某用户属于几个家庭，但用户管理 DTO 不返回家庭名称、孩子、学习、故事、媒体或成长内容。
- Companion 可以陪伴产生原始学习、阅读和科学证据，但不能修改家庭关键设置、授权老师、管理家庭课程路径或导出全家数据。
- Family Admin 可以邀请/移除成人、修改 `admin/companion` 权限、维护逐孩子关系及新增/编辑/归档孩子；系统拒绝移除或降级最后一个 admin。
- 成人的爸爸/妈妈/监护人关系只用于家庭展示，绝不推导权限。两个家长可以同时是 admin；同一成人对兄弟姐妹可以有不同关系。
- 被移除的成人下一次家庭/孩子请求立即失效；其已有 User 与历史 evidence actor 原样保留。
- 课程完成、故事阅读和科学 exposure 都不能直接写“认识/正确”；`ChildKnowledgeState` 只由统一 evidence 算法推导。
- 跨家庭/跨孩子/跨老师对象使用后端归属查询拒绝，通常以 `404` 隐藏资源存在性。

这些边界由 `test_families.py`、`test_family_collaboration.py`、`test_household_cleanup.py`、`test_character_learning.py`、`test_story_generation_and_reading.py`、`test_science_lab.py`、`test_growth_archive.py`、`test_teacher_collaboration.py`、`test_courses_and_catalog.py` 与 `test_child_experience.py` 共同覆盖。
