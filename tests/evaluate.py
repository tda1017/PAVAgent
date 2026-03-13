"""评测指标计算：对比模型输出 vs ground truth 标注。"""

import json
import sys
from pathlib import Path

from tests.config import ANNOTATIONS_PATH, RESULTS_DIR


def load_annotations() -> dict:
    if not ANNOTATIONS_PATH.exists():
        print(f"[!] 标注文件不存在: {ANNOTATIONS_PATH}")
        print("    请先运行 python -m tests.annotate")
        sys.exit(1)
    return json.loads(ANNOTATIONS_PATH.read_text())


def load_results(round_num: int, model_name: str) -> dict:
    path = RESULTS_DIR / f"round{round_num}_{model_name}.json"
    if not path.exists():
        print(f"[!] 结果文件不存在: {path}")
        sys.exit(1)
    return json.loads(path.read_text())


def evaluate_round1(model_name: str) -> dict:
    """评估单图分类：category 准确率 + importance_score 偏差。"""
    annotations = load_annotations()
    results = load_results(1, model_name)

    total = 0
    category_correct = 0
    score_diffs = []
    latencies = []
    errors = 0

    for key, pred in results.items():
        if "_error" in pred:
            errors += 1
            continue
        gt = annotations.get(key)
        if not gt or "_error" in gt:
            continue

        total += 1

        # Category 匹配
        if pred.get("category") == gt.get("category"):
            category_correct += 1

        # Score 偏差
        gt_score = gt.get("importance_score", 0)
        pred_score = pred.get("importance_score", 0)
        score_diffs.append(abs(pred_score - gt_score))

        # 延迟
        if "_latency_s" in pred:
            latencies.append(pred["_latency_s"])

    if total == 0:
        return {"error": "没有可评估的样本"}

    # 误报/漏报：以 importance_score >= 7 为"重要"阈值
    threshold = 7
    tp = fp = fn = tn = 0
    for key, pred in results.items():
        if "_error" in pred:
            continue
        gt = annotations.get(key)
        if not gt or "_error" in gt:
            continue
        gt_important = gt.get("importance_score", 0) >= threshold
        pred_important = pred.get("importance_score", 0) >= threshold
        if gt_important and pred_important:
            tp += 1
        elif not gt_important and pred_important:
            fp += 1
        elif gt_important and not pred_important:
            fn += 1
        else:
            tn += 1

    report = {
        "model": model_name,
        "round": 1,
        "total_samples": total,
        "errors": errors,
        "category_accuracy": round(category_correct / total, 4) if total else 0,
        "avg_score_diff": round(sum(score_diffs) / len(score_diffs), 2) if score_diffs else 0,
        "max_score_diff": max(score_diffs) if score_diffs else 0,
        "importance_detection": {
            "threshold": threshold,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else 0,
        },
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
    }
    return report


def print_report(report: dict):
    """终端可读摘要。"""
    print(f"\n{'='*50}")
    print(f"  评测报告: {report.get('model', '?')} | Round {report.get('round', '?')}")
    print(f"{'='*50}")

    if "error" in report:
        print(f"  错误: {report['error']}")
        return

    print(f"  样本数: {report['total_samples']}  (错误: {report['errors']})")
    print(f"  Category 准确率: {report['category_accuracy']:.1%}")
    print(f"  Score 平均偏差: {report['avg_score_diff']}  最大偏差: {report['max_score_diff']}")

    det = report.get("importance_detection", {})
    print(f"\n  重要性检测 (threshold >= {det.get('threshold', 7)}):")
    print(f"    Precision: {det.get('precision', 0):.1%}")
    print(f"    Recall:    {det.get('recall', 0):.1%}")
    print(f"    TP={det.get('true_positive', 0)} FP={det.get('false_positive', 0)} "
          f"FN={det.get('false_negative', 0)} TN={det.get('true_negative', 0)}")

    print(f"\n  平均延迟: {report['avg_latency_s']}s")
    print(f"{'='*50}\n")


def main():
    if len(sys.argv) < 3:
        print("用法: python -m tests.evaluate <round> <model>")
        print("  例: python -m tests.evaluate 1 sonnet")
        sys.exit(1)

    round_num = int(sys.argv[1])
    model_name = sys.argv[2]

    if round_num == 1:
        report = evaluate_round1(model_name)
    else:
        print(f"[!] Round {round_num} 的评估尚未实现")
        sys.exit(1)

    print_report(report)

    # 保存报告
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"eval_round{round_num}_{model_name}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"  报告已写入 {out_path}")


if __name__ == "__main__":
    main()
