"""复用 tests/models 中的模型注册表和 prompt 模板。"""

import sys
from pathlib import Path

# 把项目根目录加到 sys.path，让 tests 包可被导入
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from tests.models import MODEL_REGISTRY  # noqa: E402

# 模型能力矩阵：哪些模型支持图片/视频
CAPABILITY = {
    "sonnet":             {"image": True, "video": False},
    "kimi":               {"image": True, "video": True},
    "gemini":             {"image": True, "video": True},
    "gemini_flash_image": {"image": True, "video": True},
    "qwen":               {"image": True, "video": True},
    "qwen_omni":          {"image": True, "video": True},
    "gpt":                {"image": True, "video": True},
}

# ── 中文 prompt（上传对比模式专用，不影响 benchmark）──────────────

SINGLE_IMAGE_V1 = """\
你是一个可穿戴 AI 摄像头助手。请从用户的第一人称视角分析这张图片。

请用 JSON 格式回复，包含以下字段：
{
  "importance_score": <1-10 整数>,
  "category": "<以下之一: safety_hazard, social_interaction, notable_object, \
navigation, routine, other>",
  "summary": "<用一句话描述画面中正在发生什么>",
  "reason": "<解释为什么这个时刻重要或不重要>"
}

规则：
- importance_score 1-3: 日常场景，可忽略
- importance_score 4-6: 有一定意义
- importance_score 7-10: 重要，应通知用户
- 请用中文填写 summary 和 reason 字段，简洁明了。不要添加额外的 key。
"""

VIDEO_V1 = """\
你是一个可穿戴 AI 摄像头助手。请从用户的第一人称视角分析这段视频。

请用 JSON 格式回复：
{
  "importance_score": <1-10 整数>,
  "category": "<以下之一: safety_hazard, social_interaction, notable_object, \
navigation, routine, other>",
  "events": [
    {"timestamp_sec": <浮点数>, "description": "<发生了什么>"}
  ],
  "summary": "<用一句话总结整段视频>",
  "key_moment": "<最重要的一个时刻及其原因>"
}

规则：
- 请用中文填写 summary、description、key_moment 字段。
- 简洁明了，不要添加额外的 key。
"""

VIDEO_SEGMENT_HINT = """\

注意：这是完整视频的第 {seg_index}/{total_segments} 段（{start_sec}s - {end_sec}s）。
请在 events 的 timestamp_sec 中使用相对于完整视频的绝对时间（即加上 {start_sec} 秒的偏移）。
"""

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

__all__ = [
    "MODEL_REGISTRY",
    "CAPABILITY",
    "SINGLE_IMAGE_V1",
    "VIDEO_V1",
    "VIDEO_SEGMENT_HINT",
    "VIDEO_MERGE_V1",
]
