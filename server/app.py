"""PAVAgent 后端服务 — 上传即对比，多模型并行分析 + SSE 推送。"""

import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from server.models import (
    MODEL_REGISTRY,
    CAPABILITY,
    SINGLE_IMAGE_V1,
    VIDEO_V1,
    VIDEO_SEGMENT_HINT,
    VIDEO_MERGE_V1,
)

log = logging.getLogger(__name__)

app = FastAPI(title="PAVAgent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局任务存储 ────────────────────────────────────────────────
_tasks: dict[str, dict] = {}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MODEL_TIMEOUT_IMAGE = 120  # 图片超时秒数
MODEL_TIMEOUT_VIDEO = 300  # 视频超时秒数


# ── 视频预处理 ─────────────────────────────────────────────────

def _get_duration(video_path: Path) -> float:
    """获取视频时长（秒）。"""
    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(video_path),
    ]).decode())
    return float(info["format"]["duration"])


def _split_video(video_path: Path, segment_sec: int = 60) -> list[tuple[Path, float, float]]:
    """将视频按固定时长切成多段；短视频直接返回原文件。"""
    try:
        duration = _get_duration(video_path)
    except Exception:
        log.warning("ffprobe 失败，跳过切片: %s", video_path)
        return [(video_path, 0.0, 0.0)]

    if duration <= segment_sec:
        return [(video_path, 0.0, duration)]

    segments: list[tuple[Path, float, float]] = []
    created_paths: list[Path] = []
    start = 0.0
    seg_index = 0

    while start < duration:
        end = min(start + segment_sec, duration)
        output = video_path.parent / f"_seg_{seg_index}_{video_path.name}"
        proc = subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-t", f"{segment_sec}",
            "-i", str(video_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output),
        ], capture_output=True)

        if proc.returncode != 0 or not output.exists():
            log.warning("视频切片失败，回退原始文件: segment=%s stderr=%s",
                        seg_index, proc.stderr.decode(errors="ignore")[:300])
            for path in created_paths:
                path.unlink(missing_ok=True)
            return [(video_path, 0.0, duration)]

        created_paths.append(output)
        segments.append((output, round(start, 3), round(end, 3)))
        start = end
        seg_index += 1

    log.info("视频切片完成: %.1fs -> %d 段", duration, len(segments))
    return segments


def _remaining_timeout(deadline: float) -> float:
    """把总超时预算分配给当前步骤。"""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise asyncio.TimeoutError
    return remaining


# ── 模型并行调度 ────────────────────────────────────────────────

async def run_single_model(name, cls, file_path, file_type, prompt, queue, segments=None):
    """运行单个模型，结果推入队列。"""
    await queue.put({"model": name, "status": "running"})
    timeout = MODEL_TIMEOUT_IMAGE if file_type == "image" else MODEL_TIMEOUT_VIDEO
    try:
        model = cls()
        if file_type == "image":
            result = await asyncio.wait_for(
                asyncio.to_thread(model.analyze_image, file_path, prompt),
                timeout=timeout,
            )
        elif segments is None or len(segments) == 1:
            target_path = segments[0][0] if segments else file_path
            result = await asyncio.wait_for(
                asyncio.to_thread(model.analyze_video, target_path, prompt),
                timeout=timeout,
            )
        else:
            total = len(segments)
            deadline = time.monotonic() + (total * timeout)
            seg_results: list[dict] = []
            successful_results: list[dict] = []
            merge_inputs: list[dict] = []

            for seg_index, (seg_path, start_sec, end_sec) in enumerate(segments, start=1):
                await queue.put({
                    "model": name,
                    "status": "running",
                    "progress": f"{seg_index}/{total}",
                })

                seg_prompt = prompt + VIDEO_SEGMENT_HINT.format(
                    seg_index=seg_index,
                    total_segments=total,
                    start_sec=round(start_sec, 3),
                    end_sec=round(end_sec, 3),
                )

                try:
                    seg_result = await asyncio.wait_for(
                        asyncio.to_thread(model.analyze_video, seg_path, seg_prompt),
                        timeout=_remaining_timeout(deadline),
                    )
                except Exception as e:
                    log.warning("模型 %s 分段分析失败: %s/%s %s",
                                name, seg_index, total, e)
                    seg_results.append({
                        "_error": str(e),
                        "_segment": seg_index,
                        "_start_sec": start_sec,
                        "_end_sec": end_sec,
                    })
                    merge_inputs.append({
                        "segment_index": seg_index,
                        "start_sec": round(start_sec, 3),
                        "end_sec": round(end_sec, 3),
                        "error": str(e),
                    })
                    continue

                if seg_result.get("_error"):
                    error_text = str(seg_result["_error"])
                    log.warning("模型 %s 分段返回错误: %s/%s %s",
                                name, seg_index, total, error_text)
                    seg_results.append({
                        "_error": error_text,
                        "_segment": seg_index,
                        "_start_sec": start_sec,
                        "_end_sec": end_sec,
                    })
                    merge_inputs.append({
                        "segment_index": seg_index,
                        "start_sec": round(start_sec, 3),
                        "end_sec": round(end_sec, 3),
                        "error": error_text,
                    })
                    continue

                seg_results.append(seg_result)
                successful_results.append(seg_result)
                clean_result = {k: v for k, v in seg_result.items() if not k.startswith("_")}
                merge_inputs.append({
                    "segment_index": seg_index,
                    "start_sec": round(start_sec, 3),
                    "end_sec": round(end_sec, 3),
                    **clean_result,
                })

            if not successful_results:
                errors = [r["_error"] for r in seg_results if r.get("_error")]
                raise RuntimeError("所有分段分析失败: " + " | ".join(errors[:3]))

            await queue.put({
                "model": name,
                "status": "running",
                "progress": "合并中",
            })

            merge_prompt = VIDEO_MERGE_V1.format(
                segment_results_json=json.dumps(merge_inputs, ensure_ascii=False, indent=2)
            )

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(model.merge_segments, seg_results, merge_prompt),
                    timeout=_remaining_timeout(deadline),
                )
            except Exception as e:
                log.warning("模型 %s 合并失败，回退首个成功分段: %s", name, e)
                result = dict(successful_results[0])
                result["_latency_s"] = round(
                    sum(item.get("_latency_s", 0) for item in successful_results),
                    2,
                )
            else:
                total_latency = sum(item.get("_latency_s", 0) for item in successful_results)
                total_latency += result.get("_latency_s", 0)
                result["_latency_s"] = round(total_latency, 2)

        await queue.put({"model": name, "status": "done", "result": result})
    except asyncio.TimeoutError:
        total_timeout = timeout
        if file_type == "video" and segments and len(segments) > 1:
            total_timeout = timeout * len(segments)
        await queue.put({"model": name, "status": "error", "error": f"超时 ({total_timeout}s)"})
    except Exception as e:
        await queue.put({"model": name, "status": "error", "error": str(e)})


