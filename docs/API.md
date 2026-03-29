# API 文档

ST-Manager 提供 RESTful API 接口，所有接口返回 JSON 格式。

---

## 角色卡 API

### 获取卡片列表

```
GET /api/list_cards?page=1&page_size=20&category=&tags=&search=&sort=date_desc
```

**参数：**

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `sort` | 排序方式 | `date_desc`、`date_asc`、`import_desc`、`import_asc`、`name_asc`、`name_desc`、`token_desc`、`token_asc` |
| `search_scope` | 搜索范围 | `current`（当前目录）、`all_dirs`（全部目录）、`full`（全量，忽略分类/标签/收藏筛选，仅保留关键词搜索） |

### 更新卡片

```
POST /api/update_card
Content-Type: application/json

{
  "id": "卡片ID",
  "char_name": "角色名称",
  "description": "描述",
  "tags": ["标签1", "标签2"]
}
```

### 移动卡片

```
POST /api/move_card
Content-Type: application/json

{
  "target_category": "目标分类",
  "card_ids": ["卡片ID1", "卡片ID2"]
}
```

### 删除卡片

```
POST /api/delete_cards
Content-Type: application/json

{
  "card_ids": ["卡片ID1", "卡片ID2"]
}
```

---

## 世界书 API

### 获取世界书列表

```
GET /api/world_info/list?type=all&search=&page=1&page_size=20
```

### 上传世界书

```
POST /api/upload_world_info
Content-Type: multipart/form-data

files: [worldbook1.json, worldbook2.json]
```

### 获取世界书详情

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

### 获取条目历史

```
POST /api/world_info/entry_history/list
Content-Type: application/json

{
  "source_type": "lorebook",
  "source_id": "",
  "file_path": "/path/to/file.json",
  "entry_uid": "wi-xxxx",
  "limit": 20
}
```

---

## 聊天记录 API

### 获取聊天列表

```
GET /api/chats/list?page=1&page_size=30&search=&filter=all&card_id=
```

| 参数 | 说明 |
|------|------|
| `filter` | `all` \| `bound` \| `unbound` \| `favorites` |
| `card_id` | 可选，传入后仅返回绑定到指定角色卡的聊天 |

### 获取聊天详情

```
POST /api/chats/detail
Content-Type: application/json

{
  "id": "角色名/聊天文件.jsonl"
}
```

### 更新聊天本地信息

```
POST /api/chats/update_meta
Content-Type: application/json

{
  "id": "角色名/聊天文件.jsonl",
  "display_name": "自定义显示名",
  "notes": "本地备注",
  "favorite": true,
  "last_view_floor": 128
}
```

### 绑定聊天到角色卡

```
POST /api/chats/bind
Content-Type: application/json

{
  "id": "角色名/聊天文件.jsonl",
  "card_id": "card_id"
}
```

### 导入聊天文件

```
POST /api/chats/import
Content-Type: multipart/form-data

files: [chat1.jsonl, chat2.jsonl]
card_id: 可选
character_name: 可选
```

### 保存聊天内容

```
POST /api/chats/save
Content-Type: application/json

{
  "id": "角色名/聊天文件.jsonl",
  "raw_messages": [...],
  "metadata": {...}
}
```

### 搜索聊天正文

```
POST /api/chats/search
Content-Type: application/json

{
  "query": "关键词",
  "limit": 80,
  "card_id": "可选角色卡ID"
}
```

---

## 预设 API

### 获取预设列表

```
GET /api/presets/list?filter_type=all&search=
```

| 参数 | 说明 |
|------|------|
| `filter_type` | `all` \| `global` \| `resource` |
| `search` | 搜索关键词 |

### 获取预设详情

```
GET /api/presets/detail/{preset_id}
```

### 上传预设

```
POST /api/presets/upload
Content-Type: multipart/form-data

files: [preset1.json, preset2.json]
```

### 删除预设

```
POST /api/presets/delete
Content-Type: application/json

{
  "id": "preset_id"
}
```

### 保存预设扩展

```
POST /api/presets/save-extensions
Content-Type: application/json

{
  "id": "preset_id",
  "extensions": {
    "regex_scripts": [...],
    "tavern_helper": { "scripts": [...] }
  }
}
```

---

## 快速回复 API

### 获取快速回复列表

```
GET /api/quick-replies/list?type=all&search=
```

### 获取快速回复详情

```
GET /api/quick-replies/detail/{qr_id}
```

### 上传快速回复

```
POST /api/quick-replies/upload
Content-Type: multipart/form-data

files: [quickreply1.json]
```

---

## 正则脚本 API

### 获取正则脚本列表

```
GET /api/regex/list?source=all
```

| 参数 | 说明 |
|------|------|
| `source` | `all` \| `global` \| `preset` \| `character` |

### 保存正则脚本

```
POST /api/regex/save
Content-Type: application/json

{
  "id": "regex_id",
  "name": "脚本名称",
  "find": "查找模式",
  "replace": "替换内容",
  "enabled": true
}
```

---

## 自动化 API

### 获取规则集列表

```
GET /api/automation/rulesets
```

### 执行规则

```
POST /api/automation/execute
Content-Type: application/json

{
  "ruleset_id": "ruleset_id",
  "card_ids": ["card_id1", "card_id2"]
}
```

---

## 标签分类 API

### 获取标签分类

```
GET /api/tag_taxonomy
```

### 保存标签分类

```
POST /api/tag_taxonomy
Content-Type: application/json

{
  "taxonomy": {
    "default_category": "未分类",
    "category_order": ["未分类", "角色", "题材"],
    "categories": {
      "未分类": {"color": "#64748b", "opacity": 16},
      "角色": {"color": "#3b82f6", "opacity": 22}
    },
    "tag_to_category": {
      "女上": "题材",
      "femdom": "题材"
    }
  }
}
```

---

## 系统 API

### 获取系统状态

```
GET /api/system/status
```

### 扫描文件系统

```
POST /api/system/scan
Content-Type: application/json

{
  "full_scan": true
}
```
