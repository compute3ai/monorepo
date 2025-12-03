# C3 CLI

Command-line interface for [Compute3](https://compute3.ai) - GPU orchestration and LLM API.

## Installation

```bash
pip install c3-cli
```

This also installs the `c3-sdk` as a dependency.

## Setup

Configure your API key:

```bash
c3 configure
```

Or set via environment:

```bash
export C3_API_KEY=your_key
```

Or create `~/.c3/config`:

```
C3_API_KEY=your_key
```

Get your API key at [compute3.ai/dashboard](https://compute3.ai/dashboard)

## Usage

### Billing

```bash
c3 billing balance
c3 billing transactions
c3 billing balance -o json
```

### LLM

```bash
# List models
c3 llm models

# Quick chat
c3 llm chat deepseek-v3.1 "Explain quantum computing"

# Interactive chat
c3 llm chat deepseek-v3.1

# With system prompt
c3 llm chat deepseek-v3.1 "Write a haiku" -s "You are a poet"
```

### Jobs

```bash
# List jobs
c3 jobs list
c3 jobs list -s running

# Create a job
c3 jobs create nvidia/cuda:12.0 -g l40s -c "python train.py"

# Create and follow logs with TUI
c3 jobs create nvidia/cuda:12.0 -g h100 -n 8 -c "torchrun train.py" -f

# Get job details
c3 jobs get <job_id>

# Stream logs
c3 jobs logs <job_id> -f

# Watch GPU metrics
c3 jobs metrics <job_id> -w

# Cancel
c3 jobs cancel <job_id>

# Extend runtime
c3 jobs extend <job_id> 7200
```

### User

```bash
c3 user
```

## Output Formats

```bash
c3 jobs list -o json
c3 billing balance -o table
```

## License

MIT
