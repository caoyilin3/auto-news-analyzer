# 如何重新接入大模型 API

这个版本已经把所有真实 API 信息删掉了，默认纯规则运行、不联网、不花钱。

## 以后想用大模型，改这两个文件就行

### 1. `main.py`（日常入口）
找到 `build_config` 函数里这段：

```python
"llm": {
    "enabled": not args.no_llm,
    "api_key": "__FILL_YOUR_API_KEY_HERE__",
    "base_url": "__FILL_API_BASE_URL_HERE__",
    "model": "__FILL_MODEL_NAME_HERE__",
},
```

把三个占位符换成你的真实值，例如：

**DeepSeek**：
- `api_key` → `"sk-你的密钥"`
- `base_url` → `"https://api.deepseek.com/v1/chat/completions"`
- `model` → `"deepseek-chat"`

**OpenAI / ChatGPT**：
- `api_key` → `"sk-你的OpenAI密钥"`
- `base_url` → `"https://api.openai.com/v1/chat/completions"`
- `model` → `"gpt-4o-mini"`（或 gpt-3.5-turbo / gpt-4o）

只要是兼容 OpenAI `/chat/completions` 格式的服务都能直接换。

### 2. `run_pipeline.py`（另一个入口，可选）
同样位置也有一段，改法一样。

## 加完怎么用

```bash
cd D:\autonews_clean
python main.py            # 带大模型跑
python main.py --no-llm   # 临时不用大模型
```

## 占位符搜索

想快速找到所有要填的地方，全局搜索这个字符串：

```
__FILL_
```

一共会命中 6 处（main.py 3 个、run_pipeline.py 3 个）。
