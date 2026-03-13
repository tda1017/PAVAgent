#!/usr/bin/env python3
"""
全自动视频 benchmark 脚本。

用法:
    python auto_bench.py /path/to/video.mp4
    python auto_bench.py /path/to/video.mp4 --models kimi,gemini
    python auto_bench.py /path/to/video.mp4 --select  # 交互式选模型

它会:
  1. 检查 .env 配置，交互式补全缺失的 API key
  2. 对每个 key 做真实连通性测试
  3. ffmpeg 压缩视频（4K→720p）+ 智能抽帧
  4. 自动构建 Round 1/2/3 测试数据
  5. 跑选定模型测试，生成 results/ 下的 JSON
  6. 汇总打印能力边界报告
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── 路径常量 ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "tests" / "data"
IMAGES_DIR = DATA_DIR / "images"
SEQUENCES_DIR = DATA_DIR / "sequences"
VIDEOS_DIR = DATA_DIR / "videos"
RESULTS_DIR = PROJECT_ROOT / "results"

# ── 模型 → 所需 key 映射 ────────────────────────────────────────
KEY_MAP = {
    "PACKY_API_KEY": {
        "desc": "PackyCode 中转 — Anthropic 格式（Sonnet 4.6）",
        "models": ["sonnet"],
    },
    "AICODEMIRROR_API_KEY": {
        "desc": "AiCodeMirror 中转 — Google 格式（Gemini）",
        "models": ["gemini", "gemini_flash_image"],
    },
    "MOONSHOT_API_KEY": {
        "desc": "Moonshot API（Kimi K2.5）",
        "models": ["kimi"],
    },
    "DASHSCOPE_API_KEY": {
        "desc": "DashScope API（Qwen-VL / Qwen3-Omni）",
        "models": ["qwen", "qwen_omni"],
    },
    "GPT_API_KEY": {
        "desc": "PackyCode 包月 — OpenAI 格式（GPT-5.4）",
        "models": ["gpt"],
    },
}

ALL_MODELS = ["sonnet", "kimi", "gemini", "gemini_flash_image", "qwen", "qwen_omni", "gpt"]

# ── 能力矩阵 ────────────────────────────────────────────────────
CAPABILITY = {
    "sonnet":             {"image": True, "sequence": True, "video": False},
    "kimi":               {"image": True, "sequence": True, "video": True},
    "gemini":             {"image": True, "sequence": True, "video": True},
    "gemini_flash_image": {"image": True, "sequence": True, "video": True},
    "qwen":               {"image": True, "sequence": True, "video": True},
    "qwen_omni":          {"image": True, "sequence": True, "video": True},
    "gpt":                {"image": True, "sequence": True, "video": True},
}


# ═══════════════════════════════════════════════════════════════
# 第 0 步: .env 管理
# ═══════════════════════════════════════════════════════════════

def ensure_env() -> dict[str, str]:
    """确保 .env 存在并包含所有 key，返回 {key: value}。"""
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    changed = False
    for key, info in KEY_MAP.items():
        val = existing.get(key, "")
        if not val or val.startswith("your_"):
            print(f"\n🔑 缺少 {key}")
            print(f"   用途: {info['desc']}")
            print(f"   影响模型: {', '.join(info['models'])}")
            user_val = input(f"   请输入 {key}（留空跳过）: ").strip()
            if user_val:
                existing[key] = user_val
                changed = True
            else:
                existing[key] = ""
                print(f"   ⚠️  跳过 — {', '.join(info['models'])} 将不可用")

    if changed:
        lines = []
        for key in KEY_MAP:
            lines.append(f"{key}={existing.get(key, '')}")
        ENV_PATH.write_text("\n".join(lines) + "\n")
        print(f"\n✅ .env 已更新")

    return existing


# ═══════════════════════════════════════════════════════════════
# 第 1 步: API 连通性测试
# ═══════════════════════════════════════════════════════════════

def test_connectivity(env: dict[str, str], target_models: list[str]) -> list[str]:
    """逐个测试 API 连通性，返回可用的模型名列表。"""
    print("\n" + "=" * 60)
    print("🔌 API 连通性测试")
    print("=" * 60)

    available = []

    # Sonnet (Anthropic SDK)
    if "sonnet" in target_models and env.get("PACKY_API_KEY"):
        print("\n  [sonnet] Claude Sonnet 4.6 via PackyCode ...", end=" ", flush=True)
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=env["PACKY_API_KEY"],
                base_url="https://www.packyapi.com",
            )
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply OK"}],
            )
            print(f"✅ OK")
            available.append("sonnet")
        except Exception as e:
            print(f"❌ {e}")

    # Gemini (google-genai SDK via AiCodeMirror)
    if "gemini" in target_models and env.get("AICODEMIRROR_API_KEY"):
        print("  [gemini] Gemini 3 Flash via AiCodeMirror ...", end=" ", flush=True)
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(
                api_key=env["AICODEMIRROR_API_KEY"],
                http_options=types.HttpOptions(api_version="v1beta", base_url="https://api.aicodemirror.com/api/gemini"),
            )
            resp = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents="Reply OK",
            )
            print(f"✅ OK")
            available.append("gemini")
        except Exception as e:
            print(f"❌ {e}")

    # Gemini 3.1 Flash Image (google-genai SDK via AiCodeMirror)
    if "gemini_flash_image" in target_models and env.get("AICODEMIRROR_API_KEY"):
        print("  [gemini_flash_image] Gemini 3.1 Flash Image via AiCodeMirror ...", end=" ", flush=True)
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(
                api_key=env["AICODEMIRROR_API_KEY"],
                http_options=types.HttpOptions(api_version="v1beta", base_url="https://api.aicodemirror.com/api/gemini"),
            )
            resp = client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents="Reply OK",
            )
            print(f"✅ OK")
            available.append("gemini_flash_image")
        except Exception as e:
            print(f"❌ {e}")

    # Kimi (OpenAI SDK via Moonshot)
    if "kimi" in target_models and env.get("MOONSHOT_API_KEY"):
        print("  [kimi]   Kimi K2.5 via Moonshot ...", end=" ", flush=True)
        try:
            import openai
            client = openai.OpenAI(
                api_key=env["MOONSHOT_API_KEY"],
                base_url="https://api.moonshot.cn/v1",
            )
            resp = client.chat.completions.create(
                model="kimi-k2.5",
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply OK"}],
            )
            print(f"✅ OK")
            available.append("kimi")
        except Exception as e:
            print(f"❌ {e}")

    # Qwen (OpenAI SDK via DashScope)
    if "qwen" in target_models and env.get("DASHSCOPE_API_KEY"):
        print("  [qwen]   Qwen-VL via DashScope ...", end=" ", flush=True)
        try:
            import openai
            client = openai.OpenAI(
                api_key=env["DASHSCOPE_API_KEY"],
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            resp = client.chat.completions.create(
                model="qwen-vl-max",
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply OK"}],
            )
            print(f"✅ OK")
            available.append("qwen")
        except Exception as e:
            print(f"❌ {e}")

    skipped = [m for m in target_models if m not in available]
    if skipped:
        print(f"\n  ⚠️  不可用: {skipped}")
    print(f"  📊 可用模型: {available if available else '无'}")
    return available


# ═══════════════════════════════════════════════════════════════
# 第 2 步: 视频压缩 + 智能抽帧
# ═══════════════════════════════════════════════════════════════

def get_video_info(video_path: Path) -> dict:
    """获取视频元数据。"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def compress_video(video_path: Path, target_mb: int = 14) -> Path:
    """
    将视频压缩为 720p 30fps，适合 API 传输。
    如果原始视频已经足够小（<target_mb），跳过压缩。
    """
    print("\n" + "=" * 60)
    print("📦 视频压缩")
    print("=" * 60)

    size_mb = video_path.stat().st_size / 1024 / 1024
    info = get_video_info(video_path)
    duration = float(info["format"]["duration"])

    # 找视频流信息
    width = height = 0
    for s in info["streams"]:
        if s["codec_type"] == "video":
            width = s.get("width", 0)
            height = s.get("height", 0)
            break

    print(f"  原始: {width}x{height}, {duration:.1f}s, {size_mb:.1f}MB")

    if size_mb <= target_mb:
        print(f"  ✅ 已经足够小（<{target_mb}MB），跳过压缩")
        return video_path

    # 计算目标码率 (kbps)，留 10% 余量
    target_bitrate = int(target_mb * 0.9 * 8 * 1024 / duration)

    # 压缩到临时位置，避免后续清理 VIDEOS_DIR 时被误删
    compressed = DATA_DIR / f"_compressed_{video_path.stem}.mp4"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  目标: 720p 30fps, ~{target_mb}MB, bitrate={target_bitrate}k")
    print(f"  压缩中...", end=" ", flush=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "scale=-2:720",
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast",
        "-b:v", f"{target_bitrate}k",
        "-c:a", "aac", "-b:a", "64k",  # 保留音频
        "-movflags", "+faststart",
        str(compressed),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"❌ 压缩失败")
        print(proc.stderr[-500:])
        print("  回退使用原始视频")
        return video_path

    new_size = compressed.stat().st_size / 1024 / 1024
    print(f"✅ {new_size:.1f}MB (压缩比 {size_mb/new_size:.0f}x)")
    return compressed


