"""第三轮测试：视频理解。"""

import json
import sys
from pathlib import Path

from tests.config import VIDEOS_DIR, RESULTS_DIR
from tests.prompts import VIDEO_V1


def get_model(name: str):
    from tests.models import MODEL_REGISTRY

    cls = MODEL_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知模型: {name}")
    return cls()


def collect_videos() -> list[Path]:
    exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    return sorted(p for p in VIDEOS_DIR.iterdir() if p.suffix.lower() in exts)


def run(model_name: str) -> dict:
    model = get_model(model_name)
    videos = collect_videos()

    if not videos:
        print(f"[!] {VIDEOS_DIR} 下没有视频文件。")
        sys.exit(1)

    results = {}
    for vid in videos:
        print(f"  [{model.name}] {vid.name} ...", end=" ", flush=True)
        try:
            result = model.analyze_video(vid, VIDEO_V1)
            results[vid.name] = result
            score = result.get("importance_score", "?")
            latency = result.get("_latency_s", "?")
            print(f"score={score}  latency={latency}s")
        except Exception as e:
            print(f"ERROR: {e}")
            results[vid.name] = {"_error": str(e)}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"round3_{model_name}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n[done] 结果已写入 {out_path}")
    return results


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else "kimi"
    run(model_name)
