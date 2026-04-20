# 行动项提取器

基于FastAPI的智能行动项提取服务，能够将自由格式的文本转换为结构化的行动项列表，支持使用LLM（大语言模型）和规则方法进行提取。

## 📖 项目概述

**行动项提取器**是一款Web应用程序，能够自动从非结构化文本中识别和提取可执行的任务。它支持多种提取方法：

- **LLM驱动提取**：使用Ollama本地大语言模型进行智能行动项识别
- **基于规则的提取**：通过预定义模式匹配项目符号、复选框和编号列表
- **混合方法**：当LLM不可用时，自动从LLM回退到基于规则的方法

### 核心功能

- 🤖 **智能LLM提取**：利用本地Ollama模型（如`llama3.1:8b`）进行智能文本理解
- ⚡ **基于规则的回退**：当LLM不可用时，使用预定义模式进行可靠提取
- 📝 **笔记管理**：保存和检索原始笔记以便参考
- ✅ **行动项跟踪**：将提取的项目标记为完成状态
- 🌐 **Web界面**：用户友好的HTML前端，便于快速测试
- 📊 **RESTful API**：完整的API访问，支持与其他系统集成

## 🚀 设置和运行

### 前置要求

- Python 3.9+
- [Ollama](https://ollama.com/)（可选，用于LLM驱动提取）

### 安装

1. **克隆仓库**：
   ```bash
   cd week2
   ```

2. **安装依赖**（使用pip或poetry）：
   ```bash
   # 使用pip
   pip install fastapi uvicorn pydantic ollama

   # 使用poetry
   poetry install
   ```

3. **设置Ollama**（可选，用于LLM功能）：
   ```bash
   # 拉取模型
   ollama pull llama3.1:8b

   # 验证Ollama是否运行
   ollama list
   ```

### 运行应用程序

#### 直接使用Python运行：
```bash
python -m app.main
```

#### 使用Uvicorn运行：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 访问应用程序：
- **Web界面**：http://127.0.0.1:8000
- **API文档**：http://127.0.0.1:8000/docs
- **健康检查**：http://127.0.0.1:8000/health

## 📡 API端点和功能

### 根端点

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/` | 主Web界面 |
| GET | `/health` | 应用程序健康状态 |

### 笔记API

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/notes` | 列出所有笔记（分页） |
| GET | `/notes/{note_id}` | 获取特定笔记 |
| POST | `/notes` | 创建新笔记 |

#### 请求/响应示例

**POST /notes**
```json
{
  "content": "包含行动项的会议笔记..."
}
```

**响应：**
```json
{
  "id": 1,
  "content": "包含行动项的会议笔记...",
  "created_at": "2024-01-01T12:00:00"
}
```

### 行动项API

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/action-items/extract` | 提取行动项（混合方法） |
| POST | `/action-items/extract-llm` | 仅使用LLM提取 |
| GET | `/action-items` | 列出所有行动项 |
| GET | `/action-items/{action_item_id}` | 获取特定行动项 |
| POST | `/action-items/{action_item_id}/done` | 标记项目为完成 |

#### 请求/响应示例

**POST /action-items/extract**
```json
{
  "text": "- [ ] 设置数据库\n- 实现API提取端点\n1. 编写测试",
  "save_note": true,
  "use_llm": true
}
```

**响应：**
```json
{
  "success": true,
  "action_items": [
    {
      "id": 1,
      "description": "设置数据库",
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

### 行动项字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | int | 唯一标识符 |
| `description` | string | 任务描述（必填） |
| `priority` | string | 优先级：高/中/低 |
| `assignee` | string | 负责人 |
| `deadline` | string | 截止日期/时间 |
| `category` | string | 分类：开发/测试/文档/会议/设计/下载/安装/配置/通用 |
| `estimated_time` | string | 预计时间（分钟） |
| `note_id` | int | 关联的笔记ID |
| `done` | bool | 完成状态 |
| `created_at` | string | 创建时间戳 |
| `extraction_method` | string | 使用的提取方法 |

## 🧪 运行测试套件

### 运行所有测试：
```bash
pytest week2/tests/ -v
```

### 运行特定测试文件：
```bash
pytest week2/tests/test_extract.py -v
```

### 带覆盖率运行：
```bash
pytest week2/tests/ -v --cov=app
```

### 测试示例

测试套件涵盖：

- **项目符号提取**：`- [ ]`、`*`、`-`
- **复选框提取**：`[ ]`、`[x]`
- **编号列表提取**：`1.`、`2.`等
- **关键词检测**：需要、必须、应该
- **空输入处理**
- **LLM集成**（当Ollama可用时）

## 🏗️ 项目结构

```
week2/
├── app/
│   ├── __init__.py           # 包初始化
│   ├── main.py              # 应用程序入口点
│   ├── config.py            # 配置管理
│   ├── db.py                # 数据库层
│   ├── schemas.py           # Pydantic模型
│   ├── exceptions.py        # 自定义异常
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── action_items.py  # 行动项端点
│   │   └── notes.py         # 笔记端点
│   └── services/
│       └── extract.py       # 提取逻辑
├── frontend/
│   └── index.html           # Web界面
├── tests/
│   ├── __init__.py
│   └── test_extract.py      # 单元测试
├── assignment.md            # 作业说明
└── README.md                # 英文说明文档
```

## ⚙️ 配置

配置通过`app/config.py`管理。主要设置项：

| 设置项 | 默认值 | 描述 |
|--------|--------|------|
| `app_name` | Action Item Extractor | 应用程序名称 |
| `host` | 0.0.0.0 | 服务器主机地址 |
| `port` | 8000 | 服务器端口 |
| `ollama_model` | llama3.1:8b | 默认LLM模型名称 |
| `ollama_base_url` | http://localhost:11434 | Ollama服务地址 |
| `use_llm_by_default` | true | 默认使用LLM提取 |

### 环境变量

可以通过环境变量覆盖设置：

```bash
export OLLAMA_MODEL="llama3.1:8b"
export LOG_LEVEL="DEBUG"
```

## 🔧 故障排除

### LLM提取失败

1. **检查Ollama是否运行**：
   ```bash
   ollama list
   ```

2. **启动Ollama服务**：
   ```bash
   ollama serve
   ```

3. **拉取模型**：
   ```bash
   ollama pull llama3.1:8b
   ```

### 数据库问题

1. **重置数据库**：
   ```bash
   rm -f data/app.db
   ```

2. **重启应用程序**（数据库将自动重新创建）

### 端口已被占用

```bash
# 查找并终止使用8000端口的进程
lsof -ti:8000 | xargs kill -9
```

## 📚 附加资源

- [FastAPI文档](https://fastapi.tiangolo.com/)
- [Ollama文档](https://ollama.com/)
- [Pydantic文档](https://docs.pydantic.dev/)
- [SQLite文档](https://www.sqlite.org/docs.html)

## 📄 许可证

MIT许可证 - 详见项目文档