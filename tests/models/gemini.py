"""Gemini 系列模型 via google-genai SDK + PackyCode 中转。"""

import mimetypes
import time
from pathlib import Path

from google import genai
from google.genai import types

from tests.config import MODELS
from tests.models.base import VisionModel


class GeminiModel(VisionModel):
    name = "gemini"
    config_key = "gemini"

    def __init__(self):
        cfg = MODELS[self.config_key]
        self.client = genai.Client(
            api_key=cfg["api_key"],
            http_options=types.HttpOptions(api_version="v1beta", base_url=cfg["base_url"]),
        )
        self.model_id = cfg["model_id"]

    def _read_file(self, path: Path) -> types.Part:
        media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return types.Part.from_bytes(data=path.read_bytes(), mime_type=media_type)

    def analyze_image(self, image_path: Path, prompt: str) -> dict:
        t0 = time.monotonic()
        resp = self.client.models.generate_content(
            model=self.model_id,
            contents=[self._read_file(image_path), prompt],
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_images(self, image_paths: list[Path], prompt: str) -> dict:
        parts = [self._read_file(p) for p in image_paths]
        parts.append(prompt)
        t0 = time.monotonic()
        resp = self.client.models.generate_content(
            model=self.model_id,
            contents=parts,
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.text)
        result["_latency_s"] = round(latency, 2)
        return result

    def analyze_video(self, video_path: Path, prompt: str) -> dict:
        """Gemini 原生支持视频，通过 inline bytes 传递。"""
        t0 = time.monotonic()
        resp = self.client.models.generate_content(
            model=self.model_id,
            contents=[self._read_file(video_path), prompt],
            config=types.GenerateContentConfig(max_output_tokens=2048),
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.text)
        result["_latency_s"] = round(latency, 2)
        return result

    def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
        """用纯文本接口合并多个分段结果。"""
        t0 = time.monotonic()
        resp = self.client.models.generate_content(
            model=self.model_id,
            contents=[merge_prompt],
        )
        latency = time.monotonic() - t0
        result = self._parse_json(resp.text)
        result["_latency_s"] = round(latency, 2)
        return result


class GeminiFlashImageModel(GeminiModel):
    name = "gemini_flash_image"
    config_key = "gemini_flash_image"
