"""
core/auth.py
外网访问身份验证模块

功能:
- 使用 IP 白名单机制控制免登录访问
- 默认仅允许 127.0.0.1 (本机) 免登录
- 用户可自定义添加信任的 IP 或 IP 段到白名单
- 不在白名单内的访问需要账号密码验证
"""

import os
import secrets
import hashlib
import logging
import ipaddress
from functools import wraps
from flask import request, session, redirect, url_for, render_template_string, jsonify

from core.config import load_config

logger = logging.getLogger(__name__)

# 默认白名单（仅本机）
DEFAULT_TRUSTED_IPS = ['127.0.0.1', '::1']


def get_real_ip():
    """
    获取真实客户端 IP，考虑反向代理情况
    """
    # 常见的反向代理头
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # X-Forwarded-For 可能包含多个 IP，取第一个（原始客户端）
        return forwarded_for.split(',')[0].strip()

    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()

    return request.remote_addr or ''


def get_trusted_ips():
    """
    获取信任的 IP 白名单列表
    格式支持：
    - 单个 IP: "192.168.1.100"
    - IP 段 (CIDR): "192.168.1.0/24"
    - 通配符: "192.168.1.*" (会转换为 CIDR)
    """
    cfg = load_config()
    user_whitelist = cfg.get('auth_trusted_ips', [])

    # 合并默认白名单和用户白名单
    return DEFAULT_TRUSTED_IPS + list(user_whitelist)


def normalize_ip_pattern(pattern):
    """
    标准化 IP 模式，将通配符格式转换为 CIDR
    例如: "192.168.1.*" -> "192.168.1.0/24"
         "192.168.*.*" -> "192.168.0.0/16"
    """
    pattern = pattern.strip()

    # 处理通配符格式
    if '*' in pattern:
        parts = pattern.split('.')
        cidr_bits = 0
        normalized_parts = []

        for part in parts:
            if part == '*':
                normalized_parts.append('0')
            else:
                normalized_parts.append(part)
                cidr_bits += 8

        if len(normalized_parts) == 4:
            return f"{'.'.join(normalized_parts)}/{cidr_bits}"

    return pattern


def is_ip_in_whitelist(ip, whitelist):
    """
    检查 IP 是否在白名单中
    """
    if not ip:
        return False

    # 处理 localhost 别名
    if ip == 'localhost':
        ip = '127.0.0.1'

    try:
        client_ip = ipaddress.ip_address(ip)
    except ValueError:
        # 无法解析的 IP，不在白名单中
        return False

    for pattern in whitelist:
        pattern = normalize_ip_pattern(pattern)

        try:
            # 尝试作为单个 IP 匹配
            if '/' not in pattern:
                if client_ip == ipaddress.ip_address(pattern):
                    return True
            else:
                # 作为网络段匹配
                network = ipaddress.ip_network(pattern, strict=False)
                if client_ip in network:
                    return True
        except ValueError:
            # 无效的模式，跳过
            continue

    return False


def is_trusted_request():
    """
    判断是否为受信任的请求（在白名单中）
    """
    ip = get_real_ip()
    whitelist = get_trusted_ips()
    return is_ip_in_whitelist(ip, whitelist)


def get_auth_credentials():
    """
    获取认证凭据，优先级：环境变量 > 配置文件
    返回 (username, password) 元组
    """
    # 优先从环境变量读取
    env_username = os.environ.get('STM_AUTH_USER', '').strip()
    env_password = os.environ.get('STM_AUTH_PASS', '').strip()

    if env_username and env_password:
        return env_username, env_password

    # 从配置文件读取
    cfg = load_config()
    cfg_username = cfg.get('auth_username', '').strip()
    cfg_password = cfg.get('auth_password', '').strip()

    return cfg_username, cfg_password


def is_auth_enabled():
    """
    检查是否启用了外网认证（配置了用户名和密码）
    支持环境变量: STM_AUTH_USER, STM_AUTH_PASS
    """
    username, password = get_auth_credentials()
    return bool(username and password)


