# 配置说明

程序首次运行时会自动生成 `config.json` 配置文件。以下是所有配置项说明。

## 基础配置

```json
{
  "host": "127.0.0.1",
  "port": 5000,
  "dark_mode": true,
  "theme_accent": "blue"
}
```

## 目录配置

```json
{
  "cards_dir": "data/library/characters",
  "world_info_dir": "data/library/lorebooks",
  "chats_dir": "data/library/chats",
  "regex_dir": "data/library/extensions/regex",
  "scripts_dir": "data/library/extensions/tavern_helper",
  "quick_replies_dir": "data/library/extensions/quick-replies",
  "presets_dir": "data/library/presets",
  "resources_dir": "data/assets/card_assets"
}
```

## SillyTavern 本地路径配置

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

## 显示设置

```json
{
  "default_sort": "date_desc",
  "show_header_sort": true,
  "items_per_page": 0,
  "items_per_page_wi": 0,
  "card_width": 220,
  "font_style": "sans",
  "bg_url": "/assets/backgrounds/default_background.jpeg",
  "bg_opacity": 0.45,
  "bg_blur": 2
}
```

### 排序方式

`default_sort` 支持：`date_desc`、`date_asc`、`import_desc`、`import_asc`、`name_asc`、`name_desc`、`token_desc`、`token_asc`

### 其他说明

- `show_header_sort`：是否在主界面顶部显示"临时排序"下拉框（仅影响当前列表，不写回配置）
- `png_deterministic_sort`：是否对 PNG 元数据进行确定性排序（默认关闭，避免改变外部工具的字节级行为）
- `allowed_abs_resource_roots`：允许访问的绝对资源目录白名单（用于资源文件列表接口）
- `wi_preview_limit`：世界书详情预览最大条目数（0 表示不限制）
- `wi_preview_entry_max_chars`：世界书单条内容预览最大字符数（0 表示不截断）
- `wi_entry_history_limit`：世界书条目历史保留数（每条目独立，默认 7）

## 自动保存设置

```json
{
  "auto_save_enabled": false,
  "auto_save_interval": 3,
  "snapshot_limit_manual": 50,
  "snapshot_limit_auto": 5,
  "wi_entry_history_limit": 7
}
```

## 系统设置

```json
{
  "enable_auto_scan": true,
  "png_deterministic_sort": false,
  "allowed_abs_resource_roots": [],
  "wi_preview_limit": 300,
  "wi_preview_entry_max_chars": 2000,
  "wi_entry_history_limit": 7
}
```

---

## 公网/外网访问身份验证

强烈建议：**只要通过内网穿透/公网暴露，就开启认证**。本项目提供"账号密码 + IP/域名白名单"的保护方案：

- **默认仅本机免登录**：`127.0.0.1`、`::1`
- 其他来源（包括局域网）默认都需要登录
- 如需让某些来源免登录，可加入 **IP/域名白名单**

### 配置项

```json
{
  "auth_username": "admin",
  "auth_password": "your_password",
  "auth_trusted_ips": [
    "192.168.1.100",
    "192.168.1.0/24",
    "192.168.*.*",
    "your-ddns.example.com"
  ],
  "auth_domain_cache_seconds": 60,
  "auth_trusted_proxies": [],
  "auth_max_attempts": 5,
  "auth_fail_window_seconds": 600,
  "auth_lockout_seconds": 900,
  "auth_hard_lock_threshold": 50
}
```

### 说明

- 仅当 `auth_username` 和 `auth_password` **都不为空**时才启用认证。
- `auth_trusted_ips` 支持四种格式：单个 IP、CIDR 网段、通配符（如 `192.168.*.*`）、域名（如 `your-ddns.example.com`）。
- `auth_domain_cache_seconds`：白名单域名 DNS 解析缓存时间（秒，默认 60）。
- `auth_trusted_proxies`：仅当请求来自这些代理 IP 时，才信任 `X-Forwarded-For / X-Real-IP`。
- `auth_max_attempts` / `auth_fail_window_seconds` / `auth_lockout_seconds`：登录失败限流与锁定。
- `auth_hard_lock_threshold`：连续失败达到阈值后进入锁定模式（需要后台手动重启）。

