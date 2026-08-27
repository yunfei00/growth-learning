# Pinyin Audio Strategy

## 原则

音频是拼音学习主交互。系统禁止把 Latin `b`、`p`、`zh` 直接交给默认 Speech Synthesis，因为浏览器可能用英文读成 “bee”等错误声音。

`PinyinAudioProvider` 的选择顺序：

1. `audio_key` 指向的 curated/static 真人或高质量正式录音；
2. 后续可配置的受控音频资源；
3. 只在 `pronunciation_cue` 含汉字时，使用 `zh-CN` TTS 播放中文线索；
4. 若既无正式音频也无安全中文线索，明确返回 `missing`，提示家长示范。

V1 的 68 个正式条目都有中文线索，例如页面显示 `b`，声音文本为“玻，玻璃的玻。”。前端安全解析器再次拒绝 Latin-only fallback，形成服务端与浏览器双重门禁。

## 私有正式音频

`audio_key` 可维护为 `pinyin/b.mp3` 等对象键。替换或增加音频不会改变 KnowledgePoint ID、canonical key、课程映射或孩子历史。音频内容经 `/api/v1/pinyin/items/{point_id}/audio` 鉴权读取，MinIO bucket 不公开，响应使用 private cache。

Admin 将每项明确标成：正式音频、TTS fallback 或缺失。生产不会静默退化成英文字母音。

## 可访问性与失败行为

主播放、重新播放和听力题重播都有包含目标符号的 `aria-label`。音频失败只显示可重试提示，不阻塞学习页、记录浏览或家长手动示范，也不会因为播放成功自动写 Assessment correct。
