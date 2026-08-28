# English Visual Content Policy

英语视觉用于建立“声音 ↔ 物体/动作/场景”的理解，不是装饰。解析顺序为项目静态图片、确定性
颜色/图形、人工 icon key、Emoji fallback。每项保存 source、license 与可选 attribution；不在运行时
抓取搜索引擎图片，也不把孩子隐私发给外部视觉服务。

首批项目静态 SVG 覆盖 cat、dog、apple、ball、sun、moon；颜色和基础图形由 CSS 确定渲染。Emoji
只能作为可替换回退，架构通过 `image_key`、`visual_key` 和 `visual_type` 支持后续人工替换高质量
素材。Assessment 的可见/无障碍标签使用“选项 1/2/3”，不能通过 alt 泄露正确答案。

管理员可以按 static/fallback/missing 筛选并维护资源；归档内容不会进入儿童目录，但历史 attempt
仍保留当时视觉快照。