def verify_credentials(username, password):
    """
    验证用户名和密码
    """
    stored_username, stored_password = get_auth_credentials()

    if not stored_username or not stored_password:
        return False

    return username == stored_username and password == stored_password


def is_authenticated():
    """
    检查当前会话是否已认证
    """
    return session.get('authenticated', False)


def login_user():
    """
    标记当前会话为已认证
    """
    session['authenticated'] = True
    session.permanent = True  # 使用持久会话


def logout_user():
    """
    登出当前会话
    """
    session.pop('authenticated', None)


def check_auth():
    """
    检查是否需要认证，返回 True 表示通过（无需认证或已认证）
    """
    # 白名单内的请求直接放行
    if is_trusted_request():
        return True

    # 未启用认证，直接放行
    if not is_auth_enabled():
        return True

    # 检查是否已登录
    return is_authenticated()


# === 登录页面 HTML ===
LOGIN_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ST Manager - 登录</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #fff;
            font-size: 28px;
            margin-bottom: 8px;
        }
        .login-header p {
            color: rgba(255, 255, 255, 0.6);
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 8px;
            font-size: 14px;
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: #fff;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        .form-group input:focus {
            outline: none;
            border-color: #3b82f6;
            background: rgba(255, 255, 255, 0.15);
        }
        .form-group input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }
        .login-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            border: none;
            border-radius: 8px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -10px rgba(59, 130, 246, 0.5);
        }
        .login-btn:active {
            transform: translateY(0);
        }
        .error-msg {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #fca5a5;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            text-align: center;
        }
        .security-note {
            margin-top: 20px;
            padding: 12px;
            background: rgba(59, 130, 246, 0.1);
            border-radius: 8px;
            color: rgba(255, 255, 255, 0.6);
            font-size: 12px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🔐 ST Manager</h1>
            <p>外网访问需要身份验证</p>
        </div>
        
        {% if error %}
        <div class="error-msg">{{ error }}</div>
        {% endif %}
        
        <form method="POST" action="/auth/login">
            <div class="form-group">
                <label for="username">用户名</label>
                <input type="text" id="username" name="username" placeholder="请输入用户名" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">密码</label>
                <input type="password" id="password" name="password" placeholder="请输入密码" required>
            </div>
            <button type="submit" class="login-btn">登 录</button>
        </form>

        <div class="security-note">
            🛡️ 您的 IP: {{ client_ip }}<br>
            <span style="font-size: 11px; opacity: 0.7;">如需免登录访问，请在设置中将此 IP 添加到白名单</span>
        </div>
    </div>
</body>
</html>
'''


def init_auth(app):
    """
    初始化认证模块，注册相关路由和钩子
    """
    # 设置 Secret Key（用于 Session 加密）
    if not app.secret_key:
        # 尝试从环境变量获取，否则生成一个持久的密钥
        secret_key = os.environ.get('STM_SECRET_KEY')
        if not secret_key:
            # 生成随机密钥并存储到配置目录
            from core.config import DATA_DIR
            key_file = os.path.join(DATA_DIR, '.secret_key')
            if os.path.exists(key_file):
                with open(key_file, 'r') as f:
                    secret_key = f.read().strip()
            else:
                secret_key = secrets.token_hex(32)
                try:
                    with open(key_file, 'w') as f:
                        f.write(secret_key)
                except:
                    pass
        app.secret_key = secret_key
    
    # 配置 Session
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 天

    # === 登录页面路由 ===
    @app.route('/auth/login', methods=['GET', 'POST'])
    def auth_login():
        client_ip = get_real_ip()

        # 白名单内直接重定向到首页
        if is_trusted_request():
            return redirect('/')

        # 未启用认证也重定向
        if not is_auth_enabled():
            return redirect('/')

        error = None
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            if verify_credentials(username, password):
                login_user()
                logger.info(f"用户 '{username}' 从 {client_ip} 登录成功")
                # 重定向到原始请求页面或首页
                next_url = request.args.get('next', '/')
                return redirect(next_url)
            else:
                error = "用户名或密码错误"
                logger.warning(f"登录失败: 用户 '{username}' 从 {client_ip}")

        return render_template_string(LOGIN_PAGE_TEMPLATE, error=error, client_ip=client_ip)

    # === 登出路由 ===
    @app.route('/auth/logout')
    def auth_logout():
        logout_user()
        return redirect('/auth/login')

    # === 全局认证检查 ===
    @app.before_request
    def check_authentication():
        # 排除静态资源和认证相关路由
        excluded_paths = (
            '/static/',
            '/auth/',
            '/favicon.ico',
        )
        
        path = request.path
        for excluded in excluded_paths:
            if path.startswith(excluded):
                return None
        
        # 检查认证
        if not check_auth():
            # API 请求返回 401
            if path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized',
                    'message': '需要登录才能访问此接口'
                }), 401
            
            # 页面请求重定向到登录页
            return redirect(f'/auth/login?next={request.path}')
        
        return None

    logger.info("认证模块已初始化")


# === 命令行工具 ===
def cli_set_auth(username, password):
    """
    通过命令行设置认证账号密码
    """
    from core.config import load_config, save_config

    cfg = load_config()
    cfg['auth_username'] = username
    cfg['auth_password'] = password

    if save_config(cfg):
        print(f"✅ 认证设置成功！")
        print(f"   用户名: {username}")
        print(f"   密码: {'*' * len(password)}")
        return True
    else:
        print("❌ 保存配置失败")
        return False


def cli_add_trusted_ip(ip):
    """
    通过命令行添加信任 IP
    """
    from core.config import load_config, save_config

    cfg = load_config()
    trusted_ips = cfg.get('auth_trusted_ips', [])

    if ip in trusted_ips:
        print(f"⚠️ IP {ip} 已在白名单中")
        return False

    trusted_ips.append(ip)
    cfg['auth_trusted_ips'] = trusted_ips

    if save_config(cfg):
        print(f"✅ 已添加信任 IP: {ip}")
        return True
    else:
        print("❌ 保存配置失败")
        return False


def cli_show_status():
    """
    显示当前认证状态
    """
    username, password = get_auth_credentials()
    from core.config import load_config
    cfg = load_config()
    trusted_ips = cfg.get('auth_trusted_ips', [])

    print("\n🔐 ST Manager 认证状态")
    print("=" * 40)

    if username and password:
        # 检查来源
        env_user = os.environ.get('STM_AUTH_USER', '').strip()
        source = "环境变量" if env_user else "配置文件"
        print(f"✅ 认证已启用 (来源: {source})")
        print(f"   用户名: {username}")
        print(f"   密码: {'*' * len(password)}")
    else:
        print("❌ 认证未启用")
        print("   (未设置用户名和密码)")

    print(f"\n📋 IP 白名单:")
    print(f"   固定: 127.0.0.1, ::1 (本机)")
    if trusted_ips:
        for ip in trusted_ips:
            print(f"   自定义: {ip}")
    else:
        print(f"   自定义: (无)")

    print("\n💡 使用提示:")
    print("   设置账号: python -m core.auth --set-auth <用户名> <密码>")
    print("   添加白名单: python -m core.auth --add-ip <IP地址>")
    print("   环境变量: STM_AUTH_USER, STM_AUTH_PASS")
    print()


def main():
    """
    命令行入口
    用法:
        python -m core.auth                          # 显示状态
        python -m core.auth --set-auth <用户名> <密码>  # 设置账号密码
        python -m core.auth --add-ip <IP地址>         # 添加信任 IP
    """
    import sys

    args = sys.argv[1:]

    if not args:
        cli_show_status()
        return

    if args[0] == '--set-auth' and len(args) >= 3:
        cli_set_auth(args[1], args[2])
    elif args[0] == '--add-ip' and len(args) >= 2:
        cli_add_trusted_ip(args[1])
    elif args[0] in ('-h', '--help'):
        print(main.__doc__)
    else:
        print("❌ 无效的参数")
        print(main.__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
