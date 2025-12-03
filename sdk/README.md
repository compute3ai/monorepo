# C3 SDK

Python SDK for [Compute3](https://compute3.ai) - GPU orchestration API.

## Installation

```bash
pip install c3-sdk
```

## Setup

Set your API key:

```bash
export C3_API_KEY=your_api_key
```

Or create `~/.c3/config`:
```
C3_API_KEY=your_api_key
```

Or pass directly:
```python
c3 = C3(api_key="your_api_key")
```

## Usage

```python
from c3 import C3

c3 = C3()

# Check balance
balance = c3.billing.balance()
print(f"Balance: ${balance.total:.2f}")
print(f"Rewards: ${balance.rewards:.2f}")

# List transactions
for tx in c3.billing.transactions(limit=10):
    print(f"{tx.transaction_type}: ${tx.amount_usd:.4f}")

# Create a job
job = c3.jobs.create(
    image="nvidia/cuda:12.0",
    command="python train.py",
    gpu_type="l40s",
    gpu_count=1,
)
print(f"Job ID: {job.job_id}")
print(f"State: {job.state}")

# List jobs
for job in c3.jobs.list():
    print(f"{job.job_id}: {job.state}")

# Get job details
job = c3.jobs.get("job_id")

# Get job logs
logs = c3.jobs.logs("job_id")

# Get GPU metrics
metrics = c3.jobs.metrics("job_id")
for gpu in metrics.gpus:
    print(f"GPU {gpu.index}: {gpu.utilization}% util, {gpu.temperature}°C")

# Cancel a job
c3.jobs.cancel("job_id")

# Extend runtime
c3.jobs.extend("job_id", runtime=7200)

# Get user info
user = c3.user.get()
print(f"User: {user.email}")
```

## LLM API

For LLM access, use the OpenAI SDK with C3's base URL:

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

## Error Handling

```python
from c3 import C3, APIError

c3 = C3()

try:
    job = c3.jobs.get("invalid_id")
except APIError as e:
    print(f"Error {e.status_code}: {e.detail}")
```

## License

MIT
