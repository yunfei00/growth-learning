# Pinyin Canonical Catalog

## 版本与来源

正式版本为 `pinyin-foundation-v1`，由项目人工维护，固定顺序、来源 metadata 和导入时间保存在 `pinyin_catalog_releases`。导入按 canonical key upsert，重复执行不新建 KnowledgePoint，也不改变既有 UUID。

所有条目 `subject=chinese`，类型和 canonical key 如下：

- 23 声母，`pinyin_initial`：`b p m f d t n l g k h j q x zh ch sh r z c s y w`；键形如 `chinese:pinyin:initial:b`。
- 24 韵母，`pinyin_final`：`a o e i u ü ai ei ui ao ou iu ie üe er an en in un ün ang eng ing ong`；键形如 `chinese:pinyin:final:ang`。
- 5 声调，`pinyin_tone`：第一、二、三、四、轻声；键固定为 `chinese:pinyin:tone:1..4` 和 `chinese:pinyin:tone:neutral`。
- 16 整体认读，`pinyin_syllable`：`zhi chi shi ri zi ci si yi wu yu ye yue yuan yin yun ying`；metadata 含 `whole_recognition=true`。

## 拼音规范化

领域 helper 统一 NFC、小写，并把 `v`、`u:` 规范成 `ü`；儿童界面永远显示 `ü`。标调函数覆盖六个元音及常见复韵母规则：优先 `a`、再 `e`、`ou` 标在 `o`，其余标在最后一个可标元音。

`j/q/x + ü` 保存 underlying final 为 `ü`，显示时省略两点：`j + ü → ju`、`q + üe → que`、`x + ün → xun`。规则信息保存在 practice domain 字段和 metadata，不因显示拼写丢失。

## 易混淆与练习

通过双向 `KnowledgeRelation.confusing` 导入 8 对、16 条关系：`b/p`、`d/t`、`g/k`、`z/c`、`zh/ch`、`an/ang`、`en/eng`、`in/ing`。

V1 只建立 18 个小而明确的 `PinyinPracticeItem`，覆盖基本拼读及 `ü` 规则。它们是 practice material，不是数百个都必须达到 Stable 的 canonical syllable KnowledgePoint。

## 课程顺序

系统课程 `拼音启蒙` 有 16 Unit：

1. a o e · 四声初体验
2. i u ü
3. b p m f
4. d t n l
5. g k h
6. j q x
7. z c s
8. zh ch sh r
9. y w
10. ai ei ui
11. ao ou iu
12. ie üe er
13. an en in un ün
14. ang eng ing ong
15. 整体认读音节
16. 综合拼读
