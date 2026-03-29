# 开发指南

## 项目结构

```
ST-Manager/
├── app.py                      # 主入口文件
├── config.json                 # 配置文件（自动生成）
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 镜像构建文件
├── docker-compose.yaml         # Docker Compose 配置
├── AGENTS.md                   # AI 助手指南
│
├── core/                       # 核心业务逻辑
│   ├── __init__.py            # 模块初始化（create_app 工厂 + init_services 后台启动）
│   ├── auth.py                # 外网访问认证
│   ├── config.py              # 配置管理
│   ├── consts.py              # 常量定义
│   ├── context.py             # 全局上下文（Singleton）
│   ├── event_bus.py           # 事件总线
│   │
│   ├── api/                   # API 路由层
│   │   ├── views.py          # 页面视图
│   │   └── v1/               # API v1 Blueprints
│   │
│   ├── services/              # 业务服务层
│   ├── automation/            # 自动化引擎
│   ├── data/                  # 数据层（SQLite + 缓存）
│   └── utils/                 # 工具函数
│
├── templates/                 # HTML 模板（Jinja2）
├── static/                    # 静态资源（CSS / JS / 第三方库）
├── tests/                     # pytest 测试
└── data/                      # 数据目录（运行时生成）
```

## 环境设置

```bash
# 安装运行依赖
pip install -r requirements.txt

# 安装测试依赖
pip install pytest

# 安装开发工具（可选）
pip install black flake8 mypy
```

## 启动方式

```bash
# 正常启动
python app.py

# 调试模式（热重载）
python app.py --debug
# 或
FLASK_DEBUG=1 python app.py
```

## 代码风格

### Python

- 导入顺序：标准库 → 第三方库 → 本地模块，组间空一行
- 命名：`PascalCase`（类）、`snake_case`（函数/变量）、`UPPER_CASE`（常量）
- 私有方法：`_leading_underscore`
- Blueprint 对象通常命名为 `bp`
- 使用 `os.path.join()` 构建路径，存储路径用 `.replace('\\', '/')` 规范化
- JSON 写入使用 `ensure_ascii=False`
- 错误处理：优先捕获具体异常，避免裸 `except:`
- 日志：通过 `logging.getLogger(__name__)` 记录

### 前端

- 使用 Alpine.js 作为响应式框架
- Tailwind CSS 提供原子化样式
- 模块化组织（`static/js/api/`、`static/js/components/`、`static/js/utils/`）

## 数据库

项目使用 SQLite（直接 `sqlite3` 模块），启用 WAL 模式。

### 主要表

**card_metadata** — 角色卡元数据索引

```sql
CREATE TABLE card_metadata (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    char_name TEXT,
    description TEXT,
    tags TEXT,
    token_count INTEGER,
    file_size INTEGER,
    file_hash TEXT,
    last_modified REAL,
    category TEXT,
    char_version TEXT,
    creator TEXT,
    is_favorite INTEGER DEFAULT 0,
    has_character_book INTEGER DEFAULT 0,
    character_book_name TEXT
);
```

**wi_clipboard** — 世界书剪切板

```sql
CREATE TABLE wi_clipboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_json TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at REAL DEFAULT (strftime('%s', 'now'))
);
```

**wi_entry_history** — 世界书条目历史

```sql
CREATE TABLE wi_entry_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id TEXT DEFAULT '',
    file_path TEXT DEFAULT '',
    entry_uid TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at REAL DEFAULT (strftime('%s', 'now'))
);
```

### 数据库约定

- 使用参数化查询，禁止字符串拼接 SQL
- 写操作使用 `execute_with_retry()` 处理锁冲突
- 连接使用 `with sqlite3.connect(...)` 或 Flask `g` 连接模式

## 运行测试

```bash
# 全部测试
pytest tests/

# 单个文件
pytest tests/test_st_auth_flow.py

# 单个用例
pytest tests/test_st_auth_flow.py::test_st_http_client_web_performs_login

# 详细输出
pytest -v tests/test_chat_list_filters.py::test_chat_list_fav_filter_included
```

## 代码质量检查

```bash
# 格式化
black app.py core tests

# 代码风格检查
flake8 app.py core tests

# 类型检查
mypy core
```