### 登录失败限流与锁定模式

- **限流锁定**：默认 10 分钟内失败 ≥ 5 次，锁定 15 分钟。
- **硬锁模式**：连续失败达到阈值（默认 50 次）后，系统进入锁定模式，所有 API 返回 503，需要后台重启。

### 环境变量（适合 Docker/systemd）

认证凭据优先级为：**环境变量 > config.json**。

- `STM_AUTH_USER`：用户名
- `STM_AUTH_PASS`：密码

```bash
STM_AUTH_USER=admin STM_AUTH_PASS=your_password python app.py
```

### 命令行工具（适合纯公网 Linux 服务器首次配置）

```bash
# 查看当前认证状态
python -m core.auth

# 设置账号密码
python -m core.auth --set-auth admin your_password

# 添加白名单
python -m core.auth --add-ip 192.168.*.*
python -m core.auth --add-ip your-ddns.example.com
```

### 反向代理/内网穿透注意事项

本项目会读取 `X-Forwarded-For` / `X-Real-IP` 来识别真实客户端 IP。

- 如果你**直接把 Flask 端口暴露到公网**，请确保代理/网关会**覆盖或移除**客户端自带的这些 Header，避免被伪造。
- 更推荐：在 Nginx/Caddy/Traefik 后面运行，并只允许代理访问后端端口。
- 仅当请求来自 `auth_trusted_proxies` 中的代理地址时，才会信任 `X-Forwarded-For / X-Real-IP`。

---

## Discord 论坛认证配置

用于自动化规则抓取Discord论坛（如类脑）帖子标签的认证信息。

```json
{
  "discord_auth_type": "token",
  "discord_bot_token": "your_discord_token_here",
  "discord_user_cookie": ""
}
```

### 配置项说明

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `discord_auth_type` | 认证方式 | `"token"` 或 `"cookie"`（推荐 Token） |
| `discord_bot_token` | Discord Token | 从浏览器开发者工具获取的 Token 值 |
| `discord_user_cookie` | Discord Cookie | 完整的浏览器 Cookie 字符串（备用方案） |

### 获取 Token 的步骤

1. 在浏览器中打开 Discord 网页版（https://discord.com）并登录账号
2. 按 `F12` 打开开发者工具
3. 按 `Ctrl + Shift + M` 启用移动设备模拟
4. 切换到 **Console（控制台）** 标签
5. **Chrome 浏览器新版限制**：如果提示"无法粘贴代码"，请在控制台手动输入 `allow pasting` 并回车，以解锁粘贴功能
6. 粘贴以下代码并回车：
```javascript
const iframe = document.createElement('iframe');
console.log(
  'Token: %c%s',
  'font-size:16px;',
  JSON.parse(document.body.appendChild(iframe).contentWindow.localStorage.token)
);
iframe.remove();
```
7. 控制台会显示 `Token: xxxxxxxxxxxx`，复制这个值
8. 在 ST-Manager 设置中粘贴保存

### 注意事项

- Token 有过期时间，通常几小时到几天不等
- 如遇 401 错误，请重新获取 Token
- Token 仅保存在本地 `config.json`，不会上传
- 需要 Discord 账号已加入目标服务器并有访问权限
- Cookie 方式（`discord_auth_type: cookie`）为备用方案，成功率较低

---

## SillyTavern 同步配置

```json
{
  "st_data_dir": "D:/SillyTavern",
  "st_url": "http://127.0.0.1:8000",
  "st_auth_type": "basic",
  "st_username": "",
  "st_password": ""
}
```

- `st_data_dir`：SillyTavern 安装目录（留空自动探测常见路径）
- `st_url`：SillyTavern API 地址（如使用 API 模式）
- 支持认证：Basic Auth 或 API Key

### 同步模式

1. **文件系统模式**（推荐）：直接读取 SillyTavern 数据目录，无需 SillyTavern 运行
2. **API 模式**：通过 SillyTavern 的 st-api-wrapper 接口读取，需要 SillyTavern 运行
