# 🚀 Compute3 Monorepo

Developer tools and resources for [Compute3](https://compute3.ai) - GPU orchestration and LLM API platform.

## 📦 Packages

| Package | Description | Install |
|---------|-------------|---------|
| [**c3-sdk**](./sdk) | Python SDK for Compute3 API | `pip install c3-sdk` |
| [**c3-cli**](./cli) | Command-line interface with TUI | `pip install c3-cli` |

## 🤖 Applications

| App | Description |
|-----|-------------|
| [**tgbot**](./tgbot) | Telegram bot for AI chat with MCP tool integration |

## 🐳 Docker Images

Pre-built, GPU-optimized containers cached for fast boot times on Compute3 infrastructure.

| Image | Description | Pull |
|-------|-------------|------|
| [**c3-vllm**](./images/c3-vllm) | vLLM inference server | `ghcr.io/comput3ai/c3-vllm` |
| [**comfyui**](./images/comfyui) | ComfyUI for image/video generation | `ghcr.io/comput3ai/comfyui` |
| [**sglang**](./images/sglang) | SGLang inference server | `ghcr.io/comput3ai/sglang` |
| [**ollama**](./images/ollama) | Ollama for local LLMs | `ghcr.io/comput3ai/ollama` |

## ⚡ Quick Start

### SDK

```python
from c3 import C3

c3 = C3()  # Uses C3_API_KEY from env or ~/.c3/config

# Create a GPU job
job = c3.jobs.create(
    image="nvidia/cuda:12.0",
    gpu_type="l40s",
    command="python train.py",
    ports={"lb": 8080},  # HTTPS load balancer
)

# Stream logs
from c3 import LogStream
async with LogStream(job.job_key) as stream:
    async for line in stream:
        print(line)
```

### CLI

```bash
# Configure API key
c3 configure

# Check balance
c3 billing balance

# Create job with live TUI monitoring
c3 jobs create nvidia/cuda:12.0 -g h100 -n 4 -c "torchrun train.py" -f

# Run ComfyUI workflow
c3 comfyui run wan2_1_t2v --prompt "a cat dancing" --output cat.mp4 --lb 8188

# Chat with LLMs
c3 llm chat deepseek-v3.1 "Explain quantum computing"
```

### LLM API (OpenAI Compatible)

```python
from openai import OpenAI

client = OpenAI(
    api_key="your_c3_api_key",
    base_url="https://api.compute3.ai/v1"
)

response = client.chat.completions.create(
    model="deepseek-v3.1",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## 🔑 Authentication

Get your API key at [console.compute3.ai](https://console.compute3.ai)

```bash
# Option 1: Environment variable
export C3_API_KEY=your_key

# Option 2: Config file
echo "C3_API_KEY=your_key" > ~/.c3/config

# Option 3: CLI configure
c3 configure
```

## 📚 Documentation

- [docs.compute3.ai](https://docs.compute3.ai) - Full documentation
- [API Reference](https://docs.compute3.ai/api-reference/introduction) - REST API docs

## 🔗 Links

- [compute3.ai](https://compute3.ai) - Main website
- [console.compute3.ai](https://console.compute3.ai) - Dashboard
- [GitHub](https://github.com/comput3ai) - Source code

## 📄 License

MIT
