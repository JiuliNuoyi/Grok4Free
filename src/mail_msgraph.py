"""微软邮箱 MS Graph / Outlook 取件：用 refresh_token + client_id 换 access_token，
轮询收件箱提取验证码。

从原项目 mail_service.py（msgraph_* 系列）抽离并重写成纯函数模块。
关键改进：不依赖全局 config 或注入，所有凭据显式传入/传出。

账号格式（本项目约定，一行一个）：
    邮箱----密码----refresh_token----client_id

说明：
- refresh_token + client_id 用于换取 access_token（真正取件靠它）。
- password 是微软邮箱账号自身的密码，取件用不到，仅作记录透传。
- 换 token 时会依次尝试多个 tenant + 多个 scope，容错性强（沿用原项目实战逻辑）。
"""

import re
import time
from typing import Optional, List, Dict, Callable, Any

from .http_client import http_post, http_get
# 复用 MoEmail 模块里已经写好的正文归一化 / 列表适配 / 验证码提取，避免重复实现
from .mail_moemail import (
    MailError,
    _normalize_mail_body,
    _pick_list_payload,
    extract_verification_code,
)


# ============================================================================
# 账号行解析
# ============================================================================
def parse_account_line(raw: str) -> Dict[str, str]:
    """解析一行微软邮箱账号：邮箱----密码----refresh_token----client_id。

    Returns:
        {"email", "password", "refresh_token", "client_id"}

    Raises:
        MailError: 字段不足
    """
    line = str(raw or "").strip()
    if not line:
        raise MailError("微软邮箱账号为空")
    parts = line.split("----")
    if len(parts) < 4:
        raise MailError(
            "微软邮箱账号格式错误，需要：邮箱----密码----refresh_token----client_id"
        )
    email = parts[0].strip()
    password = parts[1].strip()
    refresh_token = parts[2].strip()
    # client_id 是最后一段；万一 refresh_token 里含有分隔符，把中间多出来的并回 token
    client_id = parts[-1].strip()
    if len(parts) > 4:
        refresh_token = "----".join(p.strip() for p in parts[2:-1])
    if not email:
        raise MailError("微软邮箱账号缺少邮箱")
    if not refresh_token:
        raise MailError("微软邮箱账号缺少 refresh_token")
    if not client_id:
        raise MailError("微软邮箱账号缺少 client_id")
    return {
        "email": email,
        "password": password,
        "refresh_token": refresh_token,
        "client_id": client_id,
    }


