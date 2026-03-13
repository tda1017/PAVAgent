# 长视频分段分析 + 智能合并 (Map-Reduce) - Task List

## Implementation Tasks

- [ ] 1. **新增 Prompt 常量** (`server/models.py`)
    - [ ] 1.1. 新增 `VIDEO_SEGMENT_HINT` 模板
        - *Goal*: 为分段分析提供上下文提示，让模型知道当前段在全局的位置
        - *Details*: 模板包含 `{seg_index}`, `{total_segments}`, `{start_sec}`, `{end_sec}` 四个占位符。追加到 VIDEO_V1 prompt 末尾。内容见设计文档 §3
        - *File*: `server/models.py`
    - [ ] 1.2. 新增 `VIDEO_MERGE_V1` 合并 prompt
        - *Goal*: 指导模型将多段分析结果综合为一份完整报告
        - *Details*: 包含 `{segment_results_json}` 占位符。输出 schema 必须与 VIDEO_V1 完全一致。内容见设计文档 §3
        - *File*: `server/models.py`
    - [ ] 1.3. 更新 `__all__` 导出列表
        - *Details*: 添加 `VIDEO_SEGMENT_HINT` 和 `VIDEO_MERGE_V1`

- [ ] 2. **基类新增 `merge_segments` 方法** (`tests/models/base.py`)
    - [ ] 2.1. 在 `VisionModel` 中新增非抽象方法 `merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict`
        - *Goal*: 提供合并接口，各子类覆写
        - *Details*: 默认实现抛 `NotImplementedError(f"{self.name} 未实现 merge_segments")`。**不加 `@abstractmethod`**，避免破坏现有子类
        - *File*: `tests/models/base.py`

- [ ] 3. **各模型实现 `merge_segments`**
    - [ ] 3.1. GPT (`tests/models/gpt.py`)
        - *Goal*: 纯文本调用 `self.client.chat.completions.create`
        - *Details*: `messages=[{"role": "user", "content": merge_prompt}]`，`max_tokens=2048`。计时并写入 `_latency_s`。用 `_parse_json` 解析响应
    - [ ] 3.2. Kimi (`tests/models/kimi.py`)
        - *Goal*: 同 GPT，纯文本 OpenAI 兼容调用
        - *Details*: 实现与 GPT 完全相同（都是 OpenAI SDK）
    - [ ] 3.3. QwenModel (`tests/models/qwen.py`)
        - *Goal*: 纯文本 OpenAI 兼容调用
        - *Details*: 实现与 GPT 相同。**QwenOmniModel 继承 QwenModel，无需覆写**
    - [ ] 3.4. Gemini (`tests/models/gemini.py`)
        - *Goal*: 纯文本 `self.client.models.generate_content`
        - *Details*: `contents=[merge_prompt]`。**GeminiFlashImageModel 继承 GeminiModel，无需覆写**
    - [ ] 3.5. Sonnet (`tests/models/sonnet.py`)
        - *Goal*: 纯文本 `self.client.messages.create`
        - *Details*: `messages=[{"role": "user", "content": merge_prompt}]`，`max_tokens=2048`。虽然 sonnet 不支持视频分析（CAPABILITY 中 video=False），但 merge_segments 方法仍需实现以保证接口完整性

- [ ] 4. **视频切片函数** (`server/app.py`)
    - [ ] 4.1. 新增 `_split_video(video_path: Path, segment_sec: int = 60) -> list[tuple[Path, float, float]]`
        - *Goal*: 替代 `_clip_video`，将长视频切成多段
        - *Details*:
            1. 用 `_get_duration` 获取时长
            2. 若 ≤ segment_sec：返回 `[(video_path, 0, duration)]`，不切片
            3. 若 > segment_sec：循环 `ffmpeg -y -ss {start} -t {segment_sec} -i {path} -c copy -movflags +faststart {output}`
            4. 切片命名：`_seg_{i}_{original_name}`，放在 video_path 同目录
            5. 最后一段的 end_sec = min(start + segment_sec, duration)
            6. ffprobe 失败时回退为返回单段 `[(video_path, 0, 0)]`
        - *File*: `server/app.py`
    - [ ] 4.2. 删除 `_clip_video` 函数
        - *Details*: 完全移除，不再使用
    - [ ] 4.3. 删除 `MAX_VIDEO_SECONDS` 常量
        - *Details*: 不再需要，切片长度由 `_split_video` 的 `segment_sec` 参数控制（默认 60）

