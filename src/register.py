#!/usr/bin/env python3
"""Grok4Free Camoufox 注册主流程：创建邮箱 → 注册 → OAuth → token。

从原项目 test_camoufox_mvp.py 搬运并适配，改为使用新项目的本地模块（config、mail_moemail、oauth、account_store）。
完全独立，不依赖原 grok-register 项目。

运行方式:
    python run.py            # GUI 模式（通过 run.py 分发）
    python -m src.register   # CLI 命令行模式（单次注册）
    python -m src.register --count 3 --headless  # 批量注册
"""

import sys
import time
import random
import string
import secrets
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


try:
    from camoufox.sync_api import Camoufox
except ImportError:
    print("❌ 请安装 camoufox: pip install camoufox[geoip]")
    sys.exit(1)


# ============================================================================
# 配置与邮箱服务
# ===========================================================================
def get_proxy_config(raw_override=None):
    """把代理字符串解析成 Camoufox/Playwright 需要的格式。

    Args:
        raw_override: 显式指定的代理字符串（多进程模式下由调度器分配）。
                      为 None 时回退到从 config.json 读取单个 proxy 字段。

    Returns:
        (playwright_proxy, raw_proxy_url): 
          - playwright_proxy: {"server", "username"?, "password"?} 或 None
          - raw_proxy_url: 原始代理字符串（供 OAuth/token 请求复用）
    """
    import urllib.parse

    if raw_override is not None:
        raw = str(raw_override or "").strip()
    else:
        from .config import load_config, get_proxy
        cfg = load_config()
        raw = str(get_proxy(cfg) or "").strip()

    if not raw:
        return None, ""
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parts = urllib.parse.urlsplit(raw)
    except Exception as e:
        print(f"[!] 代理解析失败，将直连：{e}", flush=True)
        return None, ""
    if not parts.hostname:
        print("[!] 代理缺少主机名，将直连", flush=True)
        return None, ""
    scheme = parts.scheme or "http"
    server = f"{scheme}://{parts.hostname}"
    if parts.port:
        server += f":{parts.port}"
    pw_proxy = {"server": server}
    if parts.username:
        pw_proxy["username"] = urllib.parse.unquote(parts.username)
    if parts.password:
        pw_proxy["password"] = urllib.parse.unquote(parts.password)
    return pw_proxy, raw


def create_email():
    """调用 MoEmail 服务创建邮箱，返回 (email, email_id)。"""
    from .config import load_config
    from .mail_moemail import create_email as _create_email
    
    cfg = load_config()
    email, email_id = _create_email(cfg)
    print(f"✅ 已创建真实邮箱：{email} (id={email_id})", flush=True)
    return email, email_id


def fetch_verification_code(email, email_id, timeout=180, log_callback=None, cancel_callback=None):
    """轮询 MoEmail 邮箱获取验证码。"""
    from .config import load_config
    from .mail_moemail import poll_verification_code, extract_verification_code
    
    cfg = load_config()
    
    def my_log(msg):
        if log_callback:
            log_callback(msg)
    
    print(f"[*] 正在为 {email} 拉取验证码（最多等 {timeout} 秒）...", flush=True)
    
    code = poll_verification_code(
        email_id=email_id,
        config=cfg,
        timeout=timeout,
        poll_interval=3,
        log_callback=lambda m: print("   " + m, flush=True),
        resend_callback=None,
        cancel_callback=cancel_callback,
    )
    return code


def fetch_verification_code_graph(graph_account, timeout=180, cancel_callback=None,
                                  submailbox=False):
    """轮询微软邮箱（MS Graph）获取验证码。

    Args:
        graph_account: {"email","password","refresh_token","client_id"}
        submailbox:    True 表示子邮箱模式：换 token 固定走 GRAPH scope，
                       且只提取收件人为本子邮箱地址的邮件（防止共享收件系统串号）。
    """
    from .mail_msgraph import poll_verification_code as _poll_graph, SCOPE_GRAPH

    email = graph_account.get("email", "")
    if submailbox:
        print(f"[*] 正在为子邮箱 {email} 拉取验证码（最多等 {timeout} 秒）...", flush=True)
    else:
        print(f"[*] 正在为微软邮箱 {email} 拉取验证码（最多等 {timeout} 秒）...", flush=True)

    code = _poll_graph(
        client_id=graph_account["client_id"],
        refresh_token=graph_account["refresh_token"],
        tenant=graph_account.get("tenant", "consumers"),
        timeout=timeout,
        poll_interval=3,
        log_callback=lambda m: print("   " + m, flush=True),
        resend_callback=None,
        cancel_callback=cancel_callback,
        target_address=email if submailbox else None,
        force_scope=SCOPE_GRAPH if submailbox else None,
    )
    return code


# ============================================================================
# 注册资料生成（姓名 + 密码）
# ===========================================================================
_GIVEN_NAMES = [
    "Neo", "Ethan", "Liam", "Noah", "Lucas", "Mason", "Ryan", "Leo",
    "Owen", "Aiden", "Ivan", "Nolan", "Evan", "Kai", "Caleb", "Adam",
    "Ezra", "Miles", "Logan", "Carter", "Hunter", "Jason", "Brian", "Dylan",
    "Alex", "Colin", "Blake", "Gavin", "Henry", "Julian", "Kevin", "Louis",
    "Marcus", "Nathan", "Oscar", "Peter", "Simon", "Victor", "Wesley", "Felix",
]
_FAMILY_NAMES = [
    "Lin", "Wang", "Zhao", "Liu", "Chen", "Zhang", "Xu", "Sun",
    "Guo", "Yang", "Wu", "Zhou", "Tang", "Qin", "Shi", "Fang",
    "Peng", "Cao", "Deng", "Fan", "Gao", "Han", "Hu", "Jiang",
    "Lu", "Ma", "Pan", "Ren", "Tian", "Xie", "Yan", "Yao",
    "Yu", "Zeng", "Bai", "Hou", "Jin", "Luo", "Song", "Wei",
]