def extract_frames(video_path: Path, max_keyframes: int = 12, max_uniform: int = 8) -> list[Path]:
    """
    智能抽帧策略:
      1. 场景变化检测 — 找到视觉上有意义的转折点
      2. 均匀采样 — 补充覆盖度，防止遗漏

    返回按时间排序的帧路径列表。
    """
    print("\n" + "=" * 60)
    print("🎬 ffmpeg 智能抽帧")
    print("=" * 60)

    info = get_video_info(video_path)
    duration = float(info["format"]["duration"])
    print(f"  视频时长: {duration:.1f}s")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # 先清空旧数据
    for old in IMAGES_DIR.glob("*.jpg"):
        old.unlink()

    # ── 场景变化检测 ──
    # 阈值 0.15：无人机/运动相机画面变化较平滑，需要更低阈值
    print(f"  [1/2] 场景变化检测 (threshold=0.15) ...", end=" ", flush=True)
    scene_dir = IMAGES_DIR / "_scene_tmp"
    scene_dir.mkdir(exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "scale=-2:720,select='gt(scene,0.15)',showinfo",
        "-vsync", "vfr",
        "-frames:v", str(max_keyframes),
        "-q:v", "2",
        str(scene_dir / "scene_%04d.jpg"),
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    scene_frames = sorted(scene_dir.glob("*.jpg"))
    print(f"得到 {len(scene_frames)} 帧")

    # ── 均匀采样 ──
    print(f"  [2/2] 均匀采样 ({max_uniform} 帧) ...", end=" ", flush=True)
    uniform_dir = IMAGES_DIR / "_uniform_tmp"
    uniform_dir.mkdir(exist_ok=True)

    if duration > 0:
        interval = duration / (max_uniform + 1)
        for i in range(max_uniform):
            ts = interval * (i + 1)
            out_file = uniform_dir / f"uniform_{i:04d}.jpg"
            cmd = [
                "ffmpeg", "-y", "-ss", f"{ts:.2f}",
                "-i", str(video_path),
                "-vf", "scale=-2:720",
                "-frames:v", "1", "-q:v", "2",
                str(out_file),
            ]
            subprocess.run(cmd, capture_output=True)
    uniform_frames = sorted(uniform_dir.glob("*.jpg"))
    print(f"得到 {len(uniform_frames)} 帧")

    # ── 合并到 IMAGES_DIR ──
    all_frames = []
    for idx, f in enumerate(scene_frames):
        dst = IMAGES_DIR / f"scene_{idx:03d}.jpg"
        shutil.move(str(f), str(dst))
        all_frames.append(dst)

    for idx, f in enumerate(uniform_frames):
        dst = IMAGES_DIR / f"uniform_{idx:03d}.jpg"
        shutil.move(str(f), str(dst))
        all_frames.append(dst)

    # 清理临时目录
    shutil.rmtree(scene_dir, ignore_errors=True)
    shutil.rmtree(uniform_dir, ignore_errors=True)

    all_frames.sort()
    print(f"\n  📸 共 {len(all_frames)} 帧已保存到 {IMAGES_DIR}")
    return all_frames


def build_sequences(frames: list[Path], window: int = 4) -> list[str]:
    """
    从抽帧结果中构建帧序列（每个序列 = window 张连续帧，步长 = window//2）。
    序列放入 SEQUENCES_DIR/seq_XXX/ 下。
    """
    print(f"\n  🔗 构建帧序列 (窗口={window}) ...", end=" ", flush=True)

    # 清空旧序列
    if SEQUENCES_DIR.exists():
        for d in SEQUENCES_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                shutil.rmtree(d)

    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)
    step = max(1, window // 2)
    seq_ids = []

    for start in range(0, len(frames) - window + 1, step):
        seq_id = f"seq_{len(seq_ids):03d}"
        seq_dir = SEQUENCES_DIR / seq_id
        seq_dir.mkdir(exist_ok=True)
        for j, frame in enumerate(frames[start:start + window]):
            shutil.copy2(str(frame), str(seq_dir / f"{j:03d}.jpg"))
        seq_ids.append(seq_id)

    print(f"得到 {len(seq_ids)} 组序列")
    return seq_ids


# ═══════════════════════════════════════════════════════════════
# 第 3 步: 跑测试
# ═══════════════════════════════════════════════════════════════

def run_tests(available_models: list[str]):
    """对所有可用模型跑 3 轮测试。"""
    print("\n" + "=" * 60)
    print("🧪 开始跑测试")
    print("=" * 60)

    # 需要把项目根目录加入 sys.path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # 重新加载 config（.env 可能刚刚创建）
    from importlib import reload
    import tests.config
    reload(tests.config)

    report = {}

    for model_name in available_models:
        cap = CAPABILITY[model_name]
        report[model_name] = {"round1": None, "round2": None, "round3": None}

        # Round 1: 单图
        if cap["image"]:
            print(f"\n── Round 1 · 单图分析 · {model_name} ──")
            try:
                from tests.test_single_image import run as run_r1
                result = run_r1(model_name)
                report[model_name]["round1"] = {
                    "status": "ok",
                    "count": len(result),
                    "errors": sum(1 for v in result.values() if "_error" in v),
                }
            except Exception as e:
                print(f"  ❌ Round 1 失败: {e}")
                report[model_name]["round1"] = {"status": "error", "msg": str(e)}

        # Round 2: 帧序列
        if cap["sequence"]:
            print(f"\n── Round 2 · 帧序列分析 · {model_name} ──")
            try:
                from tests.test_image_sequence import run as run_r2
                result = run_r2(model_name)
                report[model_name]["round2"] = {
                    "status": "ok",
                    "count": len(result),
                    "errors": sum(1 for v in result.values() if "_error" in v),
                }
            except Exception as e:
                print(f"  ❌ Round 2 失败: {e}")
                report[model_name]["round2"] = {"status": "error", "msg": str(e)}

        # Round 3: 视频
        if cap["video"]:
            print(f"\n── Round 3 · 视频分析 · {model_name} ──")
            try:
                from tests.test_video import run as run_r3
                result = run_r3(model_name)
                report[model_name]["round3"] = {
                    "status": "ok",
                    "count": len(result),
                    "errors": sum(1 for v in result.values() if "_error" in v),
                }
            except Exception as e:
                print(f"  ❌ Round 3 失败: {e}")
                report[model_name]["round3"] = {"status": "error", "msg": str(e)}
        else:
            report[model_name]["round3"] = {"status": "skipped", "reason": "不支持原生视频"}

    return report


# ═══════════════════════════════════════════════════════════════
# 第 4 步: 汇总报告
# ═══════════════════════════════════════════════════════════════

def print_report(report: dict, available: list[str]):
    """打印能力边界测试汇总。"""
    print("\n" + "=" * 60)
    print("📋 能力边界测试报告")
    print("=" * 60)

    header = f"{'模型':<10} {'Round1(单图)':<16} {'Round2(序列)':<16} {'Round3(视频)':<16} {'状态'}"
    print(header)
    print("-" * len(header))

    for model in ALL_MODELS:
        if model not in available:
            print(f"{model:<10} {'—':<16} {'—':<16} {'—':<16} ⛔ 未测试")
            continue

        r = report.get(model, {})
        cols = []
        for rnd in ["round1", "round2", "round3"]:
            info = r.get(rnd)
            if info is None:
                cols.append("—")
            elif info["status"] == "ok":
                errs = info.get("errors", 0)
                total = info.get("count", 0)
                if errs == 0:
                    cols.append(f"✅ {total}项")
                else:
                    cols.append(f"⚠️ {total-errs}/{total}")
            elif info["status"] == "skipped":
                cols.append("⏭️ 跳过")
            else:
                cols.append("❌ 失败")

        print(f"{model:<10} {cols[0]:<16} {cols[1]:<16} {cols[2]:<16} 🟢")

    # 保存详细报告
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "auto_bench_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n📄 详细报告已保存: {report_path}")

    # 能力矩阵总结
    print("\n📊 能力矩阵总结:")
    print("  ┌──────────┬────────┬────────┬────────┐")
    print("  │ 模型     │ 单图   │ 帧序列 │ 原生视频│")
    print("  ├──────────┼────────┼────────┼────────┤")
    for model in ALL_MODELS:
        cap = CAPABILITY[model]
        avail = model in available
        c1 = "✅" if cap["image"] and avail else "❌"
        c2 = "✅" if cap["sequence"] and avail else "❌"
        c3 = "✅" if cap["video"] and avail else "❌"
        print(f"  │ {model:<8} │  {c1}    │  {c2}    │  {c3}    │")
    print("  └──────────┴────────┴────────┴────────┘")
    print(f"\n  💡 Sonnet 不支持原生视频，通过 ffmpeg 抽帧 → 帧序列间接分析")
    print(f"  💡 Kimi 通过 File API 上传视频")
    print(f"  💡 Gemini / Qwen 通过 inline data 传视频")


