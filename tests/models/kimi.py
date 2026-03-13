"""Kimi K2.5 via OpenAI SDK + Moonshot API。"""

import base64
import mimetypes
import time
from pathlib import Path

import openai

from tests.config import MODELS
from tests.models.base import VisionModel


class KimiModel(VisionModel):
    name = "kimi"

    def __init__(self):
        cfg = MODELS["kimi"]
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
        """Kimi K2.5 支持视频输入，通过 video_url + base64 传递。"""
        media_type = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
        data = base64.standard_b64encode(video_path.read_bytes()).decode()
        content = [
            {
                "type": "video_url",
                "video_url": {"url": f"data:{media_type};base64,{data}"},
            },
            {"type": "text", "text": prompt},
        ]
        t0 = time.monotonic()
        resp = self.client.chat.completions.create(
            model=self.model_id,
            max_tokens=2048,
            messages=[{"role": "user", "content": content}],
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.choices[0].message.content)
        result["_latency_s"] = round(latency, 2)
        return result

    def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
        """用纯文本接口合并多个分段结果。"""
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
