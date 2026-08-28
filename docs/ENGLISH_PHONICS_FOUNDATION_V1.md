# English Phonics Foundation V1

Phonics 与 letter name 分开建模。V1 包含 5 个短元音、19 个基础辅音开头音和 20 个受控 CVC
blending 项，共 44 个 `english_phonics` KnowledgePoint；不把全部可能单词或音标组合展开为课程。

单音素项的安全播放优先正式 phoneme；缺失时使用人工示例词，例如 m → moon，并提示孩子关注
目标位置。CVC 项保存 segments，练习把 c · a · t 连成 cat，再选择完整单词。系统不声称所有英语词
都能由当前规则解码，也不在 Phase 19 建完整 sight-word 或音标课程。

`english-phonics-v1` 初期使用 sound_recognition；一旦存在 blending/decoding evidence，掌握投影以
decoding 为核心。同一天重复无法 stable，letter-name evidence 也不能推进 phonics mastery。