def generate_password(length=10):
    """生成随机密码：含大写、小写、数字、特殊符号各至少 1 个。"""
    if length < 4:
        length = 4
    lowers = string.ascii_lowercase
    uppers = string.ascii_uppercase
    digits = string.digits
    specials = "!@#$%^&*-_=+"
    chars = [
        secrets.choice(lowers),
        secrets.choice(uppers),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    pool = lowers + uppers + digits + specials
    chars += [secrets.choice(pool) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def build_profile():
    """返回 (given_name, family_name, password)。"""
    given_name = secrets.choice(_GIVEN_NAMES)
    family_name = secrets.choice(_FAMILY_NAMES)
    password = generate_password(10)
    return given_name, family_name, password


# ============================================================================
# 拟人化鼠标/键盘工具
# ===========================================================================
def _move_to(page, box):
    """移动到元素框内一个略偏离中心的随机点，返回点击坐标"""
    tx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
    ty = box["y"] + box["height"] * random.uniform(0.35, 0.65)
    page.mouse.move(tx, ty)
    return tx, ty


def human_click(page, selector: str, state: dict, label="元素") -> bool:
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=10_000)
        loc.scroll_into_view_if_needed(timeout=5_000)
        box = loc.bounding_box()
        if not box:
            print(f"⚠️ 无法获取 {label} 坐标")
            return False
        tx, ty = _move_to(page, box)
        time.sleep(random.uniform(0.05, 0.18))
        page.mouse.click(tx, ty, delay=random.uniform(40, 110))
        state["pos"] = (tx, ty)
        print(f"✅ 拟人化点击：{label}")
        return True
    except Exception as e:
        print(f"❌ {label} 点击失败：{e}")
        return False


def human_type(page, selector: str, text: str, state: dict, label="输入框") -> bool:
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=10_000)
        loc.scroll_into_view_if_needed(timeout=5_000)
        box = loc.bounding_box()
        if not box:
            print(f"⚠️ 无法获取 {label} 坐标")
            return False
        tx, ty = _move_to(page, box)
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.click(tx, ty, delay=random.uniform(40, 90))
        state["pos"] = (tx, ty)
        time.sleep(random.uniform(0.15, 0.35))
        for ch in text:
            page.keyboard.type(ch, delay=random.uniform(45, 140))
            if random.random() < 0.06:
                time.sleep(random.uniform(0.08, 0.2))
        time.sleep(random.uniform(0.05, 0.15))
        try:
            val = loc.input_value(timeout=2000)
        except Exception:
            val = ""
        ok = val.strip() == text.strip()
        print(f"{'✅' if ok else '⚠️'} 拟人化输入：{label} -> '{val}' (期望 '{text}')")
        return ok
    except Exception as e:
        print(f"❌ {label} 输入失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def human_type_otp(page, selector: str, text: str, state: dict, label="验证码") -> bool:
    """针对 OTP 输入框的特殊填写（支持 input-otp 组件）。"""
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=10_000)
        
        # 尝试多种方式聚焦并点击
        box = loc.bounding_box()
        if box:
            tx, ty = _move_to(page, box)
            time.sleep(random.uniform(0.05, 0.15))
            page.mouse.click(tx, ty, delay=random.uniform(40, 90))
            state["pos"] = (tx, ty)
        else:
            loc.focus()
        
        time.sleep(random.uniform(0.05, 0.15))
        
        # 逐字符输入
        for ch in text:
            page.keyboard.type(ch, delay=random.uniform(60, 140))
        
        time.sleep(random.uniform(0.1, 0.25))
        
        # 尝试多种方法验证输入值
        val = ""
        methods = [
            # 1. JavaScript querySelector
            lambda: page.evaluate(
                "(sel) => { const e = document.querySelector(sel); return e ? (e.value || '') : ''; }",
                selector,
            ),
            # 2. direct value from locator
            lambda: loc.input_value(timeout=2000),
            # 3. data-input-value attribute (input-otp 常用)
            lambda: page.locator(selector).first.get_attribute("data-input-value"),
            # 4. first child input's value
            lambda: page.locator(f"{selector} input").first.input_value(timeout=2000),
        ]
        
        for method in methods:
            try:
                val = method()
                if val and len(val) == len(text):
                    break
            except Exception:
                continue
        
        ok = str(val).strip().upper() == str(text).strip().upper()
        print(f"{'✅' if ok else '⚠️'} 拟人化输入：{label} -> '{val}' (期望 '{text}')", flush=True)
        return ok
    except Exception as e:
        import traceback
        print(f"❌ {label} 输入失败：{e}", flush=True)
        traceback.print_exc()
        return False


def _accept_all_cookies(page):
    """自动点击 OneTrust Cookie 同意按钮（如果存在）。"""
    try:
        # 尝试点击"接受所有 Cookie"按钮
        buttons = [
            "#onetrust-accept-btn-handler",
            "#onetrust-reject-all-sticky",
            "[id*='onetrust']",
            ".ot-sdk-btn-consent",
        ]

        for selector in buttons:
            try:
                page.wait_for_selector(selector, timeout=2000)
                element = page.query_selector(selector)
                if element:
                    print(f"✅ 已点击 Cookie 同意按钮：{selector}", flush=True)
                    element.click(timeout=3000)
                    return True
            except Exception:
                continue

        # 如果没有找到，返回 None 表示无需处理
        return None
    except Exception as e:
        print(f"⚠️ Cookie 同意检查失败（忽略）: {e}", flush=True)
        return None


def _get_turnstile_token(page):
    """读取 Turnstile 的 response token，没有则返回空串。"""
    try:
        token = page.evaluate(
            """() => {
                const el = document.querySelector('input[name="cf-turnstile-response"]');
                return el ? (el.value || '') : '';
            }"""
        )
        return str(token) if token else ""
    except Exception:
        return ""


