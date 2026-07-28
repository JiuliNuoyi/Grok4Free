"""MoEmail 临时邮箱服务：创建邮箱、轮询收件、提取验证码。

从原项目 mail_service.py（1592 行）中完整抽离 MoEmail 相关逻辑，重写成纯函数模块。
关键改进：不依赖全局 config 或 bind_runtime() 注入，所有数据显式传入/传出。
只保留 MoEmail，删除 Cloudflare / msgraph / duckmail / cloudmail / yyds 等无关内容。
"""

import re
import time
from typing import Optional, List, Dict, Callable, Any

# 导入本地 HTTP 客户端
from .http_client import http_post, http_get


class MailError(Exception):
    """邮箱服务错误基类。"""
    pass


def _normalize_mail_body(*sources) -> str:
    """从邮件 payload 中提取文本内容（支持 text/html/list/dict 混合格式）。"""
    parts = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        # Text-like fields
        for key in ("text", "raw", "content", "intro", "body", "snippet"):
            value = source.get(key)
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                if isinstance(item, str) and item.strip():
                    parts.append(item)
        # HTML content
        html_value = source.get("html")
        if html_value:
            html_items = html_value if isinstance(html_value, (list, tuple)) else [html_value]
            for item in html_items:
                if isinstance(item, str) and item.strip():
                    # Strip HTML tags
                    clean = re.sub(r"<[^>]+>", " ", item)
                    parts.append(clean.strip())
    return "\n".join(parts)


