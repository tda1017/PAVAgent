"""第二轮测试：连续帧状态转换检测。"""

import json
import sys
from pathlib import Path

from tests.config import SEQUENCES_DIR, RESULTS_DIR
from tests.prompts import IMAGE_SEQUENCE_V1


def get_model(name: str):
    from tests.models import MODEL_REGISTRY

    cls = MODEL_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知模型: {name}")
    return cls()


def collect_sequences() -> list[tuple[str, list[Path]]]:
    """每个子目录为一组序列，目录名为序列 ID。"""
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    sequences = []
    for d in sorted(SEQUENCES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        frames = sorted(p for p in d.iterdir() if p.suffix.lower() in exts)
        if frames:
            sequences.append((d.name, frames))
    return sequences


def run(model_name: str) -> dict:
    model = get_model(model_name)
    sequences = collect_sequences()

    if not sequences:
        print(f"[!] {SEQUENCES_DIR} 下没有序列子目录。")
        print("    请创建子目录并放入按顺序命名的帧图片（如 001.jpg, 002.jpg ...）")
        sys.exit(1)

    results = {}
    for seq_id, frames in sequences:
        print(f"  [{model.name}] seq={seq_id} ({len(frames)} frames) ...", end=" ", flush=True)
        try:
            result = model.analyze_images(frames, IMAGE_SEQUENCE_V1)
            results[seq_id] = result
            transition = result.get("transition_detected", "?")
            latency = result.get("_latency_s", "?")
            print(f"transition={transition}  latency={latency}s")
        except Exception as e:
            print(f"ERROR: {e}")
            results[seq_id] = {"_error": str(e)}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"round2_{model_name}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n[done] 结果已写入 {out_path}")
    return results


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else "sonnet"
    run(model_name)
