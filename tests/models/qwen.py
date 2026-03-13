"""Qwen 系列模型 via DashScope。"""

import base64
import mimetypes
import subprocess
import time
from pathlib import Path

import openai

from tests.config import MODELS
from tests.models.base import VisionModel


class QwenModel(VisionModel):
    name = "qwen"
    config_key = "qwen"

    def __init__(self):
        cfg = MODELS[self.config_key]
        self.client = openai.OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )
        self.model_id = cfg["model_id"]

    def _image_url(self, path: Path) -> dict:
        media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}"},
        }

    def _call(self, content: list, prompt: str) -> tuple[str, float]:
        content.append({"type": "text", "text": prompt})
        t0 = time.monotonic()
        resp = self.client.chat.completions.create(
            model=self.model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        latency = time.monotonic() - t0
        return resp.choices[0].message.content, latency

    def analyze_image(self, image_path: Path, prompt: str) -> dict:
        content = [self._image_url(image_path)]
        text, latency = self._call(content, prompt)
        result = self._parse_json(text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_images(self, image_paths: list[Path], prompt: str) -> dict:
        content = [self._image_url(p) for p in image_paths]
        text, latency = self._call(content, prompt)
        result = self._parse_json(text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_video(self, video_path: Path, prompt: str) -> dict:
        """Qwen-VL 视频分析，通过 DashScope 原生 SDK 传递本地文件（自动上传 OSS）。"""
        from dashscope import MultiModalConversation

        cfg = MODELS[self.config_key]
        t0 = time.monotonic()
        resp = MultiModalConversation.call(
            api_key=cfg["api_key"],
            model=self.model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"video": str(video_path.resolve())},
                    {"text": prompt},
                ],
            }],
        )
        latency = time.monotonic() - t0
        text = resp.output.choices[0].message.content[0]["text"]
        result = self._parse_json(text)
        result["_latency_s"] = round(latency, 2)
        return result

    def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
        """用 OpenAI 兼容文本接口合并多个分段结果。"""
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


class QwenOmniModel(QwenModel):
    """Qwen3-Omni: 支持音视频联合理解，必须流式输出，有视频长度限制。"""
    name = "qwen_omni"
    config_key = "qwen_omni"
    max_video_seconds = 60

    def _clip_video(self, video_path: Path) -> Path:
        """如果视频超长，截取前 max_video_seconds 秒。"""
        import json as _json
        info = _json.loads(subprocess.check_output([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(video_path),
        ]).decode())
        duration = float(info["format"]["duration"])
        if duration <= self.max_video_seconds:
            return video_path
        clip = video_path.parent / f"_clip_{self.max_video_seconds}s_{video_path.name}"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-t", str(self.max_video_seconds), "-c", "copy", str(clip),
        ], capture_output=True)
        return clip

    def analyze_video(self, video_path: Path, prompt: str) -> dict:
        """Qwen3-Omni 音视频联合分析，流式输出。"""
        from dashscope import MultiModalConversation

        cfg = MODELS[self.config_key]
        clipped = self._clip_video(video_path)
        t0 = time.monotonic()
        resp = MultiModalConversation.call(
            api_key=cfg["api_key"],
            model=self.model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"video": str(clipped.resolve())},
                    {"text": prompt},
                ],
            }],
            stream=True,
            incremental_output=True,
        )
        text = ""
        for chunk in resp:
            if chunk.status_code != 200:
                raise RuntimeError(f"DashScope error: {chunk.code} - {chunk.message}")
            if chunk.output and chunk.output.choices:
                for item in chunk.output.choices[0].message.content or []:
                    if "text" in item:
                        text += item["text"]
        latency = time.monotonic() - t0
        result = self._parse_json(text)
        result["_latency_s"] = round(latency, 2)
        return result
