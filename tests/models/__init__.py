"""模型注册表。"""

from tests.models.sonnet import SonnetModel
from tests.models.kimi import KimiModel
from tests.models.gemini import GeminiModel, GeminiFlashImageModel
from tests.models.qwen import QwenModel, QwenOmniModel
from tests.models.gpt import GPTModel

MODEL_REGISTRY = {
    "sonnet": SonnetModel,
    "kimi": KimiModel,
    "gemini": GeminiModel,
    "gemini_flash_image": GeminiFlashImageModel,
    "qwen": QwenModel,
    "qwen_omni": QwenOmniModel,
    "gpt": GPTModel,
}
