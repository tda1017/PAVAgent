"""预标注脚本：用 Opus 4.6 自动标注图片，生成 ground truth 供人工审核。"""

import json
import sys
from pathlib import Path

import anthropic

from tests.config import MODELS, IMAGES_DIR, ANNOTATIONS_PATH
from tests.prompts import ANNOTATE_V1
from tests.models.sonnet import SonnetModel


def get_opus_client():
    """用 Opus 做标注（更强的模型 = 更准的 ground truth）。"""
    cfg = MODELS["opus"]
    return anthropic.Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"]), cfg["model_id"]


def collect_images() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    images = sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in exts)
    return images


def annotate_image(client, model_id, image_path: Path) -> dict:
    """用 Opus 标注单张图片。"""
    # 复用 SonnetModel 的编码逻辑
    model = SonnetModel.__new__(SonnetModel)
    img_block = model._encode_image(image_path)

    resp = client.messages.create(
        model=model_id,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [img_block, {"type": "text", "text": ANNOTATE_V1}],
            }
        ],
    )
    return SonnetModel._parse_json(resp.content[0].text)


def main():
    images = collect_images()
    if not images:
        print(f"[!] 没有在 {IMAGES_DIR} 找到图片，请先放入测试图片。")
        sys.exit(1)

    # 加载已有标注（增量标注）
    existing = {}
    if ANNOTATIONS_PATH.exists():
        existing = json.loads(ANNOTATIONS_PATH.read_text())
        print(f"[*] 已有 {len(existing)} 条标注，增量标注新图片。")

    client, model_id = get_opus_client()
    new_count = 0

    for img in images:
        key = img.name
        if key in existing:
            print(f"  [skip] {key}")
            continue

        print(f"  [annotate] {key} ...", end=" ", flush=True)
        try:
            result = annotate_image(client, model_id, img)
            existing[key] = result
            new_count += 1
            print(f"score={result.get('importance_score', '?')}")
        except Exception as e:
            print(f"ERROR: {e}")
            existing[key] = {"_error": str(e)}

    ANNOTATIONS_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"\n[done] 新增 {new_count} 条标注，共 {len(existing)} 条。")
    print(f"  -> {ANNOTATIONS_PATH}")
    print("  请审核 annotations.json，修正不准确的标签后即为 ground truth。")


if __name__ == "__main__":
    main()
