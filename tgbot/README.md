# Compute3 Telegram Bot

A Telegram bot for AI chat powered by [Compute3](https://compute3.ai) with MCP tool integration.

## Features

- **AI Chat**: Stream chat completions using Compute3's OpenAI-compatible API
- **MCP Tools**: Access Compute3 services (jobs, renders, billing) via Model Context Protocol
- **Render Webhooks**: Automatically receive rendered images/videos in chat with AI-generated captions
- **Context Management**: Create new contexts or resume previous conversations
- **Multi-User**: Each user authenticates with their own Compute3 API key
- **Model Selection**: Choose from available LLM models

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Starlette App                            │
├─────────────────────────────────────────────────────────────────┤
│  /webhook/<token>    │  /render/<secret>   │  /health           │
│  Telegram updates    │  Render results     │  Health check      │
└─────────────────────────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│    Handlers     │    │    Services     │
├─────────────────┤    ├─────────────────┤
│ • onboarding    │    │ • inference     │
│ • chat          │    │ • mcp           │
│ • settings      │    │ • compute3      │
│ • webhook       │    │                 │
└─────────────────┘    └─────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   SQLite DB     │    │  Compute3 API   │
│   (via SQLAlchemy)   │  /v1/* + /mcp   │
└─────────────────┘    └─────────────────┘
```

## Setup

### Prerequisites

- Python 3.12+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Public HTTPS URL for webhooks

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
WEBHOOK_PREFIX=https://your-domain.com/tgbot

# Optional
API_BASE_URL=https://api.compute3.ai  # Compute3 API endpoint
DATABASE_URL=sqlite:///./tgbot.db     # Database connection string
DEFAULT_MODEL=hermes4:70b              # Default LLM model
MCP_SERVER_URL=                        # Optional custom MCP server
PORT=8000                              # Server port
LOG_LEVEL=INFO                         # Logging level
```

### Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment file
cp env.sample .env
# Edit .env with your values

# Run database migrations
alembic upgrade head

# Start the bot
python bot.py
```

### Docker

```bash
# Build
docker build -t c3-tgbot .

# Run
docker run -p 8000:8000 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e WEBHOOK_PREFIX=https://your-domain.com/tgbot \
  c3-tgbot
```

## Project Structure

```
tgbot/
├── bot.py              # Main entry point, Starlette app setup
├── config.py           # Environment configuration
├── db.py               # SQLAlchemy models and database functions
├── keyboards.py        # Telegram inline keyboard builders
├── handlers/
│   ├── onboarding.py   # /start command and API key setup
│   ├── chat.py         # Message handling and streaming responses
│   ├── settings.py     # Settings menu and model selection
│   └── webhook.py      # Render completion webhook handler
├── services/
│   ├── compute3.py     # API key verification and model listing
│   ├── inference.py    # Chat completions with MCP tool support
│   └── mcp.py          # MCP client for Compute3 tools
├── alembic/            # Database migrations
├── Dockerfile
├── entrypoint.sh
└── requirements.txt
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and set up API key |
| `/newcontext` or `/new` | Start a fresh conversation context |

## Inline Buttons

After each AI response:
- **New Context**: Start fresh conversation
- **Settings**: Change model or API key

On context markers:
- **Resume this context**: Merge back to previous context

## How It Works

### Chat Flow

1. User sends message
2. Bot stores message in SQLite with context ID
3. Bot calls Compute3 `/v1/chat/completions` with streaming
4. If model requests MCP tools, bot executes them and continues
5. Response streams to Telegram with rate-limited edits
6. Final response stored in DB with inline keyboard

### Render Webhooks

When creating renders via chat, the bot injects a `notify_url` unique to each user:
```
notify_url: {WEBHOOK_PREFIX}/render/{user.webhook_secret}
```

When the render completes, Compute3 POSTs to this URL and the bot:
1. Looks up user by webhook secret
2. Fetches render details to get the original prompt
3. Generates a witty caption using the LLM
4. Sends the image/video to the user's chat

## Database Schema

**Users**
- `chat_id`: Telegram chat ID (primary key)
- `api_key`: Compute3 API key
- `model`: Selected LLM model
- `current_context_id`: Active conversation context
- `webhook_secret`: Unique secret for render webhooks

**Messages**
- `id`: Auto-increment ID
- `chat_id`: Foreign key to users
- `message_id`: Telegram message ID
- `context_id`: Conversation context UUID
- `role`: user | assistant | context_marker
- `content`: Message text

## Dependencies

- `python-telegram-bot[webhooks]` - Telegram Bot API
- `openai` - OpenAI-compatible client for Compute3 API
- `fastmcp` - MCP client for tool integration
- `sqlalchemy` + `alembic` - Database ORM and migrations
- `starlette` + `uvicorn` - ASGI web server
- `httpx` - Async HTTP client