def _pick_list_payload(data) -> list:
    """适配不同 API 的列表返回格式。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "hydra:member", "data", "messages"):
            nested = data.get(key)
            if isinstance(nested, list):
                return nested
    return []


def generate_username(length: int = 10) -> str:
    """生成随机用户名。"""
    import secrets
    import string
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def create_email(config: Dict[str, Any]) -> tuple[str, str]:
    """创建一个新的临时邮箱，返回 (email, email_id)。

    Args:
        config: 包含 moemail_api_base/api_key/domain/expiry_ms 的配置字典

    Returns:
        (email, email_id)

    Raises:
        MailError: 配置缺失或 API 调用失败
    """
    api_base = config.get("moemail_api_base", "").strip().rstrip("/")
    api_key = config.get("moemail_api_key", "").strip()
    domain = config.get("moemail_domain", "").strip().lstrip("@")
    expiry_ms = config.get("moemail_expiry_ms", 3600000)

    if not api_base:
        raise MailError("MoEmail API Base 未配置")
    if not api_key:
        raise MailError("MoEmail API Key 未配置")
    if not domain:
        raise MailError("MoEmail 收件域名未配置")

    payload = {
        "name": generate_username(10),
        "expiryTime": expiry_ms,
        "domain": domain,
    }
    
    headers = {"X-API-Key": api_key}
    if isinstance(payload, dict):
        headers["Content-Type"] = "application/json"

    resp = http_post(
        f"{api_base}/api/emails/generate",
        headers=headers,
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    
    try:
        data = resp.json()
    except Exception as e:
        raise MailError(f"MoEmail 创建邮箱返回非 JSON: {resp.text[:300]}")
    
    if not isinstance(data, dict):
        raise MailError(f"MoEmail 创建邮箱返回格式错误: {data}")

    email = str(data.get("email") or data.get("address") or "").strip()
    email_id = str(data.get("id") or "").strip()

    if not email or not email_id:
        raise MailError(f"MoEmail 创建邮箱缺少 email/id: {data}")

    return email, email_id


def fetch_messages(email_id: str, config: Dict[str, Any]) -> list:
    """获取邮箱的消息列表。

    Args:
        email_id: MoEmail 返回的 emailId
        config: 配置字典

    Returns:
        消息列表（dict 列表）
    """
    api_base = config.get("moemail_api_base", "").strip().rstrip("/")
    api_key = config.get("moemail_api_key", "").strip()

    if not api_base:
        raise MailError("MoEmail API Base 未配置")
    if not email_id:
        raise MailError("emailId 为空")

    resp = http_get(
        f"{api_base}/api/emails/{email_id}",
        headers={"X-API-Key": api_key},
        timeout=20,
    )
    resp.raise_for_status()

    try:
        data = resp.json()
    except Exception as e:
        raise MailError(f"MoEmail 拉取邮件失败：{e}")

    return _pick_list_payload(data)


def fetch_message_detail(email_id: str, message_id: str, config: Dict[str, Any]) -> dict:
    """获取单个邮件的详情。

    Args:
        email_id: 邮箱 ID
        message_id: 邮件 ID
        config: 配置字典

    Returns:
        邮件详情 dict
    """
    api_base = config.get("moemail_api_base", "").strip().rstrip("/")
    api_key = config.get("moemail_api_key", "").strip()

    if not api_base or not email_id or not message_id:
        raise MailError("参数错误：缺少 emailId/messageId")

    resp = http_get(
        f"{api_base}/api/emails/{email_id}/{message_id}",
        headers={"X-API-Key": api_key},
        timeout=20,
    )
    resp.raise_for_status()

    try:
        return resp.json()
    except Exception as e:
        raise MailError(f"MoEmail 获取邮件详情失败：{e}")


def extract_verification_code(text: str, subject: str = "") -> Optional[str]:
    """从邮件内容中提取验证码（支持多种格式）。

    Args:
        text: 邮件正文/HTML 清理后的文本
        subject: 邮件主题（优先匹配）

    Returns:
        验证码（如 XAI-ABC-DEF），失败返回 None
    """
    if subject:
        # xAI 验证码格式：XXX-XXX@xAI 或 XXX-XXX verification code
        patterns = [
            r"^([A-Z0-9]{3}-[A-Z0-9]{3})\s+xAI\b",
            r"\b(?:confirmation|verification)\s+code\s*:\s*([A-Z0-9]{3}-[A-Z0-9]{3})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1)

    # 通用验证码模式
    match = re.search(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", text, re.IGNORECASE)
    if match:
        return match.group(1)

    # 数字验证码
    patterns = [
        r"verification\s+code[:\s]+(\d{4,8})",
        r"your\s+code[:\s]+(\d{4,8})",
        r"confirm(?:ation)?\s+code[:\s]+(\d{4,8})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def poll_verification_code(
    email_id: str,
    config: Dict[str, Any],
    timeout: int = 180,
    poll_interval: int = 3,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
    resend_callback: Optional[Callable[[], None]] = None,
) -> str:
    """轮询邮箱，等待并提取验证邮件中的验证码。

    Args:
        email_id: MoEmail 返回的 emailId
        config: 配置字典
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）
        log_callback: 日志回调函数
        cancel_callback: 取消回调（返回 True 表示停止）
        resend_callback: 重新发送验证码回调（可选）

    Returns:
        验证码字符串

    Raises:
        MailError: 超时未收到邮件
    """
    deadline = time.time() + timeout
    seen_attempts: Dict[str, int] = {}
    next_resend_at = time.time() + 35

    while time.time() < deadline:
        if cancel_callback and cancel_callback():
            raise MailError("用户取消轮询")

        if resend_callback and time.time() >= next_resend_at:
            try:
                resend_callback()
                if log_callback:
                    log_callback("[*] 已触发重新发送验证码")
            except Exception as exc:
                if log_callback:
                    log_callback(f"[Debug] 触发重发验证码失败：{exc}")
            next_resend_at = time.time() + 35

        messages = fetch_messages(email_id, config)

        for msg in messages:
            msg_id = msg.get("id") or msg.get("messageId") or msg.get("message_id")
            if not msg_id:
                continue

            attempt = int(seen_attempts.get(msg_id, 0))
            if attempt >= 5:
                continue
            seen_attempts[msg_id] = attempt + 1

            subject = str(msg.get("subject", "") or "")
            combined = _normalize_mail_body(msg)

            # Try to get more detailed body
            try:
                detail = fetch_message_detail(email_id, msg_id, config)
                detail_body = _normalize_mail_body(detail)
                if detail_body:
                    combined += "\n" + detail_body
                if not subject:
                    subject = str(detail.get("subject", "") or "")
            except Exception as exc:
                if log_callback:
                    log_callback(f"[Debug] MoEmail detail 接口失败，改用列表内容解析：{exc}")

            if log_callback:
                log_callback(f"[Debug] MoEmail 收到邮件：{subject}")

            code = extract_verification_code(combined, subject)
            if code:
                if log_callback:
                    log_callback(f"[*] 从邮件中提取到验证码：{code}")
                return code

            if log_callback:
                log_callback(
                    f"[Debug] MoEmail 邮件已解析但未提取到验证码 "
                    f"id={msg_id} attempt={seen_attempts[msg_id]}"
                )

        remaining = max(deadline - time.time(), 0)
        if remaining > 0:
            sleep_seconds = min(poll_interval, remaining)
            time.sleep(sleep_seconds)

    raise MailError(f"在 {timeout}s 内未收到 MoEmail 验证邮件")
