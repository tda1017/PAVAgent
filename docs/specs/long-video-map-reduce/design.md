# 长视频分段分析 + 智能合并 (Map-Reduce) - Design Document

## Overview

在现有单段视频分析流程的基础上，增加 Map-Reduce 两轮分析。对 >60s 的视频，先 ffmpeg 切片，再逐段调用现有 `analyze_video`（Map），最后用纯文本调用合并所有分段结果（Reduce）。≤60s 视频走原有流程，零变更。

```
长视频 → _split_video (ffmpeg -c copy, 60s/段)
           ↓
         段1, 段2, ..., 段N
           ↓ (串行，同一模型内)
         analyze_video(段i, prompt + segment_hint)  ← Map
           ↓
         [result1, result2, ..., resultN]
           ↓
         merge_segments(results, merge_prompt)       ← Reduce (纯文本)
           ↓
         最终合并结果 (schema = VIDEO_V1)
```

## Architecture

### 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `server/app.py` | 修改 | 删 `_clip_video`，加 `_split_video`；改造 `run_single_model` 支持分段分析+合并；SSE 推送进度 |
| `server/models.py` | 修改 | 新增 `VIDEO_SEGMENT_HINT` 和 `VIDEO_MERGE_V1` 两个 prompt 常量 |
| `tests/models/base.py` | 修改 | 新增 `merge_segments` 方法（非抽象，提供默认实现） |
| `tests/models/gpt.py` | 修改 | 实现 `merge_segments`（OpenAI chat.completions 纯文本调用） |
| `tests/models/kimi.py` | 修改 | 实现 `merge_segments`（OpenAI chat.completions 纯文本调用） |
| `tests/models/qwen.py` | 修改 | QwenModel 实现 `merge_segments`（OpenAI chat.completions）；QwenOmniModel 继承即可 |
| `tests/models/gemini.py` | 修改 | 实现 `merge_segments`（genai generate_content 纯文本） |
| `tests/models/sonnet.py` | 修改 | 实现 `merge_segments`（Anthropic messages 纯文本）；虽然 sonnet 不支持视频，但方法要存在 |
| `frontend/src/components/ModelCard.vue` | 修改 | running 状态下显示 progress 文案 |

### 不改动的部分

- 前端除 ModelCard 的 running 文案外，无任何改动
- `CompareView.vue` 已经能透传 SSE 的任意字段到 modelStates，`progress` 字段自动可用
- `tests/models/__init__.py` 不变
- `server/models.py` 中的 `CAPABILITY` 矩阵不变

## Components and Interfaces

### 1. `_split_video(video_path, segment_sec=60)` — server/app.py

替代现有 `_clip_video`。

```python
def _split_video(video_path: Path, segment_sec: int = 60) -> list[tuple[Path, float, float]]:
    """
    将视频按 segment_sec 切片。

    返回: [(segment_path, start_sec, end_sec), ...]
    - ≤segment_sec 的视频: 返回 [(original_path, 0, duration)]，不切片
    - >segment_sec 的视频: ffmpeg -ss {start} -t {segment_sec} -c copy 逐段切

    切片命名: _seg_0_{name}, _seg_1_{name}, ... 放在同目录
    end_sec 为实际结束时间（最后一段可能不足 segment_sec）
    """
```

**ffmpeg 命令**（每段）:
```bash
ffmpeg -y -ss {start} -t {segment_sec} -i {video_path} -c copy -movflags +faststart {output}
```

注意 `-ss` 放在 `-i` 前面做 input seeking，速度更快。

### 2. `VIDEO_SEGMENT_HINT` — server/models.py

追加到每段 analyze_video 的 prompt 末尾：

```python
VIDEO_SEGMENT_HINT = """
注意：这是完整视频的第 {seg_index}/{total_segments} 段（{start_sec}s - {end_sec}s）。
请在 events 的 timestamp_sec 中使用相对于完整视频的绝对时间（即加上 {start_sec} 秒的偏移）。
"""
```

使用方式：`prompt + VIDEO_SEGMENT_HINT.format(seg_index=i+1, total_segments=n, start_sec=start, end_sec=end)`

### 3. `VIDEO_MERGE_V1` — server/models.py

合并 prompt：

