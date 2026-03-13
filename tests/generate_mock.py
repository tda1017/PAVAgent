"""生成 mock 数据，让前端无需 API key 即可预览。

用法: python -m tests.generate_mock
"""

import base64
import io
import json
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "report.json"

MODELS = [
    {"id": "sonnet", "name": "Claude Sonnet 4.6"},
    {"id": "kimi", "name": "Kimi K2.5"},
    {"id": "gemini", "name": "Gemini 2.5 Flash"},
    {"id": "qwen", "name": "Qwen3-VL"},
]

CATEGORIES = [
    "safety_hazard",
    "social_interaction",
    "notable_object",
    "navigation",
    "routine",
    "other",
]

SCENES = [
    {"filename": "crosswalk.jpg", "label": "Crosswalk", "color": (60, 80, 120), "gt_score": 9, "gt_cat": "safety_hazard",
     "gt_summary": "行人正在过马路，左侧有车辆驶来。", "gt_reason": "行人与车辆的交互构成潜在安全风险，需要立即关注。"},
    {"filename": "cafe_table.jpg", "label": "Cafe", "color": (100, 70, 50), "gt_score": 3, "gt_cat": "routine",
     "gt_summary": "咖啡厅桌面上的咖啡杯和笔记本电脑。", "gt_reason": "日常场景，无特殊事件发生。"},
    {"filename": "dog_park.jpg", "label": "Dog Park", "color": (50, 100, 50), "gt_score": 5, "gt_cat": "social_interaction",
     "gt_summary": "公园里有人在遛狗，一只金毛猎犬正在和另一只狗互动。", "gt_reason": "社交场景，有趣但不紧急。"},
    {"filename": "construction.jpg", "label": "Construction", "color": (120, 100, 40), "gt_score": 8, "gt_cat": "safety_hazard",
     "gt_summary": "建筑工地入口，有重型机械正在作业。", "gt_reason": "工地区域有安全风险，需提醒用户注意。"},
    {"filename": "bookstore.jpg", "label": "Bookstore", "color": (80, 60, 90), "gt_score": 4, "gt_cat": "notable_object",
     "gt_summary": "书店橱窗展示着新书推荐。", "gt_reason": "有趣的展示内容，但非紧急信息。"},
    {"filename": "intersection.jpg", "label": "Intersection", "color": (90, 90, 100), "gt_score": 7, "gt_cat": "navigation",
     "gt_summary": "复杂十字路口，多条道路交汇。", "gt_reason": "导航关键节点，需要确认方向。"},
    {"filename": "street_food.jpg", "label": "Street Food", "color": (110, 80, 50), "gt_score": 4, "gt_cat": "social_interaction",
     "gt_summary": "街边小吃摊位，摊主正在制作煎饼。", "gt_reason": "有趣的街景，可能值得记录。"},
    {"filename": "parking_lot.jpg", "label": "Parking Lot", "color": (70, 70, 80), "gt_score": 2, "gt_cat": "routine",
     "gt_summary": "停车场，车辆有序停放。", "gt_reason": "普通场景，无需特别关注。"},
]

SUMMARIES_POOL = [
    "场景中存在需要关注的安全风险因素。",
    "这是一个日常生活场景，没有特别需要注意的内容。",
    "检测到人与人之间的社交互动行为。",
    "发现了一个值得记录的有趣物体或标志。",
    "这是一个导航关键节点，建议确认方向。",
    "常规场景，自动记录即可。",
]


def make_placeholder_image(width: int, height: int, color: tuple, label: str) -> str:
    """生成带标签的纯色占位图，返回 data URL。"""
    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    # 添加网格线增加视觉层次
    for x in range(0, width, 40):
        draw.line([(x, 0), (x, height)], fill=tuple(c + 15 for c in color), width=1)
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=tuple(c + 15 for c in color), width=1)
    # 中心标签
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) / 2, (height - th) / 2), label, fill=(220, 220, 220), font=font)
    # 边框
    draw.rectangle([0, 0, width - 1, height - 1], outline=(200, 200, 200), width=2)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def mock_model_result(gt_score: int, gt_cat: str, gt_summary: str) -> dict:
    """为单个模型生成模拟结果，保持与 ground truth 有一定偏差。"""
    score_offset = random.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2])
    score = max(1, min(10, gt_score + score_offset))

    # 80% 概率命中正确 category
    if random.random() < 0.8:
        cat = gt_cat
    else:
        cat = random.choice([c for c in CATEGORIES if c != gt_cat])

    return {
        "importance_score": score,
        "category": cat,
        "summary": gt_summary if random.random() < 0.6 else random.choice(SUMMARIES_POOL),
        "reason": f"模型分析认为该场景的重要性评分为 {score}/10，属于 {cat} 类别。",
        "_latency_s": round(random.uniform(0.5, 3.0), 2),
    }


