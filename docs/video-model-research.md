# 视频理解模型调研报告

> 调研时间: 2026-03-11
> 场景: 可穿戴相机 — 分析10-30秒短视频，判断"有趣/重要" vs "无聊/常规"

## 推荐总结

| 维度 | 推荐模型 | 理由 |
|------|----------|------|
| **API 测试首选** | Gemini 2.5 Flash | ~$0.003/次，原生视频支持最成熟，免费额度 |
| **性价比云端** | Qwen3-VL 30B-A3B | MoE 仅激活 3B 参数，开源可自部署 |
| **最强视频理解** | Qwen3-VL 235B / Gemini 2.5 Flash | 各有所长 |
| **边缘部署首选** | MiniCPM-V 4.5 | 8B 参数，96x 视频压缩，iPad/手机已实跑 |
| **极致轻量** | Qwen3-VL 2B / SlowFast-LLaVA 1B | 语义判断能力可能不足 |

---

## 1. Qwen 系列（阿里巴巴）

### Qwen2.5-VL (2025.01)
- 支持 1 小时以上长视频，动态 FPS 采样，时间点定位
- 规格: 2B / 7B / 32B / 72B
- API: 阿里云百炼 DashScope，兼容 OpenAI 接口
- 价格: Qwen-VL-Max ¥0.02/千token

### Qwen3-VL (2025.09-11)
- 原生 256K token 上下文（可扩展到 1M），处理 2 小时视频
- 规格: 密集 2B/4B/8B/32B + MoE 30B-A3B / 235B-A22B
- **30B-A3B 是性价比之王**：仅激活 3B 参数，性能接近大模型
- API: qwen.ai/apiplatform
- 边缘: 2B/4B 可用 Ollama/vLLM 部署

## 2. Google Gemini

### Gemini 2.5 Flash (2025.06)
- **原生视频输入**，1M token 上下文
- 动态 FPS (0.1-60)，动态分辨率 (360p/480p/720p)
- Token 消耗: ~300 tokens/秒 → 30秒视频约 9000 tokens
- **价格极低**: $0.30/M 输入, $2.50/M 输出 → 30 秒视频 ~$0.003
- 支持 Context Caching，同一视频反复查询更便宜
- 格式: mp4, mpeg, mov, avi, flv, mpg, webm, wmv, 3gpp
- TTFT ~0.4s，输出 ~220-245 tok/s

## 3. Kimi K2.5（月之暗面, 2026.01）

- 1T 总参数 / 32B 激活参数 (MoE)
- 支持视频输入（**实验性**），2K 视频
- API: platform.moonshot.ai，OpenAI 兼容
- 价格: Together AI $0.50/M 输入 + $2.80/M 输出
- **注意**: 视频功能仅限官方 API，vLLM/SGLang 暂不支持
- 定位: 值得跟踪，不建议作为主力

## 4. InternVL 3.5（上海 AI Lab, 2025.08）

- 最大 241B-A28B (MoE)
- Visual Resolution Router 自适应压缩视觉 token（减少 50%）
- InternVideo 2.5 专用长视频，分层上下文压缩 (HiCo)
- **无官方 API**，需自行部署（开源）

## 5. LLaVA-Video 系列（开源）

### SlowFast-LLaVA-1.5 (Apple, 2025)
- **1B / 3B 参数**，专注长视频
- 双流 SlowFast 机制，LongVideoBench SOTA
- 边缘友好，但高级语义判断可能不足

## 6. MiniCPM-V 4.5（OpenBMB, 2025.08）—— 边缘部署亮点

- 3D-Resampler 实现 **96x 视频 token 压缩率**（6 帧压缩到 64 tokens）
- 8B 参数，综合评分 77.0 (OpenCompass) —— **8B 超越 GPT-4o、Qwen2.5-VL 72B**
- 已在 iPad M4 / Android / HarmonyOS 实际运行
- 支持 llama.cpp / vLLM / Ollama
- Nature Communications 发表

## 7. 专用高光检测方案

- SPOT (TimeSformer + CNN): 学术模型，局部+全局视频特征
- OpusClip: 商业工具，ClipAnything 93% 准确率
- AWS Elemental: Fox Sports 使用，20-30 秒检测关键时刻
- 核心思路: 语音高能量 + 视觉变化 + 场景切换 → "病毒性分数"

---

## 产品化路径建议

```
第一步（立即）: Gemini 2.5 Flash API 验证可行性（成本忽略不计）
第二步（方案确认后）: Qwen3-VL 30B-A3B 自建推理服务
第三步（产品化）: 评估 MiniCPM-V 4.5 设备端初筛 + 云端精分析
```
