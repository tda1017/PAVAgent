"""VisionModel 抽象基类，统一所有模型的调用接口。"""

from abc import ABC, abstractmethod
from pathlib import Path


class VisionModel(ABC):
    """视觉模型统一接口。"""

    name: str = "base"

    @abstractmethod
    def analyze_image(self, image_path: Path, prompt: str) -> dict:
        """单图分析，返回解析后的 JSON dict。"""

    @abstractmethod
    def analyze_images(self, image_paths: list[Path], prompt: str) -> dict:
        """多图序列分析，返回解析后的 JSON dict。"""

    @abstractmethod
    def analyze_video(self, video_path: Path, prompt: str) -> dict:
        """视频分析，返回解析后的 JSON dict。"""

    def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
        """将多个分段分析结果合并为一份完整报告。"""
        raise NotImplementedError(f"{self.name} 未实现 merge_segments")

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从模型回复中提取 JSON。"""
        import json
        import re

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 提取 ```json ... ``` 块
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))

        # 提取第一个 { ... }
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))

        raise ValueError(f"无法从模型输出中解析 JSON:\n{text[:200]}")