def _human_click_turnstile(page):
    """检测并拟人化点击 Turnstile 的交互式 checkbox（偶发需要手点时的兜底）。

    Turnstile 的 iframe 在 DOM 中 src 属性常为空（内容由 JS 注入），无法用
    src/title 选择器匹配。改用 Playwright 的 page.frames 读取 frame 真实 URL，
    定位到 challenges.cloudflare.com 的 frame，再对其左侧 checkbox 位置做
    拟人化坐标点击（穿透 iframe）。找不到则退化到容器选择器。
    返回 True 表示执行了点击动作。
    """
    # ---- 方案 1：通过 Playwright 的 frames 找真实 URL（DOM 里 src 属性可能为空）----
    try:
        for fr in page.frames:
            furl = (fr.url or "").lower()
            if "challenges.cloudflare.com" in furl or "turnstile" in furl:
                try:
                    handle = fr.frame_element()
                    box = handle.bounding_box()
                    if box and box["width"] > 10 and box["height"] > 10:
                        print(f"🖱️ 通过 frame URL 定位到 Turnstile（{box['width']:.0f}x{box['height']:.0f}），拟人化点击...", flush=True)
                        _human_mouse_move(page, box)
                        cx = box["x"] + min(30, box["width"] * 0.12)
                        cy = box["y"] + box["height"] / 2
                        page.mouse.click(cx, cy, delay=random.randint(50, 80))  # 加速：50-80ms
                        print(f"✅ 已对 Turnstile 执行坐标点击 ({cx:.0f}, {cy:.0f})", flush=True)
                        return True
                except Exception as e:
                    print(f"[DEBUG] frame 定位点击失败：{e}", flush=True)
    except Exception as e:
        print(f"[DEBUG] 遍历 frames 失败：{e}", flush=True)

    # ---- 方案 2：找 Turnstile 容器/输入框，点击其所在区域 ----
    # Turnstile 会在页面注入一个容器 div 和隐藏 input[name=cf-turnstile-response]，
    # 交互式 checkbox 的 iframe 就挂在容器里。直接对容器区域做坐标点击即可穿透 iframe。
    container_selectors = [
        '.cf-turnstile',
        'div[class*="turnstile"]',
        'div[id*="turnstile"]',
        'iframe[src=""]',          # 本例中 Turnstile iframe 的 src 为空
        'iframe:not([title="onetrust-text-resize"])',
    ]
    for sel in container_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            box = loc.bounding_box()
            if not box or box["width"] < 20 or box["height"] < 20:
                continue
            print(f"🖱️ 通过容器选择器（{sel}）定位到验证区，拟人化点击...", flush=True)
            _human_mouse_move(page, box, accelerated=True)  # 加速模式
            cx = box["x"] + min(30, box["width"] * 0.12)
            cy = box["y"] + box["height"] / 2
            page.mouse.click(cx, cy, delay=random.randint(50, 80))  # 加速：50-80ms
            print(f"✅ 已对验证区执行坐标点击 ({cx:.0f}, {cy:.0f})", flush=True)
            return True
        except Exception as e:
            print(f"[DEBUG] 容器选择器 {sel} 出错：{e}", flush=True)
            continue

    # ---- 诊断：如果都没找到，打印当前所有 frame 的 URL 和 iframe 尺寸 ----
    try:
        frame_urls = [fr.url for fr in page.frames]
        print(f"[DEBUG] 当前所有 frame URL：{frame_urls}", flush=True)
        info = page.evaluate(
            """() => Array.from(document.querySelectorAll('iframe')).map(f => {
                const r = f.getBoundingClientRect();
                return {src: f.src || '', title: f.title || '', w: r.width, h: r.height, x: r.x, y: r.y};
            })"""
        )
        print(f"[DEBUG] 页面 iframe 列表：{info}", flush=True)
    except Exception:
        pass

    print("[DEBUG] 未匹配到任何 Turnstile 验证框（可能尚未展开）", flush=True)
    return False


def _human_mouse_move(page, box, accelerated=True):
    """把鼠标以分段、带随机抖动的轨迹移动到目标区域中心，模拟真人。
    
    accelerated: True 时大幅减少步数和延迟，用于生产环境；False 时保持慢速拟人。
    """
    try:
        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2
        
        if accelerated:
            steps = random.randint(2, 4)           # 快：2-4 步（原 8-16）
            step_delay = (0.003, 0.01)             # 快：每步 3-10ms（原 10-50ms）
            post_delay = (0.05, 0.15)              # 快：结束后 50-150ms（原 150-400ms）
        else:
            steps = random.randint(8, 16)          # 慢：8-16 步
            step_delay = (0.01, 0.05)
            post_delay = (0.15, 0.4)
        
        start_x = target_x - random.randint(120, 260)
        start_y = target_y - random.randint(80, 200)
        for i in range(1, steps + 1):
            t = i / steps
            x = start_x + (target_x - start_x) * t + random.uniform(-3, 3)
            y = start_y + (target_y - start_y) * t + random.uniform(-3, 3)
            page.mouse.move(x, y)
            time.sleep(random.uniform(*step_delay))
        time.sleep(random.uniform(*post_delay))
    except Exception:
        pass


def wait_for_turnstile(page, timeout=90, cancel_callback=None):
    """等待 Cloudflare Turnstile 验证完成。

    优先等待自动通过；若等待超过一定时间仍无 token，则判定为进入了
    interactive 模式（偶发），检测 iframe 并拟人化点击 checkbox 作为兜底。
    """
    print("⏳ 等待 Turnstile 自动验证...", flush=True)
    deadline = time.time() + timeout
    start = time.time()
    interactive_wait = 6.0   # 等待自动通过的秒数，超过则尝试手点
    last_click = 0.0
    click_cooldown = 8.0     # 两次点击之间的冷却，避免疯狂连点

    while time.time() < deadline:
        _check_cancel(cancel_callback)

        # 1. 已拿到 token → 成功
        token = _get_turnstile_token(page)
        if token and len(token) > 20:
            print(f"✅ Turnstile 已完成 (token 长度 {len(token)})", flush=True)
            return True

        # 2. 显示 "成功" 文本 → 成功
        try:
            if page.locator("text=成功").count() > 0 and page.locator("text=成功").first.is_visible():
                print("✅ Turnstile 显示 '成功！'", flush=True)
                return True
        except Exception:
            pass

        # 3. 等待超过 interactive_wait 仍无 token，且过了冷却期 → 尝试拟人化点击
        elapsed = time.time() - start
        if elapsed > interactive_wait and (time.time() - last_click) > click_cooldown:
            if _human_click_turnstile(page):
                last_click = time.time()
                time.sleep(random.uniform(0.8, 1.5))  # 点后给 Cloudflare 后台验证时间
                continue

        time.sleep(1.5)

    print("⚠️ Turnstile 等待超时", flush=True)
    return False


