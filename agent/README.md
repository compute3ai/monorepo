# Compute3 Chat Bot

Multi-transport chat bot supporting Telegram and REST API access, powered by [Compute3](https://compute3.ai).

## Features

- **Multi-Transport**: Telegram bot and REST API for web clients
- **AI Chat**: Stream chat completions using Compute3's OpenAI-compatible API
- **MCP Tools**: Access Compute3 services (jobs, renders, billing) via Model Context Protocol
- **Render Webhooks**: Automatically receive rendered images/videos in chat
- **Thread Management**: Organize conversations into threads
- **Message Editing**: Edit messages and regenerate responses from that point
- **Model Selection**: Choose from available LLM models

## Architecture

```
bot/
├── core/
│   ├── __init__.py
│   └── engine.py        # ChatEngine - transport-agnostic message processing
├── handlers/            # Telegram-specific handlers
│   ├── chat.py          # Message handling
│   ├── onboarding.py    # Welcome & API key setup
│   ├── settings.py      # Model selection, settings
│   └── webhook.py       # Render completion webhooks
├── services/
│   ├── inference.py     # OpenAI-compatible streaming with MCP tools
│   ├── mcp.py           # MCP tool integration
│   └── compute3.py      # Compute3 API client
├── alembic/             # Database migrations
├── api.py               # FastAPI REST endpoints
├── bot.py               # Telegram webhook server
├── db.py                # SQLAlchemy models & database functions
├── config.py            # Environment configuration
└── entrypoint.sh        # Container startup script
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | One of these | Telegram bot token - enables Telegram bot |
| `API_PORT` | must be set | REST API port - enables REST API |
| `WEBHOOK_PREFIX` | If TG enabled | Webhook URL prefix (e.g., `https://api.compute3.ai/bot/tg`) |
| `DEFAULT_MODEL` | Yes | Default model for inference |
| `API_BASE_URL` | No | Compute3 API URL (default: `https://api.compute3.ai`) |
| `PORT` | No | Telegram webhook port (default: 8000) |
| `DB_HOST` | No | PostgreSQL host (uses SQLite if not set) |
| `DB_PORT` | No | PostgreSQL port (default: 5432) |
| `DB_USER` | No | PostgreSQL user |
| `DB_PASSWORD` | No | PostgreSQL password |
| `DB_NAME` | No | PostgreSQL database name |
| `DB_SSLMODE` | No | PostgreSQL SSL mode (default: `require`) |
| `MCP_SERVER_URL` | No | MCP server URL for tool support |

**Note:** At least one of `TELEGRAM_BOT_TOKEN` or `API_PORT` must be set.

## REST API

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.
JWTs are validated by calling the backend `/user` endpoint.

### Threads

```http
# List threads
GET /threads?limit=20

# Create thread
POST /threads
{"title": "Optional title"}

# Get thread
GET /threads/{thread_id}

# Delete thread
DELETE /threads/{thread_id}
```

### Messages

```http
# List messages
GET /threads/{thread_id}/messages

# Send message (waits for full response)
POST /threads/{thread_id}/messages
{"content": "Hello, how are you?"}

# Send message (streaming via SSE)
POST /threads/{thread_id}/messages/stream
{"content": "Hello, how are you?"}

# Edit message and regenerate from that point
POST /threads/{thread_id}/messages/{message_id}/update
{"content": "Updated message"}
```

### SSE Stream Format

```
data: Hello
data: Hello, I'm
data: Hello, I'm doing well
event: done
data: 123
```

### Render Notifications

Web clients can receive render completion notifications by:
1. Getting their webhook URL via `/webhook-secret`
2. Using that URL when creating renders
3. Polling `/notifications` for results

```http
# Get webhook URL for render callbacks
GET /webhook-secret
Response: {"webhook_secret": "...", "webhook_url": "https://api.compute3.ai/bot/api/render/..."}

# Get unread render notifications
GET /notifications

# Mark notifications as read
POST /notifications/read
{"notification_ids": [1, 2, 3]}  # or omit to mark all read

# Render webhook (called by render service, no auth)
POST /render/{webhook_secret}
{"id": "render-uuid", "status": "success", "result_url": "https://..."}
```

### Health Check

```http
GET /health
```

## Database Schema

### Users
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Auto-increment primary key |
| `user_id` | String | Unique identifier (UUID for web, `tg_{chat_id}` for Telegram) |
| `chat_id` | BigInteger | Telegram chat ID (nullable) |
| `api_key` | String | API key or JWT token |
| `model` | String | Preferred model |
| `current_thread_id` | String | Active thread FK |
| `webhook_secret` | String | For render callbacks |
| `free` | Integer | Free tier flag |

### Threads
| Column | Type | Description |
|--------|------|-------------|
| `id` | String | UUID primary key |
| `user_id` | String | Owner's user_id FK |
| `title` | String | Thread title |
| `created_at` | DateTime | Created timestamp |
| `updated_at` | DateTime | Last activity |

### Messages
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Auto-increment primary key |
| `user_id` | String | Owner's user_id FK |
| `thread_id` | String | Parent thread FK |
| `telegram_message_id` | BigInteger | Telegram message ID (nullable) |
| `role` | String | `user` or `assistant` |
| `content` | Text | Message content |
| `created_at` | DateTime | Timestamp |

### Render Notifications
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Auto-increment primary key |
| `user_id` | String | Owner's user_id FK |
| `render_id` | String | Render UUID |
| `status` | String | `success` or `failed` |
| `result_url` | String | Result URL (if success) |
| `error` | Text | Error message (if failed) |
| `read` | Integer | 0=unread, 1=read |
| `created_at` | DateTime | Timestamp |

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and set up API key |
| `/newcontext` or `/new` | Start a new conversation thread |

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
export TELEGRAM_BOT_TOKEN=your_token
export WEBHOOK_PREFIX=https://your-domain.com/bot/tg
export DEFAULT_MODEL=minimax-m2
export API_PORT=8001  # Optional: enables REST API

# Run migrations
alembic upgrade head

# Start bot
python bot.py

# Or start API only (without Telegram)
unset TELEGRAM_BOT_TOKEN
uvicorn api:app --port 8001
```

## Docker

```bash
# Build
docker build -t bot .

# Run with Telegram only
docker run -p 8000:8000 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e WEBHOOK_PREFIX=https://your-domain.com/bot/tg \
  -e DEFAULT_MODEL=minimax-m2 \
  bot

# Run with REST API only
docker run -p 8001:8001 \
  -e API_PORT=8001 \
  -e DEFAULT_MODEL=minimax-m2 \
  bot

# Run both
docker run -p 8000:8000 -p 8001:8001 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e WEBHOOK_PREFIX=https://your-domain.com/bot/tg \
  -e API_PORT=8001 \
  -e DEFAULT_MODEL=minimax-m2 \
  bot
```

## Dependencies

- `python-telegram-bot[webhooks]` - Telegram Bot API
- `openai` - OpenAI-compatible client for Compute3 API
- `fastapi` - REST API framework
- `fastmcp` - MCP client for tool integration
- `sqlalchemy` + `alembic` - Database ORM and migrations
- `starlette` + `uvicorn` - ASGI web server
- `httpx` - Async HTTP client
- `pydantic` - Data validation
