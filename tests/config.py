"""API 配置管理，从 .env 读取密钥。"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# PackyCode 中转 — Anthropic 格式（Sonnet / Opus）
# 注意：Anthropic SDK 会自动拼 /v1/messages，base_url 不带 /v1
PACKY_API_KEY = os.getenv("PACKY_API_KEY", "")
PACKY_BASE_URL = "https://www.packyapi.com"

# PackyCode 中转 — Google 格式（Gemini）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://www.packyapi.com"

# AiCodeMirror 中转 — Google 格式（Gemini Flash Image 等）
AICODEMIRROR_API_KEY = os.getenv("AICODEMIRROR_API_KEY", "")
AICODEMIRROR_BASE_URL = "https://api.aicodemirror.com/api/gemini"

# PackyCode 包月 — OpenAI 格式（GPT-5.4）
GPT_API_KEY = os.getenv("GPT_API_KEY", "")
GPT_BASE_URL = "https://codex-api.packycode.com/v1"

# Moonshot (Kimi)
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"

# DashScope (Qwen)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 模型 ID 映射
MODELS = {
    "sonnet": {
        "sdk": "anthropic",
        "model_id": "claude-sonnet-4-6",
        "base_url": PACKY_BASE_URL,
        "api_key": PACKY_API_KEY,
    },
    "opus": {
        "sdk": "anthropic",
        "model_id": "claude-opus-4-6",
        "base_url": PACKY_BASE_URL,
        "api_key": PACKY_API_KEY,
    },
    "kimi": {
        "sdk": "openai",
        "model_id": "kimi-k2.5",
        "base_url": MOONSHOT_BASE_URL,
        "api_key": MOONSHOT_API_KEY,
    },
    "gemini": {
        "sdk": "google",
        "model_id": "gemini-3-flash-preview",
        "base_url": AICODEMIRROR_BASE_URL,
        "api_key": AICODEMIRROR_API_KEY,
    },
    "gemini_flash_image": {
        "sdk": "google",
        "model_id": "gemini-3.1-flash-image-preview",
        "base_url": AICODEMIRROR_BASE_URL,
        "api_key": AICODEMIRROR_API_KEY,
    },
    "qwen": {
        "sdk": "openai",
        "model_id": "qwen-vl-max",
        "base_url": DASHSCOPE_BASE_URL,
        "api_key": DASHSCOPE_API_KEY,
    },
    "qwen_omni": {
        "sdk": "dashscope",
        "model_id": "qwen3-omni-flash",
        "base_url": DASHSCOPE_BASE_URL,
        "api_key": DASHSCOPE_API_KEY,
    },
    "gpt": {
        "sdk": "openai",
        "model_id": "gpt-5.4",
        "base_url": GPT_BASE_URL,
        "api_key": GPT_API_KEY,
    },
}

# 数据目录
DATA_DIR = Path(__file__).resolve().parent / "data"
IMAGES_DIR = DATA_DIR / "images"
SEQUENCES_DIR = DATA_DIR / "sequences"
VIDEOS_DIR = DATA_DIR / "videos"
ANNOTATIONS_PATH = DATA_DIR / "annotations.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
