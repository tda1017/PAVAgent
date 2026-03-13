"""Sonnet 4.6 via Anthropic SDK + PackyCode 中转。"""

import base64
import mimetypes
import time
from pathlib import Path

import anthropic

from tests.config import MODELS
from tests.models.base import VisionModel


class SonnetModel(VisionModel):
    name = "sonnet"

    def __init__(self):
        cfg = MODELS["sonnet"]
        self.client = anthropic.Anthropic(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )
        self.model_id = cfg["model_id"]

    def _encode_image(self, path: Path) -> dict:
        media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        }

    def analyze_image(self, image_path: Path, prompt: str) -> dict:
        content = [self._encode_image(image_path), {"type": "text", "text": prompt}]
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.content[0].text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_images(self, image_paths: list[Path], prompt: str) -> dict:
        content = [self._encode_image(p) for p in image_paths]
        content.append({"type": "text", "text": prompt})
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.content[0].text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_video(self, video_path: Path, prompt: str) -> dict:
        raise NotImplementedError("Sonnet 不支持直接视频输入，请用帧序列代替")

    def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
        """用纯文本接口合并多个分段结果。"""
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
