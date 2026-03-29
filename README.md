# ST-Manager

<div align="center">

**SillyTavern 资源可视化管理工具**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

功能强大 • 界面美观 • 操作便捷

</div>

<!-- 主界面效果图 -->
<p align="center">
  <img src="docs/screenshots/hero.png" alt="ST-Manager 主界面" width="900">
</p>

---

## ✨ 功能亮点

<table>
<tr>
<td width="50%">

### 🎴 角色卡管理

- PNG / JSON 格式角色卡浏览与编辑
- 标签分类、收藏、批量操作
- 一键发送到 SillyTavern
- Bundle 多版本管理

</td>
<td width="50%">

<!-- 截图占位：角色卡网格 -->
<img src="docs/screenshots/feature-cards.png" alt="角色卡管理" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 截图占位：聊天阅读器 -->
<img src="docs/screenshots/feature-chats.png" alt="聊天记录管理" width="100%">

</td>
<td width="50%">

### 💬 聊天记录管理

- `.jsonl` 聊天导入、角色绑定、全文检索
- 沉浸式三栏阅读器，楼层导航与收藏
- 楼层编辑、批量查找替换
- 整页实例模式运行前端片段

</td>
</tr>
<tr>
<td width="50%">

### 📚 世界书管理

- 全局 / 资源目录 / 内嵌世界书统一管理
- 在线编辑、剪切板、一键新建
- 版本时光机：快照、回滚、可视化对比
- 条目级独立历史版本

</td>
<td width="50%">

<!-- 截图占位：世界书 -->
<img src="docs/screenshots/feature-wi.png" alt="世界书管理" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 截图占位：预设 -->
<img src="docs/screenshots/feature-presets.png" alt="预设管理" width="100%">

</td>
<td width="50%">

### 📝 预设管理

- 拖拽上传 JSON 预设文件
- 三栏详情阅读器（采样器 / 参数 / Prompts）
- Prompts 筛选（启用 / 禁用 / 全部）
- 正则脚本与 ST 脚本扩展集成

</td>
</tr>
<tr>
<td width="50%">

### 🤖 自动化规则引擎

- 基于条件的自动化任务执行
- 支持标签管理、收藏、论坛标签抓取
- 标签合并（同义标签归并）
- Discord 论坛帖子标签自动同步

</td>
<td width="50%">

<!-- 截图占位：自动化 -->
<img src="docs/screenshots/feature-automation.png" alt="自动化规则引擎" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 截图占位：脚本管理 -->
<img src="docs/screenshots/feature-scripts.png" alt="脚本管理" width="100%">

</td>
<td width="50%">

### 🛠️ 脚本与扩展

- 正则脚本可视化管理
- Tavern Helper 脚本运行 / 重载 / 停止
- 快速回复模板管理
- 运行时检查器统一状态查看

</td>
</tr>
</table>

### 更多特性

- 🔄 **实时同步** — 文件系统自动监听，变更即时同步到数据库
- 🎨 **暗色 / 亮色主题** — 现代化响应式 UI，移动端适配
- 🔍 **智能搜索** — 名称、标签、创作者等多维度搜索，支持搜索范围控制
- 🏷️ **标签系统** — 分类管理、颜色 / 透明度、自定义筛选与批量管理
- 📦 **酒馆资源同步** — 从本地 SillyTavern 一键同步角色卡、聊天、世界书、预设等

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip 包管理器

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Dadihu123/ST-Manager.git
cd ST-Manager

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python app.py
```

程序启动后自动打开浏览器访问 `http://127.0.0.1:5000`。

### Docker 部署

```bash
docker-compose up -d
# 访问 http://localhost:5000
```

---

## 📸 界面展示

> 以下截图均为占位，实际图片请补充到 `docs/screenshots/` 目录。

<!-- 截图展示区 -->
<p align="center">
  <img src="docs/screenshots/gallery-cards-grid.png" alt="角色卡网格" width="420">&nbsp;
  <img src="docs/screenshots/gallery-chat-reader.png" alt="聊天阅读器" width="420">
</p>
<p align="center">
  <img src="docs/screenshots/gallery-wi-editor.png" alt="世界书编辑器" width="420">&nbsp;
  <img src="docs/screenshots/gallery-preset-detail.png" alt="预设详情" width="420">
</p>
<p align="center">
  <img src="docs/screenshots/gallery-automation.png" alt="自动化规则" width="420">&nbsp;
  <img src="docs/screenshots/gallery-settings.png" alt="设置界面" width="420">
</p>

---

## ⚙️ 配置速览

程序首次运行自动生成 `config.json`。常用配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `host` | 监听地址 | `127.0.0.1` |
| `port` | 监听端口 | `5000` |
| `st_url` | SillyTavern 地址 | `http://127.0.0.1:8000` |
| `st_data_dir` | SillyTavern 数据目录（留空自动探测） | `""` |
| `auth_username` | 公网访问用户名（需与密码同时设置） | `""` |

完整配置说明请参阅 → [docs/CONFIG.md](docs/CONFIG.md)

---

## 📖 相关文档

| 文档 | 内容 |
|------|------|
| [配置说明](docs/CONFIG.md) | 完整配置项、Discord 认证、身份验证、环境变量 |
| [API 文档](docs/API.md) | REST API 接口说明（角色卡、聊天、世界书、预设等） |
| [开发指南](docs/DEVELOPMENT.md) | 项目结构、代码风格、数据库结构、测试 |

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送并开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE)。

---

## 🙏 致谢

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 本项目管理的目标程序
- [Flask](https://flask.palletsprojects.com/) — Web 框架
- [Tailwind CSS](https://tailwindcss.com/) — CSS 框架
- [Alpine.js](https://alpinejs.dev/) — 轻量级 JavaScript 框架

---

## 📮 联系方式

- 问题反馈：[GitHub Issues](https://github.com/Dadihu123/ST-Manager/issues)
- 功能建议：[Discord 类脑](https://discord.com/channels/1134557553011998840/1448353646596325578)

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！**

Made with ❤️ by ST-Manager Team

</div>
