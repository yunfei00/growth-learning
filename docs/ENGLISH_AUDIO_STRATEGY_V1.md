# English Audio Strategy V1

英语 V1 固定主要口音 `en-US`。`EnglishAudioProvider` 按正式 curated object、配置资源、受控
speech synthesis/安全示例词、明确 unavailable 的顺序解析。正式对象通过鉴权 API 读取，不暴露
对象存储 key。

普通词、字母名称和短句可以使用 `en-US` TTS。Phonics 禁止把 Latin 字母交给 TTS 后用 “bee”、
“em” 等 letter name 充当音素。缺少正式音素时只能播放人工配置的完整示例词（如 m → moon）并
提示关注开头声音；CVC 可播放完整拼读词。没有安全示例词时按钮明确不可用且学习流程继续可用。

播放不会自动写学习或正确证据；重播次数只进入 attempt metadata，且不算提示。管理员页同时显示
正式音频、TTS/安全回退和 phonics missing 状态，并允许维护 `audio_key`。