def oauth_authorize_login(page, state, email, password, timeout=90, cancel_callback=None):
    """在同一浏览器中完成 OAuth 设备授权登录。"""
    _check_cancel(cancel_callback)
    print("\n🔐 OAuth 授权登录流程开始...", flush=True)

    # 点击「继续」
    try:
        btn = page.locator('button[type="submit"]').filter(has_text="继续").first
        if btn.count() > 0:
            print("👆 点击 '继续'...", flush=True)
            time.sleep(1.2)
            btn.click(delay=100)
            time.sleep(0.8)
            print("✅ 已点击 '继续'", flush=True)
        else:
            print("[DEBUG] 未找到 '继续' 按钮", flush=True)
    except Exception as e:
        print(f"[DEBUG] 点击继续失败：{e}", flush=True)

    time.sleep(1.5)

    # 检测分支：允许授权页（已登录）还是 使用邮箱登录（未登录）
    allow_exists = False
    email_login_exists = False
    try:
        allow_exists = page.locator('button[type="submit"]').filter(has_text="允许").count() > 0
    except Exception:
        pass
    try:
        email_login_exists = page.locator('button[data-testid="continue-with-email"]').count() > 0
    except Exception:
        pass

    print(f"[DEBUG] 分支检测：允许={allow_exists}, 邮箱登录={email_login_exists}", flush=True)

    # 情况 B：已登录，直接授权（可能需要「继续」→「允许」多步）
    if allow_exists:
        print("🅱️ 检测到授权确认页（账号已登录）...", flush=True)
        _handle_authorize_buttons(page, cancel_callback=cancel_callback, timeout=timeout)
        print("✅ OAuth 授权登录执行完毕（免密授权）", flush=True)
        time.sleep(0.5)
        return True

    # 情况 A：未登录，走邮箱密码登录
    # 点击「使用邮箱登录」+ 重试（10 轮，每轮 5 秒），防止网速慢导致按钮未加载
    email_login_clicked = False
    for attempt in range(10):
        _check_cancel(cancel_callback)
        # 若邮箱输入框已经出现，说明已进入登录页，无需再点
        try:
            if page.locator('input[data-testid="email"]').count() > 0:
                email_login_clicked = True
                break
        except Exception:
            pass
        try:
            btn = page.locator('button[data-testid="continue-with-email"]').first
            if btn.count() > 0 and btn.is_visible():
                print("👆 A：点击 '使用邮箱登录'...", flush=True)
                time.sleep(1.2)
                btn.click(delay=100)
                time.sleep(0.8)  # 等待跳转到新页面
                print("✅ 已点击 '使用邮箱登录'", flush=True)
                email_login_clicked = True
                break
        except Exception as e:
            print(f"[DEBUG] 点击使用邮箱登录失败：{e}", flush=True)
        print(f"[DEBUG] 第 {attempt + 1}/10 次未找到 '使用邮箱登录' 按钮，5 秒后重试...", flush=True)
        time.sleep(5.0)

    if not email_login_clicked:
        print("[DEBUG] 多轮未找到 '使用邮箱登录' 按钮", flush=True)

    time.sleep(1.5)
    
    # 检查是否需要先点 "下一步" / "继续"
    _check_cancel(cancel_callback)

    # 填写邮箱（同样加重试，等待邮箱输入框出现）
    email_input_found = False
    for attempt in range(10):
        _check_cancel(cancel_callback)
        try:
            if page.locator('input[data-testid="email"]').count() > 0:
                email_input_found = True
                break
        except Exception:
            pass
        print(f"[DEBUG] 第 {attempt + 1}/10 次未找到邮箱输入框，5 秒后重试...", flush=True)
        time.sleep(5.0)

    if email_input_found:
        print("📧 填写登录邮箱...", flush=True)
        human_type(page, 'input[data-testid="email"]', email, state, "登录邮箱")
        time.sleep(0.8)
        
        # 尝试点击 "下一步" / "继续" 按钮
        try:
            submit_btn = page.locator('button[type="submit"]').filter(has_text="下一步").first
            if submit_btn.count() > 0:
                print("👆 点击 '下一步'...", flush=True)
                submit_btn.click(delay=100)
                time.sleep(0.5)  # 等待跳转到密码页
                print("✅ 已点击 '下一步'", flush=True)
            else:
                submit_btn = page.locator('button[type="submit"]').filter(has_text="继续").first
                if submit_btn.count() > 0:
                    print("👆 点击 '继续'...", flush=True)
                    submit_btn.click(delay=100)
                    time.sleep(0.5)
                    print("✅ 已点击 '继续'", flush=True)
        except Exception:
            print("[DEBUG] 无'下一步'/ '继续'按钮，直接进入密码输入", flush=True)
            
    else:
        print("⚠️ OAuth 登录页未找到邮箱输入框", flush=True)
        return False

    _check_cancel(cancel_callback)
    time.sleep(1.0)

    # 填写密码（尝试多种选择器 + 重试，防止网速慢导致密码页未加载出来）
    password_selector = None
    password_selectors = ['input[data-testid="password"]', 'input[type="password"]', 'input[name="password"]']
    for attempt in range(5):  # 最多 5 次，每次间隔 2 秒 = 共 10 秒
        _check_cancel(cancel_callback)
        for sel in password_selectors:
            try:
                if page.locator(sel).count() > 0:
                    password_selector = sel
                    break
            except Exception:
                continue
        if password_selector:
            break
        print(f"[DEBUG] 第 {attempt + 1}/5 次未找到密码输入框，2 秒后重试...", flush=True)
        time.sleep(2.0)

    if password_selector:
        print(f"🔑 在 {password_selector} 填写登录密码...", flush=True)
        human_type(page, password_selector, password, state, "登录密码")
    else:
        print("⚠️ OAuth 登录页未找到密码输入框", flush=True)
        return False

    time.sleep(1.0)

    # 等待 Turnstile
    # 先点击 Cookie 同意按钮（如果存在）
    _accept_all_cookies(page)
    
    print("🛡️ 等待 Turnstile 验证...", flush=True)
    wait_for_turnstile(page, timeout=timeout, cancel_callback=cancel_callback)

    # 点击「登录」
    try:
        btn = page.locator('button[data-testid="sign-in-submit"]').first
        if btn.count() > 0:
            print("🎯 点击 '登录'...", flush=True)
            time.sleep(1.2)
            btn.click(delay=100)
            print("✅ 已点击 '登录'！", flush=True)
        else:
            btn = page.locator('button[type="submit"]').filter(has_text="登录").first
            if btn.count() > 0:
                print("🎯 点击 '登录'（文本匹配）...", flush=True)
                time.sleep(1.2)
                btn.click(delay=100)
                print("✅ 已点击 '登录'！", flush=True)
            else:
                print("[DEBUG] 未找到 '登录' 按钮", flush=True)
                return False
    except Exception as e:
        print(f"[DEBUG] 点击登录失败：{e}", flush=True)
        return False

    time.sleep(0.8)

    # 点击登录后会跳转到 oauth2/device 页面，需要额外等待页面完全加载
    print("[DEBUG] 等待 OAuth 授权页加载...", flush=True)
    time.sleep(0.8)
    
    # 检查授权确认页：登录后可能需要依次点击「继续」和「允许」
    # x.ai 的流程不固定，可能是：直接允许 / 继续→允许 / 继续→继续→允许
    # 用循环逐步处理，每轮找一个可点的授权按钮，直到完成或超时
    _check_cancel(cancel_callback)
    _handle_authorize_buttons(page, cancel_callback=cancel_callback, timeout=timeout)

    print("✅ OAuth 授权登录流程执行完毕", flush=True)
    
    # 等待一小段时间让授权生效
    time.sleep(0.5)
    
    return True


