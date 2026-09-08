# Pinyin Audio Strategy

## 原则

音频是拼音学习主交互。拼音主音频永远表示当前目标音素或音节本身；中文例词和教学说明不得作为主发音。听音 Assessment 不得包含能泄漏答案的中文语义提示。

目录和 API 明确拆分三个概念：

- `target_pronunciation`：孩子当前真正学习、模仿和辨听的目标声音；
- `teaching_cue`：只显示在页面的教学说明；
- `example_text` / `example_pinyin` / `example_focus`：帮助理解或拼读的例子。

`teaching_cue` 继续兼容存放在原 `pronunciation_cue` 数据库列中，但播放提供器永远不读取该列。新增语义存放在版本化 `PinyinItem.metadata_json`，因此不需要数据库迁移，也不改变 KnowledgePoint UUID、canonical key、mastery 或历史 evidence。

`PinyinAudioProvider` 的选择顺序：

1. `audio_key` 指向的 curated/static 真人或高质量正式录音；
2. 明确配置的 target pronunciation 音频；
3. 仅在 `target_audio_text_verified=true` 时使用人工定义的单汉字最短发音代理；
4. 若无可靠目标来源，明确返回 `missing`，提示家长示范。

服务端响应固定带 `purpose=target_pronunciation`；前端只接受这一 purpose，并再次拒绝 Latin-only 或非单汉字的 TTS fallback。Latin-only 字符串不能未经验证直接交给系统 Speech Synthesis，避免 `b` 被读成 “bee”。“玻，玻璃的玻。”等教学句即使误入响应，也会被前端拒绝。

四声当前不使用“阿 / 答 / 马 / 大”等例字代理，因为例字包含额外声母或会把例子误当作目标韵母。没有正式录音时返回 `missing`，而不是播放错误内容。声母、韵母和整体认读现阶段保留人工审核的单汉字最短代理，并应逐步替换为正式录音。

## 私有正式音频

`audio_key` 可维护为 `pinyin/b.mp3` 等对象键。替换或增加音频不会改变 KnowledgePoint ID、canonical key、课程映射或孩子历史。音频内容经 `/api/v1/pinyin/items/{point_id}/audio` 鉴权读取，MinIO bucket 不公开，响应使用 private cache。

Admin 分开维护目标拼音、教学说明、最短目标音代理及其人工确认状态，并将每项明确标成：正式音频、TTS fallback 或缺失。生产不会静默退化成英文字母音。

## 可访问性与失败行为

主播放、重新播放、“跟我读”、听力题开始与重播共用同一个 target playback。若声音为 `missing`，听音选项不会打开，也不会产生没有可靠声音的 Assessment evidence。音频失败不阻塞学习页、记录浏览或家长手动示范，播放成功本身也不会写 Assessment correct。