def generate_items() -> list:
    """生成所有测试项：单图 + 序列 + 视频。"""
    items = []

    # 单图（8 张）
    for i, scene in enumerate(SCENES):
        b64 = make_placeholder_image(640, 480, scene["color"], scene["label"])
        item = {
            "id": f"img_{i+1:03d}",
            "type": "image",
            "filename": scene["filename"],
            "media_base64": b64,
            "ground_truth": {
                "importance_score": scene["gt_score"],
                "category": scene["gt_cat"],
                "summary": scene["gt_summary"],
                "reason": scene["gt_reason"],
            },
            "results": {},
        }
        for model in MODELS:
            item["results"][model["id"]] = mock_model_result(
                scene["gt_score"], scene["gt_cat"], scene["gt_summary"]
            )
        items.append(item)

    # 序列（2 组，每组 4 帧）
    seq_scenes = [
        {"name": "entering_store", "label": "Store Entry", "colors": [(60, 50, 70), (80, 60, 80), (100, 80, 90), (90, 70, 85)]},
        {"name": "crossing_bridge", "label": "Bridge Cross", "colors": [(50, 80, 110), (60, 90, 120), (70, 100, 130), (80, 110, 140)]},
    ]
    for i, seq in enumerate(seq_scenes):
        frames = [
            make_placeholder_image(320, 240, c, f"{seq['label']} F{j+1}")
            for j, c in enumerate(seq["colors"])
        ]
        item = {
            "id": f"seq_{i+1:03d}",
            "type": "sequence",
            "filename": seq["name"],
            "frames_base64": frames,
            "ground_truth": {
                "transition_detected": True,
                "transition_type": "scene_change",
                "before_state": "室外街道",
                "after_state": "室内商店" if i == 0 else "桥上",
                "importance_score": 6,
                "summary": f"从室外进入{'商店' if i == 0 else '桥面'}的场景转换。",
            },
            "results": {},
        }
        for model in MODELS:
            item["results"][model["id"]] = {
                "transition_detected": random.choice([True, True, True, False]),
                "transition_type": random.choice(["scene_change", "activity_change", "none"]),
                "before_state": "室外",
                "after_state": "室内" if i == 0 else "桥上",
                "importance_score": random.randint(4, 8),
                "summary": f"检测到场景转换：从外部环境进入{'商店' if i == 0 else '桥面'}。",
                "_latency_s": round(random.uniform(1.0, 4.0), 2),
            }
        items.append(item)

    # 视频（1 个占位）
    vid_item = {
        "id": "vid_001",
        "type": "video",
        "filename": "walking_downtown.mp4",
        "media_base64": None,  # 视频太大，前端显示占位
        "ground_truth": {
            "importance_score": 6,
            "category": "navigation",
            "events": [
                {"timestamp_sec": 2, "description": "经过路口"},
                {"timestamp_sec": 5, "description": "看到指示牌"},
                {"timestamp_sec": 8, "description": "到达目的地"},
            ],
            "summary": "在市中心步行，经过几个路口后到达目的地。",
            "key_moment": "在第 5 秒看到关键指示牌。",
        },
        "results": {},
    }
    for model in MODELS:
        vid_item["results"][model["id"]] = {
            "importance_score": random.randint(4, 8),
            "category": random.choice(["navigation", "routine"]),
            "events": [
                {"timestamp_sec": 2, "description": "路口场景"},
                {"timestamp_sec": 6, "description": "标志牌"},
            ],
            "summary": "步行穿过市区的视频记录。",
            "key_moment": "路口处的交通情况。",
            "_latency_s": round(random.uniform(2.0, 6.0), 2),
        }
    items.append(vid_item)

    return items


def generate_stats(items: list) -> dict:
    """根据 items 计算各模型的汇总统计。"""
    stats = {}
    image_items = [it for it in items if it["type"] == "image"]

    for model in MODELS:
        mid = model["id"]
        cat_correct = 0
        score_diffs = []
        latencies = []
        tp = fp = fn = tn = 0
        threshold = 7

        for it in image_items:
            gt = it["ground_truth"]
            pred = it["results"].get(mid, {})
            if not pred:
                continue

            if pred.get("category") == gt.get("category"):
                cat_correct += 1
            score_diffs.append(abs(pred.get("importance_score", 0) - gt.get("importance_score", 0)))
            if "_latency_s" in pred:
                latencies.append(pred["_latency_s"])

            gt_imp = gt.get("importance_score", 0) >= threshold
            pred_imp = pred.get("importance_score", 0) >= threshold
            if gt_imp and pred_imp:
                tp += 1
            elif not gt_imp and pred_imp:
                fp += 1
            elif gt_imp and not pred_imp:
                fn += 1
            else:
                tn += 1

        total = len(image_items)
        stats[mid] = {
            "category_accuracy": round(cat_correct / total, 4) if total else 0,
            "avg_score_diff": round(sum(score_diffs) / len(score_diffs), 2) if score_diffs else 0,
            "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0,
        }

    return stats


def main():
    random.seed(42)

    items = generate_items()
    stats = generate_stats(items)

    report = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "models": MODELS,
            "total_images": sum(1 for it in items if it["type"] == "image"),
            "total_sequences": sum(1 for it in items if it["type"] == "sequence"),
            "total_videos": sum(1 for it in items if it["type"] == "video"),
        },
        "items": items,
        "stats": stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[✓] Mock report 已生成: {OUTPUT_PATH}")
    print(f"    图片: {report['metadata']['total_images']}")
    print(f"    序列: {report['metadata']['total_sequences']}")
    print(f"    视频: {report['metadata']['total_videos']}")


if __name__ == "__main__":
    main()