def _handle_authorize_buttons(page, cancel_callback=None, timeout=60):
    """循环处理 OAuth 授权页的「继续」/「允许」按钮。

    x.ai 授权流程步骤数不固定，登录成功后通常还需要：
      「继续」→「允许」
    也可能是：直接「允许」 / 「继续」→「继续」→「允许」
    
    策略：每轮扫描页面上可点的授权按钮并点击（优先允许 > 继续）。
    第一轮会额外等待页面加载，找到按钮立即点击并进入下一轮重新扫描。
    只有完全扫不到任何按钮时，才用 URL 判断是否已跳转完成。
    """
    deadline = time.time() + timeout
    clicked_allow = False
    empty_rounds = 0
    first_round = True  # 标记是否第一轮

    while time.time() < deadline and not clicked_allow:
        _check_cancel(cancel_callback)
        acted = False

        # 第一轮额外等待，确保登录后的新页面完全加载
        if first_round:
            first_round = False
            print("[DEBUG] [第一轮] 额外等待 5 秒让页面加载", flush=True)
            time.sleep(5.0)

        # 优先找「允许」（授权流程最后一步）
        try:
            allow_btn = page.locator('button[type="submit"]').filter(has_text="允许").first
            if allow_btn.count() > 0 and allow_btn.is_visible():
                print("🅱️ 检测到 '允许' 按钮，点击...", flush=True)
                time.sleep(1.0)
                allow_btn.click(delay=100)
                print("✅ 已点击 '允许'！授权完成", flush=True)
                clicked_allow = True
                time.sleep(0.5)
                break
        except Exception as e:
            print(f"[DEBUG] 扫描 '允许' 按钮失败：{e}", flush=True)
            pass

        # 其次找「继续」（授权流程中间步骤）
        try:
            continue_btn = page.locator('button[type="submit"]').filter(has_text="继续").first
            if continue_btn.count() > 0 and continue_btn.is_visible():
                print("👆 检测到 '继续' 按钮，点击...", flush=True)
                time.sleep(1.0)
                continue_btn.click(delay=100)
                print("✅ 已点击 '继续'", flush=True)
                acted = True
                time.sleep(2.5)  # 等待跳转到下一页
                empty_rounds = 0
                continue  # 立即进入下一轮，重新扫描按钮
        except Exception as e:
            print(f"[DEBUG] 扫描 '继续' 按钮失败：{e}", flush=True)
            pass

        # 本轮没找到任何授权按钮
        if not acted:
            empty_rounds += 1
            # 放宽重试次数：最多 10 轮（约 15 秒），适应网速慢的情况
            if empty_rounds >= 3:
                if _check_authorization_complete(page):
                    print("✅ 未见授权按钮且页面已跳转，视为授权完成", flush=True)
                    break
                if empty_rounds >= 10:
                    print("[DEBUG] 连续多轮未找到授权按钮，停止等待", flush=True)
                    break
            time.sleep(1.5)

    if not clicked_allow:
        print("[DEBUG] 未点击到 '允许' 按钮，token 轮询可能仍会成功（若已授权）", flush=True)



def _check_authorization_complete(page):
    """检测 OAuth 授权是否真正完成。

    注意：整个授权流程都在 accounts.x.ai 域名下进行（继续/登录/允许页都是），
    所以不能笼统地用 "x.ai in url" 判断，否则会把中间页误判为完成。
    真正完成的标志：跳转到 grok.com 主站，或明确的 device success 成功页。
    """
    try:
        url = (page.url or "").lower()

        # 中间页（授权流程中的各步骤），明确视为"未完成"
        intermediate_markers = ["/oauth2/authorize", "/login", "/sign-in", "/oauth2/device"]
        if any(m in url for m in intermediate_markers):
            # 但 device/success 或带 success 的算完成
            if "success" in url:
                return True
            return False

        # 真正完成：跳转到 grok 主站
        if "grok.com" in url:
            return True

        # 明确的成功提示文本
        for text in ["授权成功", "authorized", "You may now close"]:
            try:
                if page.locator(f"text={text}").count() > 0:
                    return True
            except Exception:
                pass

        return False
    except Exception:
        return False


# ============================================================================
# 完整注册流程
# ===========================================================================
class CancelledError(Exception):
    """用户请求停止时抛出，用于中断注册流程。"""
    pass


def _check_cancel(cancel_callback):
    """检查是否请求停止，是则抛 CancelledError。"""
    if cancel_callback and cancel_callback():
        raise CancelledError()


def _cancellable_sleep(seconds, cancel_callback):
    """可被取消打断的 sleep：按 0.2s 分片检查停止标志。"""
    deadline = time.time() + max(seconds, 0)
    while time.time() < deadline:
        _check_cancel(cancel_callback)
        time.sleep(min(0.2, max(deadline - time.time(), 0)))


