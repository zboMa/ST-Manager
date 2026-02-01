# ST-Manager

<div align="center">

**SillyTavern 资源可视化管理工具**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

功能强大 • 界面美观 • 操作便捷

</div>

## 📖 简介

ST-Manager 是一款专为 SillyTavern AI 聊天程序设计的资源可视化管理工具。它提供了一个现代化的 Web 界面，帮助用户高效管理角色卡、世界书、扩展脚本等各种资源，支持批量操作、自动化规则引擎、智能缓存等功能。

### ✨ 核心特性

- 🎴 **角色卡管理** - 支持 PNG/JSON 格式角色卡的浏览、编辑、导入导出
- 📚 **世界书管理** - 统一管理全局世界书、资源目录世界书和内嵌世界书
- 🤖 **自动化引擎** - 基于规则的自动化任务执行，支持复杂的条件判断
- 🔄 **实时同步** - 文件系统自动监听，实时同步变更到数据库
- 🎨 **可视化界面** - 现代化响应式 UI，支持暗色/亮色主题
- 📦 **版本管理** - 支持角色卡 Bundle 多版本管理
- 🏷️ **标签系统** - 强大的标签过滤和批量标签管理
- 🔍 **智能搜索** - 支持名称、文件名、标签、创作者等多维度搜索
- 📝 **预设管理** - 管理 SillyTavern 生成参数预设（JSON）并支持上传/查看
- 🔗 **酒馆资源同步** - 从本地 SillyTavern 读取并同步角色卡、世界书、预设、正则、快速回复
- 🧩 **正则汇总** - 支持读取全局正则与预设绑定正则并汇总展示

---

## 🚀 快速开始

### 环境要求

- Python 3.10 或更高版本
- pip 包管理器

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/Dadihu123/st-manager.git
cd st-manager
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **运行程序**

```bash
python app.py
```

4. **访问界面**

程序启动后会自动打开浏览器访问 `http://127.0.0.1:5000`

### Docker 部署（推荐）

1. **使用 Docker Compose**

```bash
docker-compose up -d
```

2. **访问服务**

服务将在 `http://localhost:5000` 上运行

---

## 📁 项目结构

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
│   ├── __init__.py            # 模块初始化
│   ├── config.py              # 配置管理
│   ├── consts.py              # 常量定义
│   ├── context.py             # 全局上下文（Singleton）
│   ├── event_bus.py           # 事件总线
│   │
│   ├── api/                   # API 路由层
│   │   ├── views.py          # 页面视图
│   │   └── v1/               # API v1
│   │       ├── cards.py      # 角色卡 API
│   │       ├── world_info.py # 世界书 API
│   │       ├── system.py     # 系统 API
│   │       ├── resources.py  # 资源 API
│   │       ├── automation.py # 自动化 API
│   │       └── extensions.py # 扩展 API
│   │       └── presets.py    # 预设 API
│   │
│   ├── services/              # 业务服务层
│   │   ├── scan_service.py   # 文件扫描服务
│   │   ├── cache_service.py  # 缓存管理服务
│   │   ├── card_service.py   # 卡片业务服务
│   │   └── automation_service.py # 自动化服务
│   │
│   ├── automation/            # 自动化引擎
│   │   ├── engine.py         # 规则引擎核心
│   │   ├── manager.py        # 规则集管理
│   │   ├── executor.py       # 规则执行器
│   │   └── constants.py      # 常量定义
│   │
│   ├── data/                  # 数据层
│   │   ├── db_session.py     # 数据库会话
│   │   ├── cache.py          # 全局缓存
│   │   └── ui_store.py       # UI 数据存储
│   │
│   └── utils/                 # 工具函数
│       ├── data.py           # 数据处理工具
│       ├── filesystem.py     # 文件系统工具
│       ├── image.py          # 图片处理工具
│       ├── text.py           # 文本处理工具
│       ├── hash.py           # 哈希计算工具
│       └── net.py            # 网络工具
│
├── templates/                 # HTML 模板
│   ├── layout.html           # 主布局
│   ├── index.html            # 首页
│   ├── components/            # 组件模板
│   │   ├── header.html
│   │   ├── sidebar.html
│   │   ├── grid_cards.html
│   │   ├── grid_wi.html
│   │   └── grid_extensions.html
│   │   └── grid_presets.html
│   └── modals/               # 模态框模板
│       ├── detail_card.html
│       ├── detail_wi_fullscreen.html
│       ├── detail_wi_popup.html
│       ├── settings.html
│       ├── advanced_editor.html
│       ├── automation.html
│       └── ...
│
├── static/                    # 静态资源
│   ├── css/                  # 样式文件
│   │   └── modules/
│   ├── js/                   # JavaScript 文件
│   │   └── utils/
│   │   └── components/presetGrid.js
│   └── lib/                  # 第三方库
│       ├── alpine.js
│       ├── tailwindcss.js
│       ├── marked.min.js
│       └── diff.min.js
│
└── data/                      # 数据目录（运行时生成）
    ├── system/               # 系统数据
    │   ├── db/              # 数据库
    │   ├── thumbnails/      # 缩略图
    │   ├── trash/           # 回收站
    │   └── automation/      # 自动化规则
    ├── library/              # 资源库
    │   ├── characters/      # 角色卡目录
    │   ├── lorebooks/       # 世界书目录
    │   └── extensions/      # 扩展脚本
    │   └── presets/         # 预设目录
    └── temp/                # 临时文件