async def run_all_models(file_path, file_type, prompt, queue, segments=None):
    """并行启动所有适用模型。"""
    tasks = []
    for name, cls in MODEL_REGISTRY.items():
        if not CAPABILITY.get(name, {}).get(file_type):
            await queue.put({"model": name, "status": "skipped"})
            continue
        tasks.append(run_single_model(name, cls, file_path, file_type, prompt, queue, segments=segments))
    await asyncio.gather(*tasks)
    await queue.put({"status": "complete"})


# ── API 路由 ────────────────────────────────────────────────────

@app.get("/api/models")
def list_models():
    """返回所有模型的名称和能力矩阵。"""
    return [{"id": name, "capability": cap} for name, cap in CAPABILITY.items()]


@app.post("/api/analyze")
async def analyze(file: UploadFile):
    """接收上传文件，创建分析任务，后台并行调模型。"""
    # 校验文件大小（读前检查 content-length，读后二次确认）
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，上限 50MB")

    # 判断文件类型
    suffix = Path(file.filename or "unknown").suffix.lower()
    if suffix in IMAGE_EXTS:
        file_type = "image"
        prompt = SINGLE_IMAGE_V1
    elif suffix in VIDEO_EXTS:
        file_type = "video"
        prompt = VIDEO_V1
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")

    # 写入临时文件
    tmp_dir = Path(tempfile.mkdtemp(prefix="pav_"))
    file_path = tmp_dir / file.filename
    file_path.write_bytes(content)

    # 创建任务
    task_id = uuid.uuid4().hex[:12]
    queue: asyncio.Queue = asyncio.Queue()
    _tasks[task_id] = {
        "queue": queue,
        "file_type": file_type,
        "tmp_dir": tmp_dir,
    }

    # 后台启动模型调用
    asyncio.create_task(_run_and_cleanup(task_id, file_path, file_type, prompt, queue, tmp_dir))

    return {"task_id": task_id, "file_type": file_type}


async def _run_and_cleanup(task_id, file_path, file_type, prompt, queue, tmp_dir):
    """预处理输入 → 运行所有模型 → 清理临时文件。"""
    try:
        segments = None
        if file_type == "video":
            segments = await asyncio.to_thread(_split_video, file_path)
        await run_all_models(file_path, file_type, prompt, queue, segments=segments)
    finally:
        # 延迟清理，给 SSE stream 时间消费队列
        await asyncio.sleep(5)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/analyze/{task_id}/stream")
async def stream_results(task_id: str):
    """SSE 流推送模型结果。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    queue = task["queue"]

    async def event_generator():
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            if msg.get("status") == "complete":
                # 清理任务记录
                _tasks.pop(task_id, None)
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── 生产环境：serve 前端静态文件 ─────────────────────────────────
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True))
