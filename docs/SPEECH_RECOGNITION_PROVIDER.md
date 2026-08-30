# Speech Recognition Provider Contract

前端 provider 是可替换边界，不把浏览器事件对象带进业务组件：

```ts
start({ lang, timeoutMs }) -> {
  transcript, alternatives, confidence, confidence_available,
  language, provider
}
stop() / abort()
```

V1 使用浏览器内置识别，`zh-CN`、单次非连续识别、最多 5 个候选、5 秒超时。组件卸载、切换孩子、切换目标或播放提示时必须 `abort()`。TTS 和识别不并行。

`confidence` 仅用于审计展示和后续实验，不作为固定阈值掌握判断；provider 超时、`no-speech`、`not-allowed`、`network` 都要转换为可恢复错误。