# ═══════════════════════════════════════════════════════════════
# 模型选择
# ═══════════════════════════════════════════════════════════════

def select_models_interactive() -> list[str]:
    """交互式选择模型。"""
    print("\n📋 可选模型:")
    for i, m in enumerate(ALL_MODELS, 1):
        cap = CAPABILITY[m]
        video_tag = "📹" if cap["video"] else "🖼️"
        print(f"  {i}. {m:<10} {video_tag}")
    print(f"  0. 全选")

    choice = input("\n选择模型编号（逗号分隔，如 1,2,3）: ").strip()
    if choice == "0" or choice == "":
        return ALL_MODELS[:]

    selected = []
    for c in choice.split(","):
        c = c.strip()
        if c.isdigit() and 1 <= int(c) <= len(ALL_MODELS):
            selected.append(ALL_MODELS[int(c) - 1])
        elif c in ALL_MODELS:
            selected.append(c)

    return selected if selected else ALL_MODELS[:]


# ═══════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       PAVAgent 全自动视觉模型 Benchmark 🚀              ║")
    print("╚══════════════════════════════════════════════════════════╝")

    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("--models", help="逗号分隔的模型列表，如 kimi,gemini")
    parser.add_argument("--select", action="store_true", help="交互式选择模型")
    parser.add_argument("--target-mb", type=int, default=14, help="Round3 视频压缩目标大小(MB)")
    args = parser.parse_args()

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        print(f"\n❌ 视频文件不存在: {video_path}")
        sys.exit(1)

    size_mb = video_path.stat().st_size / 1024 / 1024
    print(f"\n📹 输入视频: {video_path}")
    print(f"   大小: {size_mb:.1f} MB")

    # 选模型
    if args.select:
        target_models = select_models_interactive()
    elif args.models:
        target_models = [m.strip() for m in args.models.split(",") if m.strip() in ALL_MODELS]
    else:
        target_models = ALL_MODELS[:]

    print(f"\n🎯 目标模型: {target_models}")

    # Step 0: .env
    env = ensure_env()

    # Step 1: 连通性
    available = test_connectivity(env, target_models)
    if not available:
        print("\n❌ 没有任何可用的模型 API，无法继续。")
        sys.exit(1)

    # Step 2: 视频压缩 + 抽帧
    compressed = compress_video(video_path, target_mb=args.target_mb)
    frames = extract_frames(video_path)  # 抽帧用原始视频（质量更好）
    build_sequences(frames)

    # 把压缩后的视频放到 VIDEOS_DIR（Round 3 用压缩版）
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    for old in VIDEOS_DIR.glob("*.mp4"):
        old.unlink()
    dst = VIDEOS_DIR / f"compressed_{video_path.stem}.mp4"
    shutil.copy2(str(compressed), str(dst))
    # 清理临时压缩文件
    compressed.unlink(missing_ok=True)
    print(f"\n  🎥 Round3 用视频: {dst} ({dst.stat().st_size/1024/1024:.1f}MB)")

    # Step 3: 跑测试
    report = run_tests(available)

    # Step 4: 报告
    print_report(report, available)

    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()