- [ ] 5. **改造调度逻辑** (`server/app.py`)
    - [ ] 5.1. `_run_and_cleanup` 改造
        - *Goal*: 用 `_split_video` 替代 `_clip_video`
        - *Details*:
            - 视频时调 `_split_video` 得到 segments list
            - 将 segments 传给 `run_all_models`
            - 非视频时 segments = None
    - [ ] 5.2. `run_all_models` 签名变更
        - *Goal*: 透传 segments 参数
        - *Details*: 新增 `segments=None` 参数，传递给 `run_single_model`
    - [ ] 5.3. `run_single_model` 改造 — 核心 Map-Reduce 逻辑
        - *Goal*: 支持分段分析 + 合并
        - *Details*:
            1. 新增 `segments=None` 参数
            2. `file_type == "image"`：原流程不变
            3. `segments is None or len(segments) == 1`：原流程不变（短视频）
            4. `len(segments) > 1`：**Map-Reduce 流程**
                - 循环每段：推送 progress → 构造 seg_prompt（prompt + VIDEO_SEGMENT_HINT.format(...)）→ `analyze_video`
                - 单段失败时捕获异常，记录 `{"_error": str(e), "_segment": i}` 到 seg_results，继续下一段
                - 所有段都失败 → 抛异常走 error 路径
                - Map 完成后推送 `progress: "合并中"`
                - 构造 merge_prompt（清除 `_` 前缀字段后序列化）
                - 调 `model.merge_segments(seg_results, merge_prompt)`
                - 累计延迟 = Σ各段延迟 + 合并延迟
                - 合并失败时降级为返回第一个成功段的结果
    - [ ] 5.4. 更新 import
        - *Details*: 从 `server.models` 新增导入 `VIDEO_SEGMENT_HINT`, `VIDEO_MERGE_V1`

- [ ] 6. **前端进度显示** (`frontend/src/components/ModelCard.vue`)
    - [ ] 6.1. 修改 running 状态文案
        - *Goal*: 长视频分析时显示分段进度
        - *Details*: 将 `分析中...` 改为 `{{ state.progress ? \`分析中 (${state.progress})...\` : '分析中...' }}`。无 progress 字段时保持原有文案
        - *File*: `frontend/src/components/ModelCard.vue`
    - [ ] 6.2. 重新构建前端
        - *Details*: `cd frontend && npm run build`，更新 `dist/` 目录

- [ ] 7. **手工验证**
    - [ ] 7.1. 短视频兼容性测试：上传 ≤60s 视频 → 不切片 → 结果与改动前一致
    - [ ] 7.2. 长视频分段测试：上传 >60s 视频 → 切片 → 分段分析 → 合并 → 返回完整结果
    - [ ] 7.3. 绝对时间戳验证：合并结果 events 中存在 timestamp_sec > 60 的事件
    - [ ] 7.4. 全局 summary 验证：summary 提及视频后半段内容
    - [ ] 7.5. SSE 进度验证：DevTools 中确认收到 progress 字段
    - [ ] 7.6. 前端进度文案：ModelCard 显示 `分析中 (2/7)...`
    - [ ] 7.7. 图片不受影响：上传图片 → 行为与改动前一致

## Task Dependencies

- Task 1（Prompt 常量）和 Task 2（基类方法）无依赖，可并行
- Task 3（各模型 merge_segments）依赖 Task 2 完成
- Task 4（切片函数）无依赖，可与 Task 1-3 并行
- Task 5（调度逻辑改造）依赖 Task 1, 3, 4 全部完成
- Task 6（前端）无依赖，可与 Task 1-5 并行
- Task 7（验证）依赖 Task 5, 6 全部完成

```
Task 1 (prompts) ──┐
Task 2 (base)   ───┤
                    ├──→ Task 3 (model impls) ──┐
Task 4 (split)  ────────────────────────────────┼──→ Task 5 (调度) ──→ Task 7 (验证)
Task 6 (前端)   ─────────────────────────────────────────────────────→ Task 7 (验证)
```