```

---

## ⚙️ 配置说明

程序首次运行时会自动生成 `config.json` 配置文件。以下是主要配置项：

### 基础配置

```json
{
  "host": "127.0.0.1",
  "port": 5000,
  "dark_mode": true,
  "theme_accent": "blue"
}
```

### 目录配置

```json
{
  "cards_dir": "data/library/characters",
  "world_info_dir": "data/library/lorebooks",
  "regex_dir": "data/library/extensions/regex",
  "scripts_dir": "data/library/extensions/tavern_helper",
  "quick_replies_dir": "data/library/extensions/quick-replies",
  "presets_dir": "data/library/presets",
  "resources_dir": "data/assets/card_assets"
}
```

### SillyTavern 本地路径配置

```json
{
  "st_url": "http://127.0.0.1:8000",
  "st_data_dir": "",
  "st_auth_type": "basic",
  "st_username": "",
  "st_password": "",
  "st_proxy": ""
}
```

`st_data_dir` 留空时会自动探测常见安装路径（Windows: D:\SillyTavern / E:\SillyTavern 等）。
```

### SillyTavern 集成

```json
{
  "st_url": "http://127.0.0.1:8000",
  "st_auth_type": "basic",
  "st_username": "",
  "st_password": "",
  "st_proxy": ""
}
```

### 显示设置

```json
{
  "default_sort": "date_desc",
  "items_per_page": 0,
  "items_per_page_wi": 0,
  "card_width": 220,
  "font_style": "sans",
  "bg_url": "/assets/backgrounds/default_background.jpeg",
  "bg_opacity": 0.45,
  "bg_blur": 2
}
```

### 自动保存设置

```json
{
  "auto_save_enabled": false,
  "auto_save_interval": 3,
  "snapshot_limit_manual": 50,
  "snapshot_limit_auto": 5
}
```

### 系统设置

```json
{
  "enable_auto_scan": true,
  "png_deterministic_sort": false,
  "allowed_abs_resource_roots": [],
  "wi_preview_limit": 300,
  "wi_preview_entry_max_chars": 2000
}
```

#### 说明
- `png_deterministic_sort`：是否对 PNG 元数据进行确定性排序（默认关闭，避免改变外部工具的字节级行为）
- `allowed_abs_resource_roots`：允许访问的绝对资源目录白名单（用于资源文件列表接口）
- `wi_preview_limit`：世界书详情预览最大条目数（0 表示不限制）
- `wi_preview_entry_max_chars`：世界书单条内容预览最大字符数（0 表示不截断）

