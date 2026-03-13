"""读取真实测试结果，组装为前端 report.json。

用法: python -m tests.build_report
"""

import base64
import json
import mimetypes
import warnings
from datetime import datetime
from pathlib import Path

from tests.config import (
    ANNOTATIONS_PATH,
    IMAGES_DIR,
    RESULTS_DIR,
    SEQUENCES_DIR,
    VIDEOS_DIR,
)
from tests.evaluate import evaluate_round1

MODELS = [
    {"id": "sonnet", "name": "Claude Sonnet 4.6"},
    {"id": "kimi", "name": "Kimi K2.5"},
    {"id": "gemini", "name": "Gemini 2.5 Flash"},
    {"id": "qwen", "name": "Qwen3-VL"},
]

MODEL_IDS = [m["id"] for m in MODELS]

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "report.json"


def image_to_data_url(path: Path) -> str:
    """将图片文件转为 base64 data URL。"""
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "image/jpeg"
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    return f"data:{mime};base64,{b64}"


def load_json_safe(path: Path) -> dict | None:
    """安全加载 JSON 文件，失败返回 None 并打印警告。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        warnings.warn(f"加载 {path} 失败: {e}")
        return None


def load_round_results(round_num: int) -> dict[str, dict]:
    """加载某轮所有模型的结果。返回 {model_id: data}。"""
    results = {}
    for mid in MODEL_IDS:
        path = RESULTS_DIR / f"round{round_num}_{mid}.json"
        data = load_json_safe(path)
        if data is not None:
            results[mid] = data
    return results


def build_image_items(annotations: dict, round1: dict[str, dict]) -> list[dict]:
    """构建单图测试项列表。"""
    items = []
    if not IMAGES_DIR.exists():
        warnings.warn(f"图片目录不存在: {IMAGES_DIR}")
        return items

    image_files = sorted(
        f for f in IMAGES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp")
    )

    for idx, img_path in enumerate(image_files):
        stem = img_path.stem
        try:
            b64 = image_to_data_url(img_path)
        except Exception as e:
            warnings.warn(f"读取图片 {img_path} 失败: {e}")
            continue

        gt = annotations.get(stem, {})

        model_results = {}
        for mid in MODEL_IDS:
            model_data = round1.get(mid, {})
            if stem in model_data:
                model_results[mid] = model_data[stem]

        items.append({
            "id": f"img_{idx + 1:03d}",
            "type": "image",
            "filename": img_path.name,
            "media_base64": b64,
            "ground_truth": gt if gt else None,
            "results": model_results,
        })

    return items


def build_sequence_items(round2: dict[str, dict]) -> list[dict]:
    """构建序列测试项列表。"""
    items = []
    if not SEQUENCES_DIR.exists():
        warnings.warn(f"序列目录不存在: {SEQUENCES_DIR}")
        return items

    seq_dirs = sorted(
        d for d in SEQUENCES_DIR.iterdir() if d.is_dir()
    )

    for idx, seq_dir in enumerate(seq_dirs):
        frames = sorted(
            f for f in seq_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp")
        )

        frames_b64 = []
        for frame in frames:
            try:
                frames_b64.append(image_to_data_url(frame))
            except Exception as e:
                warnings.warn(f"读取帧 {frame} 失败: {e}")

        if not frames_b64:
            continue

        stem = seq_dir.name
        model_results = {}
        for mid in MODEL_IDS:
            model_data = round2.get(mid, {})
            if stem in model_data:
                model_results[mid] = model_data[stem]

        items.append({
            "id": f"seq_{idx + 1:03d}",
            "type": "sequence",
            "filename": stem,
            "frames_base64": frames_b64,
            "ground_truth": None,
            "results": model_results,
        })

    return items


def build_video_items(round3: dict[str, dict]) -> list[dict]:
    """构建视频测试项列表。"""
    items = []
    if not VIDEOS_DIR.exists():
        warnings.warn(f"视频目录不存在: {VIDEOS_DIR}")
        return items

    video_files = sorted(
        f for f in VIDEOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm")
    )

    for idx, vid_path in enumerate(video_files):
        stem = vid_path.stem
        model_results = {}
        for mid in MODEL_IDS:
            model_data = round3.get(mid, {})
            if stem in model_data:
                model_results[mid] = model_data[stem]

        items.append({
            "id": f"vid_{idx + 1:03d}",
            "type": "video",
            "filename": vid_path.name,
            "media_base64": None,
            "ground_truth": None,
            "results": model_results,
        })

    return items


def build_stats(round1: dict[str, dict]) -> dict:
    """对有 round1 结果的模型调用 evaluate_round1 获取统计指标。"""
    stats = {}
    for mid in MODEL_IDS:
        if mid not in round1:
            continue
        try:
            report = evaluate_round1(mid)
        except Exception as e:
            warnings.warn(f"评估模型 {mid} 失败: {e}")
            continue

        if "error" in report:
            warnings.warn(f"模型 {mid} 评估结果含错误: {report['error']}")
            continue

        det = report.get("importance_detection", {})
        stats[mid] = {
            "category_accuracy": report.get("category_accuracy", 0),
            "avg_score_diff": report.get("avg_score_diff", 0),
            "avg_latency_s": report.get("avg_latency_s", 0),
            "precision": det.get("precision", 0),
            "recall": det.get("recall", 0),
        }

    return stats


def main():
    # a. 加载标注
    annotations = {}
    if ANNOTATIONS_PATH.exists():
        data = load_json_safe(ANNOTATIONS_PATH)
        if data is not None:
            annotations = data
    else:
        warnings.warn(f"标注文件不存在: {ANNOTATIONS_PATH}，使用空标注")

    # b/c/d. 加载各轮结果
    round1 = load_round_results(1)
    round2 = load_round_results(2)
    round3 = load_round_results(3)

    # 构建 items
    image_items = build_image_items(annotations, round1)
    sequence_items = build_sequence_items(round2)
    video_items = build_video_items(round3)
    items = image_items + sequence_items + video_items

    # 构建统计
    stats = build_stats(round1)

    # 哪些模型有结果
    models_with_results = sorted(
        set(round1.keys()) | set(round2.keys()) | set(round3.keys())
    )

    # 组装报告
    report = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "real",
            "models": MODELS,
            "total_images": len(image_items),
            "total_sequences": len(sequence_items),
            "total_videos": len(video_items),
        },
        "items": items,
        "stats": stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # 打印摘要
    print(f"[OK] report.json 已生成: {OUTPUT_PATH}")
    print(f"     图片: {len(image_items)}")
    print(f"     序列: {len(sequence_items)}")
    print(f"     视频: {len(video_items)}")
    if models_with_results:
        print(f"     有结果的模型: {', '.join(models_with_results)}")
    else:
        print("     警告: 没有找到任何模型的结果文件")
    if stats:
        print(f"     有统计的模型: {', '.join(stats.keys())}")


if __name__ == "__main__":
    main()