```python
VIDEO_MERGE_V1 = """\
请综合以下按时间顺序排列的分段分析结果，输出一份完整的视频分析报告。

要求：
1. events 合并：去除重复事件，跨段连续事件合为一条，timestamp_sec 保持绝对时间
2. summary：概括整段视频的核心内容，不是简单拼接各段 summary
3. key_moment：从所有段中选出最重要的一刻及其原因
4. importance_score：基于完整视频全局评估（1-10）
5. category：基于完整视频内容选择最合适的分类

请用 JSON 格式回复：
{
  "importance_score": <1-10 整数>,
  "category": "<safety_hazard / social_interaction / notable_object / navigation / routine / other>",
  "events": [{"timestamp_sec": <浮点数>, "description": "<发生了什么>"}],
  "summary": "<用一句话总结整段视频>",
  "key_moment": "<最重要的一个时刻及其原因>"
}

规则：
- 请用中文填写 summary、description、key_moment 字段。
- 简洁明了，不要添加额外的 key。

以下是各分段分析结果：
{segment_results_json}
"""
```

### 4. `merge_segments` — tests/models/base.py

在 VisionModel 基类上新增**非抽象**方法，提供默认实现（抛 NotImplementedError），各子类覆写：

```python
def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
    """将多个分段分析结果合并为一份完整报告。纯文本调用，不涉及视频。"""
    raise NotImplementedError(f"{self.name} 未实现 merge_segments")
```

### 5. 各模型 `merge_segments` 实现

**GPT / Kimi / Qwen（OpenAI SDK）**— 模式完全相同：

```python
def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
    t0 = time.monotonic()
    resp = self.client.chat.completions.create(
        model=self.model_id,
        max_tokens=2048,
        messages=[{"role": "user", "content": merge_prompt}],
    )
    latency = time.monotonic() - t0
    result = self._parse_json(resp.choices[0].message.content)
    result["_latency_s"] = round(latency, 2)
    return result
```

注意：`merge_prompt` 已经包含了 segment_results 的 JSON 文本，调用方负责 format。

**Gemini（google-genai SDK）**：

```python
def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
    t0 = time.monotonic()
    resp = self.client.models.generate_content(
        model=self.model_id,
        contents=[merge_prompt],
    )
    latency = time.monotonic() - t0
    result = self._parse_json(resp.text)
    result["_latency_s"] = round(latency, 2)
    return result
```

**Sonnet（Anthropic SDK）**：

```python
def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
    t0 = time.monotonic()
    resp = self.client.messages.create(
        model=self.model_id,
        max_tokens=2048,
        messages=[{"role": "user", "content": merge_prompt}],
    )
    latency = time.monotonic() - t0
    result = self._parse_json(resp.content[0].text)
    result["_latency_s"] = round(latency, 2)
    return result
```

**QwenOmniModel**：继承 QwenModel 的实现，无需覆写。

### 6. `run_single_model` 改造 — server/app.py

核心改造逻辑：

```python
async def run_single_model(name, cls, file_path, file_type, prompt, queue, segments=None):
    """
    segments: None 表示短视频/图片，走原流程
              list[tuple[Path, float, float]] 表示长视频分段列表
    """
    await queue.put({"model": name, "status": "running"})
    timeout = MODEL_TIMEOUT_IMAGE if file_type == "image" else MODEL_TIMEOUT_VIDEO

    try:
        model = cls()

        if file_type == "image":
            # 图片：原流程不变
            result = await asyncio.wait_for(
                asyncio.to_thread(model.analyze_image, file_path, prompt),
                timeout=timeout,
            )
        elif segments is None or len(segments) == 1:
            # 短视频（≤60s）：原流程不变
            seg_path = segments[0][0] if segments else file_path
            result = await asyncio.wait_for(
                asyncio.to_thread(model.analyze_video, seg_path, prompt),
                timeout=timeout,
            )
        else:
            # 长视频：Map-Reduce
            total = len(segments)
            seg_results = []

            for i, (seg_path, start, end) in enumerate(segments):
                # 推送分段进度
                await queue.put({
                    "model": name, "status": "running",
                    "progress": f"{i+1}/{total}"
                })

                # 构造带上下文的 prompt
                seg_prompt = prompt + VIDEO_SEGMENT_HINT.format(
                    seg_index=i+1, total_segments=total,
                    start_sec=start, end_sec=end,
                )

                # Map：单段分析
                seg_result = await asyncio.wait_for(
                    asyncio.to_thread(model.analyze_video, seg_path, seg_prompt),
                    timeout=timeout,
                )
                seg_results.append(seg_result)

            # Reduce：合并
            await queue.put({
                "model": name, "status": "running",
                "progress": "合并中"
            })

            # 构造合并 prompt（把 segment_results 序列化进去）
            # 先清除 _latency_s 等内部字段
            clean_results = []
            for r in seg_results:
                clean = {k: v for k, v in r.items() if not k.startswith("_")}
                clean_results.append(clean)

            merge_prompt = VIDEO_MERGE_V1.format(
                segment_results_json=json.dumps(clean_results, ensure_ascii=False, indent=2)
            )

            result = await asyncio.wait_for(
                asyncio.to_thread(model.merge_segments, seg_results, merge_prompt),
                timeout=timeout,
            )

            # 累计延迟 = 所有分段延迟 + 合并延迟
            total_latency = sum(r.get("_latency_s", 0) for r in seg_results) + result.get("_latency_s", 0)
            result["_latency_s"] = round(total_latency, 2)

        await queue.put({"model": name, "status": "done", "result": result})
    except asyncio.TimeoutError:
        await queue.put({"model": name, "status": "error", "error": f"超时 ({timeout}s)"})
    except Exception as e:
        await queue.put({"model": name, "status": "error", "error": str(e)})
```

