"""第一轮测试：单图场景分类。"""

import json
import sys
from pathlib import Path

from tests.config import IMAGES_DIR, ANNOTATIONS_PATH, RESULTS_DIR
from tests.prompts import SINGLE_IMAGE_V1


def get_model(name: str):
    if name == "sonnet":
        from tests.models.sonnet import SonnetModel
        return SonnetModel()
    elif name == "kimi":
        from tests.models.kimi import KimiModel
        return KimiModel()
    elif name == "gemini":
        from tests.models.gemini import GeminiModel
        return GeminiModel()
    elif name == "qwen":
        from tests.models.qwen import QwenModel
        return QwenModel()
    else:
        raise ValueError(f"未知模型: {name}")


def collect_images() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    return sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in exts)


def run(model_name: str) -> dict:
    model = get_model(model_name)
    images = collect_images()

    if not images:
        print(f"[!] {IMAGES_DIR} 下没有图片。")
        sys.exit(1)

    results = {}
    for img in images:
        print(f"  [{model.name}] {img.name} ...", end=" ", flush=True)
        try:
            result = model.analyze_image(img, SINGLE_IMAGE_V1)
            results[img.name] = result
            score = result.get("importance_score", "?")
            latency = result.get("_latency_s", "?")
            print(f"score={score}  latency={latency}s")
        except Exception as e:
            print(f"ERROR: {e}")
            results[img.name] = {"_error": str(e)}

    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"round1_{model_name}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n[done] 结果已写入 {out_path}")
    return results


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else "sonnet"
    run(model_name)
