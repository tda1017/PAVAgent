# 长视频分段分析 + 智能合并 (Map-Reduce) - Requirements Document

当前视频分析只截取前60s，后面内容丢弃。本方案实现完整视频分析：ffmpeg切片 → 各段独立分析(带上下文) → 文本合并。输出schema与单段完全一致，前端零改动。

## Core Features

1. **视频切片（Split）**：将超过 60s 的视频按 60s/段用 `ffmpeg -c copy` 零开销切片
2. **分段分析（Map）**：每个片段独立调用现有 `analyze_video`，prompt 中追加分段上下文（段号、时间偏移），使 timestamp 输出为绝对时间
3. **结果合并（Reduce）**：将所有分段 JSON 结果喂给同一模型的纯文本接口，综合输出一份完整分析报告
4. **SSE 进度推送**：长视频分析时推送分段进度 `"progress": "2/7"`，前端显示 `分析中 (2/7)...`
5. **向后兼容**：≤60s 视频走原有流程，零变更；合并结果 schema 与 VIDEO_V1 完全一致

## User Stories

- 作为用户，我上传一段 6 分钟的视频，希望获得完整的分析结果而不是只看到前 60 秒的内容
- 作为用户，我在长视频分析过程中希望看到进度提示（如 "分析中 2/7..."），而不是只有一个无限旋转的 spinner
- 作为用户，我上传短视频（≤60s）时，体验与现在完全一致，没有任何退化

## Acceptance Criteria

- [ ] 上传 ≤60s 视频 → 不切片，行为与当前完全一致
- [ ] 上传 >60s 视频 → 自动切片（60s/段），每段独立分析，最终返回合并结果
- [ ] 合并结果的 JSON schema 与 VIDEO_V1 完全一致（含 importance_score, category, events, summary, key_moment）
- [ ] events 中的 timestamp_sec 为相对于完整视频的绝对时间（非段内相对时间）
- [ ] summary 是全局概括，不是各段 summary 的简单拼接
- [ ] key_moment 从所有段中选出最重要的一刻
- [ ] importance_score 基于全局内容评估
- [ ] SSE 推送包含分段进度信息 `{"model": "xxx", "status": "running", "progress": "2/7"}`
- [ ] 前端 ModelCard 在 running 状态下显示分段进度文案
- [ ] 所有支持视频的模型（kimi, gemini, gemini_flash_image, qwen, qwen_omni, gpt）均支持分段分析和合并
- [ ] sonnet（不支持视频）保持 skip 行为不变
- [ ] 单个分段分析失败不影响其他分段，失败段跳过，合并时标注
- [ ] 删除旧的 `_clip_video` 函数，用 `_split_video` 替代

## Non-functional Requirements

- **性能**：切片用 `-c copy` 零转码，毫秒级完成；分段分析串行执行（同一模型内），避免 API 并发限制
- **超时**：长视频的总超时 = 段数 × 300s（单段超时），防止无限等待
- **临时文件**：切片产生的临时文件在分析完成后统一清理
- **内存**：合并阶段仅传递文本 JSON，不涉及视频数据，内存占用极低
- **兼容性**：依赖 ffmpeg/ffprobe（已在当前环境中使用），无新外部依赖