---

## 🎯 功能详解

### 角色卡管理

#### 支持的格式
- **PNG 卡片** - 包含嵌入式元数据的 PNG 图片
- **JSON 卡片** - 独立的 JSON 格式角色文件
- **伴生图片** - 支持 PNG/JSON 配套的伴生图片

#### 核心功能

| 功能 | 描述 |
|------|------|
| **浏览查看** | 网格/列表视图，支持缩略图预览 |
| **编辑修改** | 支持编辑角色名称、描述、人格、场景等所有字段 |
| **导入导出** | 支持从 URL 导入、文件上传、导出 |
| **批量操作** | 批量移动、删除、标签管理 |
| **收藏标记** | 快速收藏常用角色 |
| **搜索过滤** | 多维度搜索和标签过滤 |
| **Bundle 管理** | 支持多版本角色聚合显示 |

#### Token 计算

自动计算角色卡的总 Token 数量（包括描述、人格、消息示例、世界书等），帮助用户了解资源消耗。

---

### 世界书管理

#### 世界书类型

| 类型 | 说明 |
|------|------|
| **全局世界书** | 存储在 `lorebooks/` 目录，全局共享 |
| **资源世界书** | 存储在角色资源目录的 `lorebooks/` 子目录 |
| **内嵌世界书** | 直接嵌入在角色卡文件中的世界书 |

#### 核心功能

- 📑 统一浏览所有类型的世界书
- ✏️ 在线编辑世界书内容
- 📋 世界书剪切板（暂存、排序）
- 📤 导出世界书为独立 JSON 文件
- 🔗 与角色卡关联显示
- 🔄 一键整理资源目录结构
- ⚡ 大型世界书预览优化：详情弹窗默认预览前 300 条，避免卡死（可手动加载全部）
- 🧹 全局列表去重：自动剔除与内嵌世界书内容重复的条目，避免混杂展示

---

### 自动化规则引擎

#### 规则引擎概述

ST-Manager 内置强大的规则引擎，支持基于条件的自动化任务执行。用户可以定义规则集，当卡片满足特定条件时自动执行预设操作。

#### 规则结构

```json
{
  "spec": "st_manager_ruleset",
  "spec_version": "1.0",
  "meta": {
    "name": "规则集名称",
    "description": "规则集描述",
    "author": "作者"
  },
  "logic": "OR",
  "rules": [
    {
      "name": "规则名称",
      "enabled": true,
      "logic": "OR",
      "groups": [
        {
          "logic": "AND",
          "conditions": [
            {
              "field": "char_name",
              "operator": "contains",
              "value": "关键词"
            }
          ]
        }
      ],
      "actions": [
        {
          "type": "set_tag",
          "value": "标签名称"
        }
      ],
      "stop_on_match": false
    }
  ]
}
```

#### 支持的字段

- `char_name` - 角色名称
- `description` - 角色描述
- `creator` - 创作者
- `tags` - 标签列表
- `token_count` - Token 数量
- `character_book` - 世界书
- `extensions.regex_scripts` - 正则脚本
- `extensions.tavern_helper` - Tavern Helper 脚本

#### 支持的操作符

| 操作符 | 说明 |
|--------|------|
| `exists` | 字段存在 |
| `not_exists` | 字段不存在 |
| `eq` | 等于 |
| `neq` | 不等于 |
| `contains` | 包含 |
| `not_contains` | 不包含 |
| `gt` | 大于 |
| `lt` | 小于 |
| `regex` | 正则匹配 |
| `true` / `false` | 布尔判断 |

#### 支持的动作

- `set_tag` - 添加标签
- `remove_tag` - 移除标签
- `set_favorite` - 设为收藏
- `unset_favorite` - 取消收藏
- `set_summary` - 设置备注
- `set_resource_folder` - 设置资源目录