### 7. `_run_and_cleanup` 改造 — server/app.py

```python
async def _run_and_cleanup(task_id, file_path, file_type, prompt, queue, tmp_dir):
    try:
        if file_type == "video":
            segments = await asyncio.to_thread(_split_video, file_path)
        else:
            segments = None
        await run_all_models(file_path, file_type, prompt, queue, segments)
    finally:
        await asyncio.sleep(5)
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

### 8. `run_all_models` 签名变更 — server/app.py

```python
async def run_all_models(file_path, file_type, prompt, queue, segments=None):
    tasks = []
    for name, cls in MODEL_REGISTRY.items():
        if not CAPABILITY.get(name, {}).get(file_type):
            await queue.put({"model": name, "status": "skipped"})
            continue
        tasks.append(run_single_model(name, cls, file_path, file_type, prompt, queue, segments))
    await asyncio.gather(*tasks)
    await queue.put({"status": "complete"})
```

### 9. 前端 ModelCard.vue 进度显示

仅改 running 状态的文案：

```vue
<!-- running -->
<div v-else-if="state.status === 'running'" class="state-msg running">
  <span class="spinner-dot"></span>
  {{ state.progress ? `分析中 (${state.progress})...` : '分析中...' }}
</div>
```

`state.progress` 来自 SSE 推送的 `progress` 字段，CompareView 已经通过 `modelStates[data.model] = data` 透传了所有字段，无需改动 CompareView。

## Data Models

### SSE 消息格式（变更部分）

原有 running 消息：
```json
{"model": "gemini", "status": "running"}
```

新增 progress 字段（仅长视频时出现）：
```json
{"model": "gemini", "status": "running", "progress": "2/7"}
{"model": "gemini", "status": "running", "progress": "合并中"}
```

### 最终输出 schema — 与 VIDEO_V1 完全一致，无变更

```json
{
  "importance_score": 7,
  "category": "social_interaction",
  "events": [
    {"timestamp_sec": 12.5, "description": "..."},
    {"timestamp_sec": 75.0, "description": "..."},
    {"timestamp_sec": 180.3, "description": "..."}
  ],
  "summary": "...",
  "key_moment": "...",
  "_latency_s": 45.67
}
```

## Error Handling

1. **ffprobe/ffmpeg 失败**：`_split_video` 中 ffprobe 失败时返回单段（原始文件），降级为不切片，打 warning log
2. **单段分析失败**：在 Map 阶段，如果某一段 `analyze_video` 抛异常，捕获后记录 `{"_error": "...", "segment": i}`，继续分析后续段。合并时将失败段信息传给 Reduce prompt
3. **合并失败**：如果 `merge_segments` 失败，回退到返回第一个成功段的结果（降级策略）
4. **所有段都失败**：整体报错，走现有的 error 路径
5. **超时**：单段超时由 `asyncio.wait_for` 控制（300s），整体无额外超时限制

## Testing Strategy

### 手工验证清单

1. **短视频兼容性**：上传 ≤60s 视频 → 不切片 → 行为与改动前完全一致
2. **长视频分段**：上传 6:43 视频 → 切成 7 段 → 每模型逐段分析 → 合并 → 返回完整结果
3. **绝对时间戳**：检查合并结果的 events 中 timestamp_sec 是否为绝对时间（>60s 的事件应当存在）
4. **全局 summary**：检查 summary 是否为全局概括（提及视频后半段内容），而非拼接
5. **SSE 进度**：打开浏览器 DevTools Network → 观察 SSE stream → 确认收到 `progress: "1/7"` ... `progress: "7/7"` ... `progress: "合并中"` 消息
6. **前端进度文案**：ModelCard 的 running 状态显示 `分析中 (2/7)...` 而非普通 `分析中...`
7. **图片不受影响**：上传图片 → 行为与改动前完全一致，无 segments 相关逻辑触发
8. **错误降级**：模拟某段分析超时 → 其他段仍正常完成 → 合并结果标注缺失段
