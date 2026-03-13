"""长视频 Map-Reduce 的本地单元测试。"""

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

# 这些单元测试只关心切片和调度逻辑，不需要真实 FastAPI 或模型 SDK。
fastapi_module = types.ModuleType("fastapi")


class DummyFastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def add_middleware(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return lambda func: func

    def post(self, *args, **kwargs):
        return lambda func: func

    def mount(self, *args, **kwargs):
        pass


class DummyUploadFile:
    filename = "dummy.mp4"


class DummyHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


fastapi_module.FastAPI = DummyFastAPI
fastapi_module.UploadFile = DummyUploadFile
fastapi_module.HTTPException = DummyHTTPException
sys.modules.setdefault("fastapi", fastapi_module)

cors_module = types.ModuleType("fastapi.middleware.cors")
cors_module.CORSMiddleware = object
sys.modules.setdefault("fastapi.middleware.cors", cors_module)

responses_module = types.ModuleType("fastapi.responses")
responses_module.StreamingResponse = object
sys.modules.setdefault("fastapi.responses", responses_module)

staticfiles_module = types.ModuleType("fastapi.staticfiles")


class DummyStaticFiles:
    def __init__(self, *args, **kwargs):
        pass


staticfiles_module.StaticFiles = DummyStaticFiles
sys.modules.setdefault("fastapi.staticfiles", staticfiles_module)

server_models_module = types.ModuleType("server.models")
server_models_module.MODEL_REGISTRY = {}
server_models_module.CAPABILITY = {}
server_models_module.SINGLE_IMAGE_V1 = "IMAGE"
server_models_module.VIDEO_V1 = "VIDEO"
server_models_module.VIDEO_SEGMENT_HINT = " SEG {seg_index}/{total_segments} {start_sec}-{end_sec}"
server_models_module.VIDEO_MERGE_V1 = "MERGE {segment_results_json}"
sys.modules.setdefault("server.models", server_models_module)

import server.app as app_module


class SplitVideoTests(unittest.TestCase):
    """验证视频切片逻辑。"""

    def test_split_video_keeps_short_video(self):
        """短视频不切片，直接复用原文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "short.mp4"
            video_path.write_bytes(b"fake")

            original = app_module._get_duration
            app_module._get_duration = lambda _: 45.0
            try:
                segments = app_module._split_video(video_path)
            finally:
                app_module._get_duration = original

            self.assertEqual(segments, [(video_path, 0.0, 45.0)])

    def test_split_video_splits_long_video(self):
        """长视频按 60 秒切片，并返回每段时间范围。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "long.mp4"
            video_path.write_bytes(b"fake")

            original_duration = app_module._get_duration
            original_run = app_module.subprocess.run

            def fake_run(cmd, capture_output=True):
                output = Path(cmd[-1])
                output.write_bytes(b"segment")

                class Result:
                    returncode = 0
                    stderr = b""

                return Result()

            app_module._get_duration = lambda _: 125.0
            app_module.subprocess.run = fake_run
            try:
                segments = app_module._split_video(video_path)
            finally:
                app_module._get_duration = original_duration
                app_module.subprocess.run = original_run

            self.assertEqual(
                [(start, end) for _, start, end in segments],
                [(0.0, 60.0), (60.0, 120.0), (120.0, 125.0)],
            )
            self.assertEqual(
                [path.name for path, _, _ in segments],
                ["_seg_0_long.mp4", "_seg_1_long.mp4", "_seg_2_long.mp4"],
            )


class RunSingleModelTests(unittest.TestCase):
    """验证长视频 Map-Reduce 调度逻辑。"""

    def test_run_single_model_long_video_merge_success(self):
        """长视频分段成功后进入合并，并累计延迟。"""

        class FakeModel:
            def analyze_video(self, video_path: Path, prompt: str) -> dict:
                sec = int(video_path.stem.split("_")[-1])
                return {
                    "importance_score": 5 + sec,
                    "category": "routine",
                    "events": [{"timestamp_sec": sec * 60, "description": f"段{sec}"}],
                    "summary": f"摘要{sec}",
                    "key_moment": f"时刻{sec}",
                    "_latency_s": 1.25,
                }

            def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
                assert len(segment_results) == 2
                assert "segment_index" in merge_prompt
                return {
                    "importance_score": 9,
                    "category": "routine",
                    "events": [{"timestamp_sec": 90, "description": "合并"}],
                    "summary": "完整摘要",
                    "key_moment": "完整时刻",
                    "_latency_s": 0.5,
                }

        async def runner():
            queue = asyncio.Queue()
            with tempfile.TemporaryDirectory() as tmpdir:
                segments = []
                for idx in range(2):
                    path = Path(tmpdir) / f"seg_{idx}.mp4"
                    path.write_bytes(b"fake")
                    segments.append((path, idx * 60.0, (idx + 1) * 60.0))

                await app_module.run_single_model(
                    "fake",
                    FakeModel,
                    segments[0][0],
                    "video",
                    "PROMPT",
                    queue,
                    segments=segments,
                )

            messages = []
            while not queue.empty():
                messages.append(queue.get_nowait())
            return messages

        messages = asyncio.run(runner())

        self.assertEqual(
            [msg["progress"] for msg in messages if msg.get("progress")],
            ["1/2", "2/2", "合并中"],
        )
        self.assertEqual(messages[-1]["status"], "done")
        self.assertEqual(messages[-1]["result"]["summary"], "完整摘要")
        self.assertEqual(messages[-1]["result"]["_latency_s"], 3.0)

    def test_run_single_model_long_video_merge_fallback(self):
        """合并失败时回退首个成功分段，单段失败不影响整体完成。"""

        class FakeModel:
            def analyze_video(self, video_path: Path, prompt: str) -> dict:
                if "seg_1" in video_path.name:
                    raise RuntimeError("第二段炸了")
                return {
                    "importance_score": 7,
                    "category": "routine",
                    "events": [{"timestamp_sec": 5, "description": "首段"}],
                    "summary": "首段摘要",
                    "key_moment": "首段时刻",
                    "_latency_s": 1.0,
                }

            def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
                assert "第二段炸了" in merge_prompt
                raise RuntimeError("合并炸了")

        async def runner():
            queue = asyncio.Queue()
            with tempfile.TemporaryDirectory() as tmpdir:
                segments = []
                for idx in range(2):
                    path = Path(tmpdir) / f"seg_{idx}.mp4"
                    path.write_bytes(b"fake")
                    segments.append((path, idx * 60.0, (idx + 1) * 60.0))

                await app_module.run_single_model(
                    "fake",
                    FakeModel,
                    segments[0][0],
                    "video",
                    "PROMPT",
                    queue,
                    segments=segments,
                )

            messages = []
            while not queue.empty():
                messages.append(queue.get_nowait())
            return messages

        messages = asyncio.run(runner())
        result = messages[-1]["result"]

        self.assertEqual(messages[-1]["status"], "done")
        self.assertEqual(result["summary"], "首段摘要")
        self.assertEqual(result["_latency_s"], 1.0)

    def test_run_single_model_treats_segment_error_payload_as_failure(self):
        """返回 _error 的分段也必须按失败处理，不能混入合并输入。"""

        class FakeModel:
            def analyze_video(self, video_path: Path, prompt: str) -> dict:
                if "seg_0" in video_path.name:
                    return {"_error": "抽帧失败", "_latency_s": 0.2}
                return {
                    "importance_score": 8,
                    "category": "routine",
                    "events": [{"timestamp_sec": 65, "description": "后段成功"}],
                    "summary": "后段摘要",
                    "key_moment": "后段时刻",
                    "_latency_s": 1.0,
                }

            def merge_segments(self, segment_results: list[dict], merge_prompt: str) -> dict:
                assert "抽帧失败" in merge_prompt
                assert '"importance_score": 8' in merge_prompt
                return {
                    "importance_score": 8,
                    "category": "routine",
                    "events": [{"timestamp_sec": 65, "description": "后段成功"}],
                    "summary": "合并摘要",
                    "key_moment": "合并时刻",
                    "_latency_s": 0.3,
                }

        async def runner():
            queue = asyncio.Queue()
            with tempfile.TemporaryDirectory() as tmpdir:
                segments = []
                for idx in range(2):
                    path = Path(tmpdir) / f"seg_{idx}.mp4"
                    path.write_bytes(b"fake")
                    segments.append((path, idx * 60.0, (idx + 1) * 60.0))

                await app_module.run_single_model(
                    "fake",
                    FakeModel,
                    segments[0][0],
                    "video",
                    "PROMPT",
                    queue,
                    segments=segments,
                )

            messages = []
            while not queue.empty():
                messages.append(queue.get_nowait())
            return messages

        messages = asyncio.run(runner())
        result = messages[-1]["result"]

        self.assertEqual(messages[-1]["status"], "done")
        self.assertEqual(result["summary"], "合并摘要")
        self.assertEqual(result["_latency_s"], 1.3)


if __name__ == "__main__":
    unittest.main()