---

### 扩展脚本管理

支持管理 SillyTavern 的扩展脚本：

#### 正则脚本（Regex Scripts）
- 浏览和编辑正则替换脚本
- 支持批量导入导出

#### Tavern Helper 脚本
- 管理 Tavern Helper 脚本库
- 支持变量和脚本配置

#### 快速回复（Quick Replies）
- 快速回复模板管理
- 支持分类和搜索

#### 预设（Presets）
- 管理生成参数预设（JSON）
- 支持拖拽上传、查看与基础信息展示

### SillyTavern 本地资源读取与同步

在设置 → 连接与服务中配置 SillyTavern 安装目录，可执行：

- 🔍 自动探测本地 SillyTavern 路径
- 📊 显示检测到的资源数量
- 🔄 一键同步角色卡、世界书、预设、正则脚本、快速回复到 ST-Manager
- 🔧 正则同步会导出 settings.json 中的全局正则到本地 regex 目录（以 `global__*.json` 命名）

---

### 缓存与性能优化

#### 全局元数据缓存

- **内存缓存** - 所有卡片元数据加载到内存，实现毫秒级查询
- **增量更新** - 单卡编辑时仅更新内存，无需重载
- **分类计数** - 实时维护分类统计
- **标签池** - 全局标签索引

#### 文件系统监听

使用 `watchdog` 库实时监听文件变化：
- 自动同步新增文件
- 自动更新修改文件
- 自动清理删除文件
- 防抖处理，避免重复扫描

#### 缩略图系统

- 自动生成卡片缩略图（后台线程）
- 支持 PNG、JPEG 格式
- 并发控制（默认 4 线程）
- 智能清理无效缓存

---

## 🔌 API 文档

### 角色卡 API

#### 获取卡片列表

```
GET /api/list_cards?page=1&page_size=20&category=&tags=&search=&sort=date_desc
```

#### 更新卡片

```
POST /api/update_card
Content-Type: application/json

{
  "id": "卡片ID",
  "char_name": "角色名称",
  "description": "描述",
  "tags": ["标签1", "标签2"],
  ...
}
```

#### 移动卡片

```
POST /api/move_card
Content-Type: application/json

{
  "target_category": "目标分类",
  "card_ids": ["卡片ID1", "卡片ID2"]
}
```

#### 删除卡片

```
POST /api/delete_cards
Content-Type: application/json

{
  "card_ids": ["卡片ID1", "卡片ID2"]
}
```

### 世界书 API

#### 获取世界书列表

```
GET /api/world_info/list?type=all&search=&page=1&page_size=20
```

#### 上传世界书

```
POST /api/upload_world_info
Content-Type: multipart/form-data

files: [worldbook1.json, worldbook2.json]
```

#### 获取世界书详情

```
POST /api/world_info/detail
Content-Type: application/json

{
  "id": "world_info_id",
  "source_type": "global",
  "file_path": "/path/to/file.json",
  "preview_limit": 300,
  "force_full": false
}
```

### SillyTavern 正则汇总 API

```
GET /api/st/regex
```

### 自动化 API

#### 获取规则集列表

```
GET /api/automation/rulesets
```

#### 执行规则

```
POST /api/automation/execute
Content-Type: application/json

{
  "ruleset_id": "ruleset_id",
  "card_ids": ["card_id1", "card_id2"]
}
```

### 系统 API

#### 获取系统状态

```
GET /api/system/status
```

#### 扫描文件系统

```
POST /api/system/scan
Content-Type: application/json

{
  "full_scan": true
}
```

---

## 🛠️ 开发指南

### 开发环境设置

1. **安装开发依赖**

```bash
pip install -r requirements.txt
pip install black flake8 mypy pylint
```

2. **启动调试模式**

```bash
python app.py --debug
# 或
FLASK_DEBUG=1 python app.py
```

