# Character Speech Review V1

儿童语音识字复习是每日复习的一种可选呈现方式。家长在「学习设置」中明确选择 `speech_auto`，否则继续使用家长判断的普通复习；周度和月度检测不会因此自动改变。

## 边界

- 浏览器通过 `SpeechRecognition` / `webkitSpeechRecognition` 取得短暂转写文本。
- 后端只保存 transcript、候选文本、归一化读音、判定和运行元数据，不保存录音、音频对象或声纹。
- ASR 失败、没听清、低质量结果最多重试两次，最终进入 `uncertain`；只有孩子明确点击「我不知道」或说出明确不知道短语才是 `incorrect`。
- 语音结果是 AssessmentItem 的辅助证据，不能直接修改掌握状态、测试成绩或学习记录。掌握度仍由既有算法重算。

## 读音判定

`normalize_pinyin` 统一声调符号、数字声调、大小写和 ü/v 拼写（例如 `dōng`、`dong1` → `dong1`）。每个字以 `ChineseCharacter.pinyin` 为主读音，`accepted_readings` 为人工维护的有限多音字读音集合。字音相同的同音字（如「东」/「冬」）可以匹配；音节相同而声调不同时记为不确定，不按错误处理。

## 数据与接口

- `character_speech_attempts`：每个复习目标按 attempt index 追加一条隐私最小证据。
- `assessment_session_targets.hint_requested_at`：提示动作在提交结果前也能持久化。
- `assessment_overrides`：家长覆盖为追加记录；原始结果保留，当前 AssessmentItem 结果更新后重算复习日程和掌握度。
- `POST /children/{child_id}/planned-assessments/{session_id}/speech-attempts`
- `POST /children/{child_id}/planned-assessments/{session_id}/targets/{knowledge_point_id}/hint`
- `POST /children/{child_id}/assessment-items/{assessment_item_id}/override`

## 可用性降级

设备不支持浏览器语音识别、用户拒绝权限、网络或识别服务失败时，页面提供普通复习模式；正常学习和保存流程不被语音能力阻断。