def run_live(page, state, proxy="", cancel_callback=None, save_to_file=True,
             mail_mode="moemail", graph_account=None):
    """完整注册流程：创建/使用邮箱 → 填邮箱 → 验证码 → 资料 → Turnstile → 完成注册 → OAuth → token。

    save_to_file: True 时在本函数内直接把账号追加写入文件（CLI/单进程用）；
                  False 时不写文件，只把账号信息放进返回值，由调用方统一写入
                  （多进程模式下由主进程单点写入，避免文件竞争）。
    mail_mode:    "moemail"（自动创建临时邮箱）/ "msgraph"（正常微软邮箱）/
                  "submailbox"（子邮箱，共享收件系统，按收件地址过滤）。
    graph_account: mail_mode 为 "msgraph"/"submailbox" 时必填，
                   {"email","password","refresh_token","client_id"}。
                   注意：这里的 password 是邮箱密码，仅透传记录；Grok 注册会另生成新密码。
    """
    SIGNUP_URL = "https://accounts.x.ai/sign-up?redirect=grok-com"

    # 微软邮箱两种模式：msgraph（正常）/ submailbox（子邮箱）
    is_graph = mail_mode in ("msgraph", "submailbox")
    is_submailbox = mail_mode == "submailbox"

    # ---- 步骤 0：准备邮箱 ----
    _check_cancel(cancel_callback)
    email_id = None  # 仅 MoEmail 模式使用
    if is_graph:
        if not graph_account or not graph_account.get("email"):
            return {"ok": False, "error": "微软邮箱模式缺少邮箱账号信息"}
        email = graph_account["email"]
        if is_submailbox:
            print(f"\n📧 步骤 0：使用子邮箱 {email}（MS Graph 取件，按收件地址过滤）", flush=True)
        else:
            print(f"\n📧 步骤 0：使用微软邮箱 {email}（MS Graph 取件）", flush=True)
    else:
        print("\n📧 步骤 0：创建 MoEmail 邮箱...", flush=True)
        try:
            email, email_id = create_email()
        except Exception as e:
            print(f"❌ 创建邮箱失败：{e}", flush=True)
            import traceback; traceback.print_exc()
            return {"ok": False, "error": f"创建邮箱失败: {e}"}

    given_name, family_name, password = build_profile()
    print(f"[*] 本次资料：{given_name} {family_name} / 密码 {password}", flush=True)

    # ---- 步骤 1：打开注册页 ----
    print(f"\n🚀 步骤 1：打开注册页 {SIGNUP_URL} ...", flush=True)
    page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=45_000)
    print(f"✅ 当前 URL: {page.url}", flush=True)
    time.sleep(0.8)

    # 处理 OneTrust Cookie 同意弹窗（一开始就可能弹出，会遮挡注册按钮）
    _accept_all_cookies(page)

    # ---- 步骤 2：点击「使用邮箱注册」 ----
    _check_cancel(cancel_callback)
    try:
        btn = page.locator('button').filter(has_text="使用邮箱注册").first
        if btn.count() > 0:
            print("👆 步骤 2：点击 '使用邮箱注册'...", flush=True)
            time.sleep(1.5)
            btn.click(delay=100)
            time.sleep(2.5)
            print("✅ 邮箱注册按钮已点击", flush=True)
        else:
            print("[DEBUG] 未找到 '使用邮箱注册' 按钮", flush=True)
    except Exception as e:
        print(f"[DEBUG] 点击邮箱注册按钮失败：{e}", flush=True)

    time.sleep(0.5)

    # ---- 步骤 3：填写邮箱 ----
    _check_cancel(cancel_callback)
    email_input = None
    for sel in ['input[data-testid="email"]', 'input[name="email"]']:
        try:
            if page.locator(sel).count() > 0:
                email_input = sel
                break
        except Exception:
            pass
    if not email_input:
        print("⚠️ 未找到邮箱输入框", flush=True)
        return {"ok": False, "email": email, "error": "未找到邮箱输入框"}
    print(f"✅ 步骤 3：填写邮箱到 {email_input}", flush=True)
    human_type(page, email_input, email, state, "邮箱输入框")

    # ---- 步骤 4：点击「注册」提交（带重试）----
    # 有时点击会落空（网络抖动/点击未生效），此时"注册"按钮仍停留在原地。
    # 策略：点击后检测提交是否真的生效——若"注册"按钮消失或验证码输入框出现即成功；
    # 否则最多重试 10 轮，每轮间隔 5s 重新点击。
    _REG_BTN = 'button[type="submit"]'
    _CODE_SELS = ['input[name="code"]', 'input[autocomplete="one-time-code"]', 'input[data-input-otp="true"]']

    def _register_submitted():
        """判断邮箱是否已成功提交：注册按钮消失 或 验证码输入框出现。"""
        try:
            for sel in _CODE_SELS:
                if page.locator(sel).count() > 0:
                    return True
        except Exception:
            pass
        try:
            btn = page.locator(_REG_BTN).filter(has_text="注册").first
            # 按钮不存在或不可见都视为已离开当前步骤
            if btn.count() == 0 or not btn.is_visible():
                return True
        except Exception:
            # 定位异常时保守认为还没提交
            return False
        return False

    submitted = False
    for attempt in range(1, 11):  # 最多 10 轮
        _check_cancel(cancel_callback)
        if _register_submitted():
            submitted = True
            break
        try:
            btn = page.locator(_REG_BTN).filter(has_text="注册").first
            if btn.count() > 0:
                if attempt == 1:
                    print("👆 步骤 4：点击 '注册' 提交...", flush=True)
                else:
                    print(f"🔁 步骤 4：'注册' 按钮仍在，第 {attempt}/10 轮重新点击...", flush=True)
                time.sleep(1.0)
                btn.click(delay=100)
                print("✅ 已提交邮箱", flush=True)
            else:
                # 按钮不在但也没检测到验证码框，稍等下一轮再判断
                print(f"[DEBUG] 第 {attempt}/10 轮未找到 '注册' 按钮，等待页面状态...", flush=True)
        except Exception as e:
            print(f"[DEBUG] 第 {attempt}/10 轮点击注册按钮失败：{e}", flush=True)

        # 点击后等待页面响应，再进入下一轮检测
        deadline_click = time.time() + 5
        while time.time() < deadline_click:
            _check_cancel(cancel_callback)
            if _register_submitted():
                submitted = True
                break
            time.sleep(0.5)
        if submitted:
            break

    if submitted:
        print("✅ 邮箱提交已生效（注册按钮消失/验证码框已出现）", flush=True)
    else:
        print("⚠️ 多轮点击后仍未确认邮箱提交生效，继续尝试后续步骤", flush=True)

    # ---- 步骤 5：获取并填写验证码 ----
    _check_cancel(cancel_callback)
    print("\n🔑 步骤 5：等待并获取验证码...", flush=True)
    try:
        if is_graph:
            raw_code = fetch_verification_code_graph(
                graph_account, timeout=180, cancel_callback=cancel_callback,
                submailbox=is_submailbox,
            )
        else:
            raw_code = fetch_verification_code(email, email_id, timeout=180, cancel_callback=cancel_callback)
    except Exception as e:
        if isinstance(e, CancelledError):
            raise
        # MailError("用户取消轮询") 也视为取消
        if "取消" in str(e):
            raise CancelledError()
        print(f"❌ 获取验证码失败：{e}", flush=True)
        return {"ok": False, "email": email, "error": f"获取验证码失败: {e}"}
    clean_code = str(raw_code).replace("-", "").strip()
    print(f"✅ 验证码：{raw_code} -> 去连字符填入 '{clean_code}'", flush=True)

    # 等待验证码输入框
    code_input = None
    deadline = time.time() + 20
    while time.time() < deadline:
        _check_cancel(cancel_callback)
        for sel in ['input[name="code"]', 'input[autocomplete="one-time-code"]', 'input[data-input-otp="true"]']:
            try:
                if page.locator(sel).count() > 0:
                    code_input = sel
                    break
            except Exception:
                pass
        if code_input:
            break
        time.sleep(1.0)
    if not code_input:
        print("⚠️ 未找到验证码输入框", flush=True)
        return {"ok": False, "email": email, "error": "未找到验证码输入框"}
    print(f"✅ 找到验证码输入框：{code_input}", flush=True)
    human_type_otp(page, code_input, clean_code, state, "验证码")
    time.sleep(0.5)

    # ---- 步骤 6：填写资料 ----
    _check_cancel(cancel_callback)
    print("\n📝 步骤 6：填写资料...", flush=True)
    deadline = time.time() + 20
    profile_ready = False
    while time.time() < deadline:
        _check_cancel(cancel_callback)
        try:
            if page.locator('input[data-testid="givenName"]').count() > 0:
                profile_ready = True
                break
        except Exception:
            pass
        time.sleep(1.0)
    if not profile_ready:
        print("⚠️ 未出现资料表单", flush=True)
        return {"ok": False, "email": email, "error": "未出现资料表单"}

    human_type(page, 'input[data-testid="givenName"]', given_name, state, "名")
    time.sleep(random.uniform(0.3, 0.7))
    human_type(page, 'input[data-testid="familyName"]', family_name, state, "姓")
    time.sleep(random.uniform(0.3, 0.7))
    human_type(page, 'input[data-testid="password"]', password, state, "密码")
    time.sleep(1.0)

    # ---- 步骤 7：等待 Turnstile ----
    _check_cancel(cancel_callback)
    print("\n🛡️ 步骤 7：等待 Turnstile 验证...", flush=True)
    wait_for_turnstile(page, timeout=90, cancel_callback=cancel_callback)

    # ---- 步骤 8：点击「完成注册」 ----
    _check_cancel(cancel_callback)
    print("\n🎯 步骤 8：点击 '完成注册'...", flush=True)
    try:
        btn = page.locator('button[type="submit"]').filter(has_text="完成注册").first
        if btn.count() > 0:
            time.sleep(1.5)
            btn.click(delay=100)
            print("✅ 已点击 '完成注册'！", flush=True)
        else:
            print("[DEBUG] 未找到 '完成注册' 按钮", flush=True)
    except Exception as e:
        print(f"[DEBUG] 点击完成注册失败：{e}", flush=True)

    print(f"\n📋 账号信息：{email} / {password}", flush=True)
    time.sleep(5.0)

    # ================= OAuth 设备授权登录 =================
    _check_cancel(cancel_callback)
    print("\n" + "=" * 60, flush=True)
    print("开始 OAuth 设备授权登录", flush=True)
    print("=" * 60, flush=True)
    
    # 导入本地 OAuth
    from .oauth.device import request_device_code, poll_device_token
    
    # 请求设备码
    print("[*] 请求 OAuth 设备码...", flush=True)
    try:
        session = request_device_code(timeout=20.0, proxy=proxy or None, cancel=cancel_callback)
    except Exception as e:
        print(f"❌ 请求设备码失败：{e}", flush=True)
        return {"ok": False, "email": email, "error": f"请求设备码失败：{e}"}
    print(f"✅ 设备码已生成，user_code: {session.user_code}", flush=True)

    # 打开授权链接
    # 注意：注册成功后 x.ai 会让原页面自动跳转到 /account。若此时直接 goto 授权链接，
    # 会与这个自动跳转撞车（Navigation interrupted）。Camoufox 是 persistent context
    # 模式，不能开新标签页规避。因此策略为：
    #   1) 先等原页的 /account 自动跳转稳定下来
    #   2) 再 goto 授权链接，并加重试兜底（万一仍撞车，等一会重试，此时自动跳转已结束）
    _check_cancel(cancel_callback)

    # 步骤 1：等待注册后的自动跳转稳定
    print(f"\n⏳ 等待注册后页面跳转稳定...", flush=True)
    try:
        # 尽量等到跳去 /account（或任意稳定态）；等不到也不报错，继续往下走
        page.wait_for_url("**/account**", timeout=8000)
        print(f"✅ 已跳转到账户页：{page.url}", flush=True)
    except Exception:
        print(f"[DEBUG] 未检测到 /account 跳转（当前 {page.url}），继续", flush=True)
    time.sleep(2.0)  # 额外缓冲，确保没有正在进行的导航

    # 步骤 2：goto 授权链接 + 重试兜底
    print(f"\n🚀 打开授权链接...", flush=True)
    goto_ok = False
    for attempt in range(4):  # 最多 4 次
        _check_cancel(cancel_callback)
        try:
            page.goto(session.verification_uri_complete, wait_until="domcontentloaded", timeout=45_000)
            goto_ok = True
            break
        except Exception as e:
            msg = str(e)
            if "interrupted" in msg.lower() or "another navigation" in msg.lower():
                print(f"[DEBUG] 第 {attempt + 1}/4 次 goto 被自动跳转打断，2 秒后重试...", flush=True)
                time.sleep(2.0)
                continue
            # 其它错误（如代理断开）也重试一次
            print(f"[DEBUG] 第 {attempt + 1}/4 次 goto 失败：{msg[:80]}，2 秒后重试...", flush=True)
            time.sleep(2.0)
    if not goto_ok:
        print("⚠️ 多次尝试打开授权链接失败", flush=True)
        return {"ok": False, "email": email, "error": "打开授权链接失败"}
    time.sleep(0.8)

    # 执行授权登录
    login_ok = oauth_authorize_login(page, state, email, password, timeout=90, cancel_callback=cancel_callback)
    if not login_ok:
        print("⚠️ OAuth 授权登录未成功完成", flush=True)

    # 轮询获取 token
    _check_cancel(cancel_callback)
    print("\n🔄 开始轮询获取 token...", flush=True)
    try:
        token = poll_device_token(
            device_code=session.device_code,
            token_endpoint=session.token_endpoint,
            interval=session.interval,
            expires_in=session.expires_in,
            timeout=30.0,
            proxy=proxy or None,
            cancel=cancel_callback,
            log=lambda m: print("   " + m, flush=True),
        )
        print("\n🎉 Token 获取成功！", flush=True)
        print(f"   access_token:  {token.access_token[:40]}...", flush=True)
        print(f"   refresh_token: {token.refresh_token[:40]}...", flush=True)
        
        # 保存账号
        if save_to_file:
            from .account_store import append_account
            import os, time as _t
            ts = _t.strftime("%Y%m%d")
            out_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"accounts_{ts}.txt")
            append_account(out_file, email, password, token.refresh_token)
            print(f"\n💾 账号已追加保存到：{out_file}", flush=True)
            print(f"   内容：{email}----{password}----{token.refresh_token[:20]}...", flush=True)
        else:
            print(f"\n💾 账号信息将由主进程统一保存", flush=True)
        
        return {
            "ok": True,
            "email": email,
            "password": password,
            "rt": token.refresh_token,
            "access_token": token.access_token,
            "id_token": getattr(token, "id_token", None),
        }
    except Exception as e:
        print(f"❌ 轮询 token 失败：{e}", flush=True)
        import traceback; traceback.print_exc()
        return {"ok": False, "email": email, "error": f"轮询 token 失败：{e}"}


