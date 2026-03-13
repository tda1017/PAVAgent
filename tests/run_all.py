"""入口脚本：运行测试并生成报告。"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="LLM 视觉能力测试")
    parser.add_argument(
        "--round",
        choices=["1", "2", "3", "all"],
        default="all",
        help="测试轮次: 1=单图, 2=序列, 3=视频, all=全部",
    )
    parser.add_argument(
        "--model",
        choices=["sonnet", "kimi", "gemini", "qwen", "all"],
        default="all",
        help="模型选择",
    )
    args = parser.parse_args()

    rounds = ["1", "2", "3"] if args.round == "all" else [args.round]
    models = ["sonnet", "kimi"] if args.model == "all" else [args.model]

    for r in rounds:
        for m in models:
            print(f"\n{'#'*50}")
            print(f"# Round {r} | Model: {m}")
            print(f"{'#'*50}\n")

            try:
                if r == "1":
                    from tests.test_single_image import run
                    run(m)
                elif r == "2":
                    from tests.test_image_sequence import run
                    run(m)
                elif r == "3":
                    from tests.test_video import run
                    run(m)
            except NotImplementedError as e:
                print(f"  [skip] {e}")
            except SystemExit:
                print(f"  [skip] 无数据，跳过")
            except Exception as e:
                print(f"  [error] {e}")

    # 评估（仅 round 1 已实现）
    if "1" in rounds:
        print(f"\n{'#'*50}")
        print(f"# 评估阶段")
        print(f"{'#'*50}\n")
        from tests.evaluate import evaluate_round1, print_report
        for m in models:
            try:
                report = evaluate_round1(m)
                print_report(report)
            except SystemExit:
                print(f"  [skip] {m} 无结果可评估")


if __name__ == "__main__":
    main()
