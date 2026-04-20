# Action Item Extractor

A FastAPI-based intelligent action item extraction service that converts free-form notes into enumerated action items using LLM (Large Language Model) and rule-based methods.

## 📖 Project Overview

**Action Item Extractor** is a web application that automatically identifies and extracts actionable tasks from unstructured text. It supports multiple extraction methods:

- **LLM-powered extraction**: Uses Ollama's local LLM models for intelligent action item recognition
- **Rule-based extraction**: Pattern matching for bullet points, checkboxes, and numbered lists
- **Hybrid approach**: Automatic fallback from LLM to rule-based methods

### Key Features

- 🤖 **Smart LLM Extraction**: Leverages local Ollama models (e.g., `llama3.1:8b`) for intelligent text understanding
- ⚡ **Rule-based Fallback**: Reliable extraction using predefined patterns when LLM is unavailable
- 📝 **Note Management**: Save and retrieve original notes for reference
- ✅ **Action Item Tracking**: Mark extracted items as complete
- 🌐 **Web Interface**: User-friendly HTML frontend for quick testing
- 📊 **RESTful API**: Full API access for integration with other systems

## 🚀 Setup and Running

### Prerequisites

- Python 3.9+
- [Ollama](https://ollama.com/) (optional, for LLM-powered extraction)

### Installation

1. **Clone the repository**:
   ```bash
   cd week2
   ```

2. **Install dependencies** (using pip or poetry):
   ```bash
   # Using pip
   pip install fastapi uvicorn pydantic ollama

   # Using poetry
   poetry install
   ```

3. **Setup Ollama** (optional, for LLM features):
   ```bash
   # Pull the model
   ollama pull llama3.1:8b

   # Verify Ollama is running
   ollama list
   ```

### Running the Application

#### Using Python directly:
```bash
python -m app.main
```

#### Using Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Access the application:
- **Web Interface**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

## 📡 API Endpoints and Functionality

### Root Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main web interface |
| GET | `/health` | Application health status |

### Notes API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notes` | List all notes (paginated) |
| GET | `/notes/{note_id}` | Get a specific note |
| POST | `/notes` | Create a new note |

#### Request/Response Example

**POST /notes**
```json
{
  "content": "Meeting notes with action items..."
}
```

**Response:**
```json
{
  "id": 1,
  "content": "Meeting notes with action items...",
  "created_at": "2024-01-01T12:00:00"
}
```

### Action Items API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/action-items/extract` | Extract action items (hybrid method) |
| POST | `/action-items/extract-llm` | Extract using LLM only |
| GET | `/action-items` | List all action items |
| GET | `/action-items/{action_item_id}` | Get specific action item |
| POST | `/action-items/{action_item_id}/done` | Mark item as complete |

#### Request/Response Example

**POST /action-items/extract**
```json
{
  "text": "- [ ] Set up database\n- Implement API endpoint\n1. Write tests",
  "save_note": true,
  "use_llm": true
}
```

**Response:**
```json
{
  "success": true,
  "action_items": [
    {
      "id": 1,
      "description": "Set up database",
      "priority": null,
      "assignee": null,
      "deadline": null,
      "category": "开发",
      "estimated_time": null,
      "note_id": 1,
      "done": false,
      "created_at": "2024-01-01T12:00:00",
      "extraction_method": "llm"
    }
  ],
  "note_id": 1,
  "extraction_method": "llm",
  "message": "成功提取 1 个行动项（使用llm方法）"
}
```

### Action Item Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique identifier |
| `description` | string | Task description (required) |
| `priority` | string | Priority level: 高/中/低 |
| `assignee` | string | Person responsible |
| `deadline` | string | Due date/time |
| `category` | string | Category: 开发/测试/文档/会议/设计/下载/安装/配置/通用 |
| `estimated_time` | string | Estimated time (minutes) |
| `note_id` | int | Associated note ID |
| `done` | bool | Completion status |
| `created_at` | string | Creation timestamp |
| `extraction_method` | string | Extraction method used |

## 🧪 Running the Test Suite

### Run all tests:
```bash
pytest week2/tests/ -v
```

### Run specific test file:
```bash
pytest week2/tests/test_extract.py -v
```

### Run with coverage:
```bash
pytest week2/tests/ -v --cov=app
```

### Test Examples

The test suite covers:

- **Bullet point extraction**: `- [ ]`, `*`, `-`
- **Checkbox extraction**: `[ ]`, `[x]`
- **Numbered list extraction**: `1.`, `2.`, etc.
- **Keyword detection**: "需要", "必须", "应该"
- **Empty input handling**
- **LLM integration** (when Ollama is available)

## 🏗️ Project Structure

```
week2/
├── app/
│   ├── __init__.py           # Package initialization
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── db.py                # Database layer
│   ├── schemas.py           # Pydantic models
│   ├── exceptions.py        # Custom exceptions
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── action_items.py  # Action item endpoints
│   │   └── notes.py         # Note endpoints
│   └── services/
│       └── extract.py       # Extraction logic
├── frontend/
│   └── index.html           # Web interface
├── tests/
│   ├── __init__.py
│   └── test_extract.py      # Unit tests
├── assignment.md            # Assignment instructions
└── README.md                # This file
```

## ⚙️ Configuration

Configuration is managed through `app/config.py`. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `app_name` | Action Item Extractor | Application name |
| `host` | 0.0.0.0 | Server host |
| `port` | 8000 | Server port |
| `ollama_model` | llama3.1:8b | Default LLM model |
| `ollama_base_url` | http://localhost:11434 | Ollama server URL |
| `use_llm_by_default` | true | Default to LLM extraction |

### Environment Variables

Settings can be overridden via environment variables:

```bash
export OLLAMA_MODEL="llama3.1:8b"
export LOG_LEVEL="DEBUG"
```

## 🔧 Troubleshooting

### LLM Extraction Fails

1. **Check if Ollama is running**:
   ```bash
   ollama list
   ```

2. **Start Ollama service**:
   ```bash
   ollama serve
   ```

3. **Pull the model**:
   ```bash
   ollama pull llama3.1:8b
   ```

### Database Issues

1. **Reset database**:
   ```bash
   rm -f data/app.db
   ```

2. **Restart the application** (database will be recreated automatically)

### Port Already in Use

```bash
# Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## 📄 License

MIT License - See project documentation for details.