# ============================================================================
# 注册入口
# ===========================================================================
class _LogRedirect:
    """把 print 的输出按行转发给 log_callback，同时保留原 stdout。"""
    def __init__(self, callback, original):
        self._callback = callback
        self._original = original
        self._buffer = ""

    def write(self, text):
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                try:
                    self._callback(line)
                except Exception:
                    pass

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass


def run_registration_flow(
    log_callback=None,
    headless=False,
    count=1,
    cancel_callback=None,
    observer=None,
):
    """执行一次或多次完整的 Camoufox 注册 + OAuth 授权流程。
    
    Args:
        log_callback: 可选，接收每行日志的回调
        headless: 是否无头模式
        count: 循环次数
        cancel_callback: 可选，返回 True 表示停止
        observer: 可选，每次完成后调用 observer(result)
    
    Returns:
        (success_count, fail_count, total)
    """
    import contextlib

    # 读取代理配置
    pw_proxy, raw_proxy = get_proxy_config()
    if pw_proxy:
        print(f"[*] 使用代理：{pw_proxy['server']}"
              + ("（含账号密码认证）" if pw_proxy.get("username") else ""), flush=True)
    else:
        print("[*] 未配置代理，浏览器将直连", flush=True)

    def _flow_one():
        state = {"pos": None}
        try:
            camoufox_kwargs = dict(
                headless=headless,
                humanize=True,
                os="windows",
                locale="zh-CN",
                firefox_user_prefs={
                    "intl.accept_languages": "zh-CN,zh,en-US,en",
                    "intl.locale.requested": "zh-CN",
                },
                window=[1400, 900],
            )
            if pw_proxy:
                camoufox_kwargs["proxy"] = pw_proxy
                camoufox_kwargs["geoip"] = True
            with Camoufox(**camoufox_kwargs) as browser:
                print("✅ Camoufox 启动成功！")
                page = browser.new_page()
                return run_live(page, state, proxy=raw_proxy, cancel_callback=cancel_callback)
        except CancelledError:
            print("\n[!] 已停止当前注册（浏览器已关闭）", flush=True)
            return {"ok": False, "error": "用户停止", "cancelled": True}
        except Exception as e:
            # OAuth 层的取消也识别为取消
            if "cancelled" in str(e).lower() or "取消" in str(e):
                print("\n[!] 已停止当前注册（浏览器已关闭）", flush=True)
                return {"ok": False, "error": "用户停止", "cancelled": True}
            print(f"❌ 运行失败：{e}")
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    print("=" * 60)
    print("Camoufox + 拟人化鼠标/键盘 注册流程")
    print("=" * 60)

    success_count = fail_count = 0
    for i in range(1, count + 1):
        if cancel_callback and cancel_callback():
            print("\n[!] 用户请求停止", flush=True)
            break
        print(f"\n{'='*60}\n第 {i}/{count} 次注册\n" + "="*60)

        if log_callback is not None:
            redirect = _LogRedirect(log_callback, sys.__stdout__)
            with contextlib.redirect_stdout(redirect), contextlib.redirect_stderr(redirect):
                result = _flow_one()
        else:
            result = _flow_one()

        # 用户中途停止：不计入成功/失败，直接结束
        if result.get("cancelled"):
            print("\n[!] 注册已被用户停止", flush=True)
            break

        if observer and callable(observer):
            try:
                observer(result)
            except Exception as e:
                print(f"[!] observer 异常：{e}", flush=True)

        if result.get("ok"):
            success_count += 1
        else:
            fail_count += 1

    total = success_count + fail_count
    print(f"\n{'='*60}\n注册完成：成功 {success_count} | 失败 {fail_count} | 总数 {total}\n{'='*60}")
    return success_count, fail_count, total