调试模式会启用热重载，修改代码后自动重启。

### 代码风格

项目遵循以下代码规范：

#### Python 代码风格

```python
# 导入顺序：标准库 -> 第三方库 -> 本地模块
import os
import sys
import json

from flask import Blueprint, request, jsonify

from core.config import CARDS_FOLDER, load_config
from core.utils.image import extract_card_info


# 命名约定
class ClassName:        # PascalCase
def function_name():    # snake_case
CONSTANT_VALUE = 1      # UPPER_CASE
_private_method()      # _leading_underscore


# 类型提示（推荐）
def process_card(card_id: str, data: dict) -> bool:
    """处理角色卡数据"""
    try:
        # 业务逻辑
        return True
    except Exception as e:
        logger.error(f"Failed to process card: {e}")
        return False


# 错误处理
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    logger.error(f"File not found: {filepath}")
    return None
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON: {e}")
    return None
```

#### 前端代码风格

```javascript
// 使用模块化
import { Alpine } from 'alpinejs';
import { marked } from 'marked';

// 数据函数
function cardData() {
    return {
        loading: false,
        cards: [],
        selectedIds: [],
        
        async loadCards() {
            this.loading = true;
            try {
                const response = await fetch('/api/list_cards');
                const data = await response.json();
                this.cards = data.cards;
            } catch (error) {
                console.error('Failed to load cards:', error);
            } finally {
                this.loading = false;
            }
        },
        
        toggleSelect(id) {
            const idx = this.selectedIds.indexOf(id);
            if (idx > -1) {
                this.selectedIds.splice(idx, 1);
            } else {
                this.selectedIds.push(id);
            }
        }
    };
}
```

### 数据库结构

#### 卡片元数据表（card_metadata）

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

#### 世界书剪切板表（wi_clipboard）

```sql
CREATE TABLE wi_clipboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_json TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at REAL DEFAULT (strftime('%s', 'now'))
);
```

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单个测试
pytest tests/test_card_service.py::test_extract_card_info
```

### 代码质量检查

```bash
# 格式化代码
black .

# 检查代码风格
flake8 .

# 类型检查
mypy core/
```

---

## 🔧 故障排除

### 常见问题

#### 1. 端口被占用

**错误信息**：
```
❌ 启动失败：地址 127.0.0.1:5000 已被占用！
```

**解决方案**：
- 关闭其他占用端口的程序
- 修改 `config.json` 中的 `port` 设置为其他端口

#### 2. 数据库锁定

**错误信息**：
```
database is locked
```

**解决方案**：
- 关闭所有 ST-Manager 实例
- 删除 `data/system/db/cards_metadata.db-wal` 和 `-shm` 文件
- 重启程序

#### 3. 缩略图生成失败

**症状**：卡片缩略图显示为空白

**解决方案**：
- 检查图片文件是否损坏
- 清空 `data/system/thumbnails/` 目录
- 重启程序重新生成

#### 4. 自动扫描不工作

**症状**：文件修改后界面不更新

**解决方案**：
- 检查 `config.json` 中 `enable_auto_scan` 是否为 `true`
- 检查是否安装了 `watchdog` 库
- 手动触发扫描：系统设置 → 扫描文件系统

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发规范

- 遵循现有的代码风格
- 为新功能添加测试
- 更新相关文档
- 编写清晰的提交信息

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) - 本项目管理的目标程序
- [Flask](https://flask.palletsprojects.com/) - Web 框架
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架
- [Alpine.js](https://alpinejs.dev/) - 轻量级 JavaScript 框架

---

## 📮 联系方式

- 问题反馈：[GitHub Issues](https://github.com/Dadihu123/ST-Manager/issues)
- 功能建议：[Discord 类脑](https://discord.com/channels/1134557553011998840/1448353646596325578)

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！**

Made with ❤️ by ST-Manager Team

</div>
