"""GPT-5.4 via OpenAI SDK + PackyCode 包月。"""

import base64
import mimetypes
import time
from pathlib import Path

import openai

from tests.config import MODELS
from tests.models.base import VisionModel


class GPTModel(VisionModel):
    name = "gpt"

    def __init__(self):
        cfg = MODELS["gpt"]
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
        """GPT-5.4 不支持原生视频，提取关键帧作为图片序列分析。"""
        import subprocess
        import tempfile

        # 提取关键帧（每 10 秒一帧，最多 20 帧）
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video_path),
                "-vf", "fps=1/10", "-frames:v", "20",
                "-q:v", "2", f"{tmpdir}/frame_%03d.jpg",
            ], capture_output=True)

            frames = sorted(Path(tmpdir).glob("frame_*.jpg"))
            if not frames:
                return {"_error": "无法提取视频帧", "_latency_s": 0}

            content = []
            for i, f in enumerate(frames):
                content.append(self._image_url(f))
                content.append({
                    "type": "text",
                    "text": f"[Frame at {i * 10}s]",
                })

            content.append({
                "type": "text",
                "text": f"Above are {len(frames)} frames extracted from a video (one every 10 seconds). {prompt}",
            })

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