def parse_account_lines(text: str) -> List[Dict[str, str]]:
    """解析多行账号文本，返回解析成功的账号列表（忽略空行）。

    每行独立解析，某一行格式错误会抛出 MailError（带行号），交给上层决定如何处理。
    这里选择跳过坏行并记录，而不是整体失败——由调用方决定。此函数只做严格解析。
    """
    result = []
    for idx, line in enumerate(str(text or "").replace("\r", "\n").split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            result.append(parse_account_line(line))
        except MailError as e:
            raise MailError(f"第 {idx} 行：{e}")
    return result


# ============================================================================
# 换取 access_token
# ============================================================================
def _tenant_candidates(tenant: str) -> List[str]:
    tenants = []
    for item in (tenant, "consumers", "common", "organizations"):
        item = str(item or "").strip()
        if item and item not in tenants:
            tenants.append(item)
    return tenants


_SCOPE_CANDIDATES = [
    "https://graph.microsoft.com/.default",
    "",  # 空 scope 保留 refresh_token 原始授权范围
    "https://graph.microsoft.com/Mail.Read offline_access",
    "https://graph.microsoft.com/Mail.ReadWrite offline_access",
    "https://outlook.office.com/Mail.Read offline_access",
    "https://outlook.office.com/Mail.ReadWrite offline_access",
]

# 协议对应的 scope（供子邮箱等场景固定指定）
SCOPE_GRAPH = "https://graph.microsoft.com/.default"       # GRAPH 协议
SCOPE_IMAP_POP3 = "https://outlook.office.com/.default"    # IMAP/POP3 协议


def refresh_access_token(
    client_id: str,
    refresh_token: str,
    tenant: str = "consumers",
    log_callback: Optional[Callable[[str], None]] = None,
    force_scope: Optional[str] = None,
) -> Dict[str, str]:
    """用 refresh_token + client_id 换取 access_token。

    依次尝试多个 tenant + 多个 scope，任一成功即返回。

    Args:
        force_scope: 指定后只用该 scope（不再遍历候选）。子邮箱走 GRAPH 时
                     传 "https://graph.microsoft.com/.default"。

    Returns:
        {
          "access_token": str,
          "refresh_token": str,   # 可能被刷新（如返回新的），否则同传入
          "tenant": str,          # 实际成功的 tenant
          "api_mode": "graph"|"outlook"|"auto",
        }

    Raises:
        MailError: 全部尝试失败
    """
    client_id = str(client_id or "").strip()
    refresh_token = str(refresh_token or "").strip()
    if not client_id:
        raise MailError("MS Graph client_id 未配置")
    if not refresh_token:
        raise MailError("MS Graph refresh_token 未配置")

    scope_list = [force_scope] if force_scope else _SCOPE_CANDIDATES

    errors: List[str] = []
    for use_tenant in _tenant_candidates(tenant):
        token_url = f"https://login.microsoftonline.com/{use_tenant}/oauth2/v2.0/token"
        for scope in scope_list:
            data = {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
            if scope:
                data["scope"] = scope
            try:
                resp = http_post(
                    token_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data=data,
                    timeout=30,
                )
            except Exception as exc:
                errors.append(f"{use_tenant}/scope={scope or '(none)'}: network {exc}")
                continue

            body_preview = str(getattr(resp, "text", "") or "")[:220]
            if resp.status_code >= 400:
                errors.append(
                    f"{use_tenant}/scope={scope or '(none)'}: HTTP {resp.status_code} {body_preview}"
                )
                continue
            try:
                payload = resp.json()
            except Exception:
                errors.append(f"{use_tenant}/scope={scope or '(none)'}: non-json {body_preview}")
                continue

            access = str((payload or {}).get("access_token") or "").strip()
            if not access:
                err = (payload or {}).get("error_description") or (payload or {}).get("error") or payload
                errors.append(f"{use_tenant}/scope={scope or '(none)'}: {err}")
                continue

            new_refresh = str((payload or {}).get("refresh_token") or "").strip() or refresh_token
            scope_out = str((payload or {}).get("scope") or scope or "").lower()
            if "graph.microsoft.com" in scope_out:
                api_mode = "graph"
            elif "outlook.office" in scope_out:
                api_mode = "outlook"
            else:
                api_mode = "auto"

            if log_callback:
                log_callback(f"[*] MS Graph 换取 access_token 成功（tenant={use_tenant}, mode={api_mode}）")
            return {
                "access_token": access,
                "refresh_token": new_refresh,
                "tenant": use_tenant,
                "api_mode": api_mode,
            }

    detail = " | ".join(errors[:6]) if errors else "unknown"
    raise MailError(f"MS Graph 刷新 token 失败：{detail}")


# ============================================================================
# 取邮件
# ============================================================================
def _auth_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {str(access_token or '').strip()}",
        "Accept": "application/json",
    }


def _message_list_urls(api_mode: str) -> List[str]:
    graph_urls = [
        (
            "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
            "?$top=20&$orderby=receivedDateTime desc"
            "&$select=id,subject,bodyPreview,body,receivedDateTime,from,toRecipients"
        ),
        (
            "https://graph.microsoft.com/v1.0/me/messages"
            "?$top=20&$orderby=receivedDateTime desc"
            "&$select=id,subject,bodyPreview,body,receivedDateTime,from,toRecipients"
        ),
    ]
    outlook_urls = [
        "https://outlook.office.com/api/v2.0/me/mailfolders/inbox/messages?$top=20&$orderby=ReceivedDateTime desc",
        "https://outlook.office.com/api/v2.0/me/messages?$top=20&$orderby=ReceivedDateTime desc",
    ]
    if api_mode == "outlook":
        return outlook_urls + graph_urls
    return graph_urls + outlook_urls


def _message_detail_urls(api_mode: str, message_id: str) -> List[str]:
    msg_id = str(message_id or "").strip()
    graph_urls = [
        f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
        "?$select=id,subject,bodyPreview,body,receivedDateTime,from,toRecipients",
    ]
    outlook_urls = [
        f"https://outlook.office.com/api/v2.0/me/messages/{msg_id}",
    ]
    if api_mode == "outlook":
        return outlook_urls + graph_urls
    return graph_urls + outlook_urls


def _extract_recipients(msg: dict) -> List[str]:
    """从邮件对象提取收件人地址列表（小写）。兼容 Graph / Outlook 字段命名。"""
    if not isinstance(msg, dict):
        return []
    recips = msg.get("toRecipients") or msg.get("ToRecipients") or []
    result = []
    for r in recips:
        if not isinstance(r, dict):
            continue
        addr_obj = r.get("emailAddress") or r.get("EmailAddress") or {}
        if isinstance(addr_obj, dict):
            addr = addr_obj.get("address") or addr_obj.get("Address") or ""
        else:
            addr = str(addr_obj or "")
        addr = str(addr).strip().lower()
        if addr:
            result.append(addr)
    return result


def _normalize_message(msg: dict) -> dict:
    """把 Graph/Outlook 的邮件对象归一化为 {subject, text, html, bodyPreview}。"""
    if not isinstance(msg, dict):
        return {"subject": "", "text": "", "html": "", "bodyPreview": ""}
    subject = str(msg.get("subject") or msg.get("Subject") or "")
    preview = str(
        msg.get("bodyPreview") or msg.get("body_preview") or msg.get("BodyPreview") or ""
    )
    body = msg.get("body") if msg.get("body") is not None else msg.get("Body")
    text = ""
    html = ""
    if isinstance(body, dict):
        content = str(body.get("content") or body.get("Content") or "")
        content_type = str(
            body.get("contentType") or body.get("content_type") or body.get("ContentType") or ""
        ).lower()
        if content_type == "text":
            text = content
        else:
            html = content
    elif isinstance(body, str):
        text = body
    if preview and not text:
        text = preview
    return {"subject": subject, "text": text, "html": html, "bodyPreview": preview}


def get_messages(access_token: str, api_mode: str = "auto") -> tuple[list, str]:
    """拉取邮件列表。返回 (messages, 实际生效的 api_mode)。

    Raises:
        PermissionError: access_token 失效（401）
        MailError: 其它失败
    """
    token = str(access_token or "").strip()
    if not token:
        raise MailError("MS Graph access_token 为空")
    headers = _auth_headers(token)
    errors = []
    saw_401 = False
    for url in _message_list_urls(api_mode):
        try:
            resp = http_get(url, headers=headers, timeout=30)
        except Exception as exc:
            errors.append(f"{url}: network {exc}")
            continue
        if resp.status_code == 401:
            saw_401 = True
            errors.append(f"{url}: HTTP 401")
            continue
        if resp.status_code >= 400:
            errors.append(f"{url}: HTTP {resp.status_code} {str(resp.text or '')[:120]}")
            continue
        try:
            data = resp.json()
        except Exception:
            errors.append(f"{url}: non-json")
            continue
        mode_out = "graph" if "graph.microsoft.com" in url else (
            "outlook" if "outlook.office.com" in url else api_mode
        )
        if isinstance(data, dict) and isinstance(data.get("value"), list):
            return data["value"], mode_out
        return _pick_list_payload(data), mode_out
    if saw_401:
        raise PermissionError("MS Graph access_token 失效")
    raise MailError("MS Graph 邮件列表失败：" + " | ".join(errors[:4]))


def get_message_detail(access_token: str, message_id: str, api_mode: str = "auto") -> dict:
    """拉取单封邮件详情。

    Raises:
        PermissionError: access_token 失效（401）
        MailError: 其它失败
    """
    token = str(access_token or "").strip()
    msg_id = str(message_id or "").strip()
    if not token or not msg_id:
        raise MailError("MS Graph access_token/message_id 为空")
    headers = _auth_headers(token)
    errors = []
    saw_401 = False
    for url in _message_detail_urls(api_mode, msg_id):
        try:
            resp = http_get(url, headers=headers, timeout=30)
        except Exception as exc:
            errors.append(f"{url}: network {exc}")
            continue
        if resp.status_code == 401:
            saw_401 = True
            errors.append(f"{url}: HTTP 401")
            continue
        if resp.status_code >= 400:
            errors.append(f"{url}: HTTP {resp.status_code} {str(resp.text or '')[:120]}")
            continue
        try:
            data = resp.json()
        except Exception:
            errors.append(f"{url}: non-json")
            continue
        return data if isinstance(data, dict) else {}
    if saw_401:
        raise PermissionError("MS Graph access_token 失效")
    raise MailError("MS Graph 邮件详情失败：" + " | ".join(errors[:3]))


# ============================================================================
# 轮询验证码
# ============================================================================
def poll_verification_code(
    client_id: str,
    refresh_token: str,
    tenant: str = "consumers",
    timeout: int = 180,
    poll_interval: int = 3,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
    resend_callback: Optional[Callable[[], None]] = None,
    target_address: Optional[str] = None,
    force_scope: Optional[str] = None,
) -> str:
    """轮询微软邮箱收件箱，提取验证码。

    Args:
        client_id / refresh_token / tenant: 换 token 用
        timeout: 超时秒数
        poll_interval: 轮询间隔秒
        log_callback / cancel_callback / resend_callback: 回调
        target_address: 子邮箱模式必填。多个子邮箱共用一个收件系统，
                        只提取「收件人（toRecipients）包含该地址」的邮件验证码，
                        避免串号。正常邮箱模式留空（不过滤）。
        force_scope: 指定后换 token 只用该 scope。子邮箱走 GRAPH 时传
                     "https://graph.microsoft.com/.default"。

    Returns:
        验证码字符串

    Raises:
        MailError: 超时或换 token 失败
    """
    def _log(m):
        if log_callback:
            log_callback(m)

    target = str(target_address or "").strip().lower()

    token_info = refresh_access_token(
        client_id, refresh_token, tenant, log_callback=_log, force_scope=force_scope
    )
    access_token = token_info["access_token"]
    api_mode = token_info["api_mode"]

    if target:
        _log(f"[*] 子邮箱模式：仅提取收件人为 {target} 的邮件")

    deadline = time.time() + timeout
    seen_attempts: Dict[str, int] = {}
    next_resend_at = time.time() + 35

    while time.time() < deadline:
        if cancel_callback and cancel_callback():
            raise MailError("用户取消轮询")

        if resend_callback and time.time() >= next_resend_at:
            try:
                resend_callback()
                _log("[*] 已触发重新发送验证码")
            except Exception as exc:
                _log(f"[Debug] 触发重发验证码失败：{exc}")
            next_resend_at = time.time() + 35

        try:
            messages, api_mode = get_messages(access_token, api_mode)
        except PermissionError:
            _log("[Debug] MS Graph token 失效，尝试刷新")
            token_info = refresh_access_token(
                client_id, refresh_token, tenant, log_callback=_log, force_scope=force_scope
            )
            access_token = token_info["access_token"]
            api_mode = token_info["api_mode"]
            time.sleep(min(poll_interval, max(deadline - time.time(), 0)))
            continue
        except Exception as exc:
            _log(f"[Debug] MS Graph 拉取邮件列表失败：{exc}")
            time.sleep(min(poll_interval, max(deadline - time.time(), 0)))
            continue

        _log(f"[Debug] MS Graph 本轮邮件数量：{len(messages)}")
        for msg in messages:
            msg_id = msg.get("id") or msg.get("Id")
            if not msg_id:
                continue
            attempt = int(seen_attempts.get(msg_id, 0))
            if attempt >= 5:
                continue
            seen_attempts[msg_id] = attempt + 1

            # 子邮箱模式：按收件地址过滤，只认发给本子邮箱的邮件
            if target:
                recipients = _extract_recipients(msg)
                if recipients and target not in recipients:
                    _log(f"[Debug] 跳过非本子邮箱邮件 id={msg_id} to={recipients}")
                    continue

            normalized = _normalize_message(msg)
            subject = normalized.get("subject") or ""
            combined = _normalize_mail_body(normalized)
            try:
                detail = get_message_detail(access_token, msg_id, api_mode)
                detail_norm = _normalize_message(detail)
                detail_body = _normalize_mail_body(detail_norm)
                if detail_body:
                    combined += "\n" + detail_body
                if not subject:
                    subject = detail_norm.get("subject") or ""
                # detail 里若能拿到收件人且列表项拿不到，二次确认过滤
                if target:
                    detail_recips = _extract_recipients(detail)
                    if detail_recips and target not in detail_recips:
                        _log(f"[Debug] detail 确认非本子邮箱邮件 id={msg_id} to={detail_recips}")
                        continue
            except PermissionError:
                token_info = refresh_access_token(
                    client_id, refresh_token, tenant, log_callback=_log, force_scope=force_scope
                )
                access_token = token_info["access_token"]
                api_mode = token_info["api_mode"]
                continue
            except Exception as exc:
                _log(f"[Debug] MS Graph detail 接口失败，改用列表内容解析：{exc}")

            _log(f"[Debug] MS Graph 收到邮件：{subject}")
            code = extract_verification_code(combined, subject)
            if code:
                _log(f"[*] MS Graph 从邮件中提取到验证码：{code}")
                return code
            _log(
                f"[Debug] MS Graph 邮件已解析但未提取到验证码 "
                f"id={msg_id} attempt={seen_attempts[msg_id]}"
            )

        remaining = max(deadline - time.time(), 0)
        if remaining > 0:
            time.sleep(min(poll_interval, remaining))

    raise MailError(f"MS Graph 在 {timeout}s 内未收到验证码邮件")
