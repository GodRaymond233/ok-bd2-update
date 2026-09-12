from __future__ import annotations

import getpass
import platform
import re
from pathlib import Path

# Scheme 后面若紧跟 ":" 或 "="，说明它是键名（如 "Token = abc"）而不是
# 认证头，交给 _SECRET_RE 处理，避免只吞掉键名留下真实值。
_AUTH_SCHEME_RE = re.compile(
    r"(?i)\b(?:Bearer|Basic|Token)\s+(?![=:])[A-Za-z0-9._~+/=-]+"
)
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
# 键词后允许 [A-Z0-9_-]{0,24} 后缀（secret_key / password_hash）；
# 值为 "Bearer/Basic/Token + 凭据" 形态时不在此匹配，留给 _AUTH_SCHEME_RE
# 连同后续凭据一起脱敏，否则 scheme 词被当作值吞掉后会泄漏真正的凭据。
_SECRET_RE = re.compile(
    r"(?i)(?P<quote>[\"']?)(?P<key>[A-Z0-9_-]{0,64}(?:authorization|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|"
    r"private[_-]?key|token|secret|password|passwd|cookie|session)"
    r"[A-Z0-9_-]{0,24})(?P=quote)"
    r"(?P<sep>\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|(?!(?:bearer|basic|token)\s)[^\s,;]+)"
)
# userinfo 形态的 URL（https://user:pass@host/...），只保留 scheme 与主机。
_URL_USERINFO_RE = re.compile(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@")
_URL_QUERY_RE = re.compile(r"(?i)(https?://[^\s?#]+)\?[^\s#]+")
_QUOTED_WINDOWS_PATH_RE = re.compile(
    r"(?i)(?P<quote>[\"'])(?P<path>(?:[A-Z]:[\\/]|\\\\).*?)(?P=quote)"
)
# 裸 Windows 路径允许"空格+段"续段（如 C:\Program Files\...）：续段要求
# 空格后到下一个空白之间出现路径分隔符，且不能是另一条盘符路径，避免把
# 路径后的普通句子一起打码。成对引号内的路径由 _QUOTED_WINDOWS_PATH_RE
# 先行完整处理。
_WINDOWS_PATH_RE = re.compile(
    r"(?i)(?<![A-Z0-9_])(?:[A-Z]:[\\/]|\\\\)"
    r"[^\s,;\"'<>|]+"
    r"(?:[ \t]+(?![A-Z]:[\\/])(?=[^\s,;\"'<>|]*[\\/])[^\s,;\"'<>|]+)*"
)
_PLACEHOLDER_PATH_RE = re.compile(r"<PATH>(?:[\\/][^\s,;\"'<>|]+)+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_PATH_PUNCTUATION = ".:)]}"


class DiagnosticRedactor:
    """Remove common credentials and local identity/path details from text."""

    def __init__(self, *, known_roots: list[Path] | None = None):
        roots = [Path.home(), Path.cwd()]
        roots.extend(known_roots or [])
        self._known_roots = sorted(
            {str(path.resolve()) for path in roots if str(path)},
            key=len,
            reverse=True,
        )
        self._known_values = sorted(
            {
                value
                for value in (getpass.getuser(), platform.node())
                if value and len(value) >= 3
            },
            key=len,
            reverse=True,
        )

    def redact(self, value: object) -> str:
        text = _CONTROL_RE.sub("", str(value))
        for root in self._known_roots:
            text = re.sub(re.escape(root), "<PATH>", text, flags=re.IGNORECASE)
            text = re.sub(
                re.escape(root.replace("\\", "/")),
                "<PATH>",
                text,
                flags=re.IGNORECASE,
            )
        text = _PLACEHOLDER_PATH_RE.sub(
            lambda match: _path_placeholder(match.group(0)),
            text,
        )
        for value in self._known_values:
            text = re.sub(re.escape(value), "<LOCAL_ID>", text, flags=re.IGNORECASE)

        # 键值对先于认证头：否则 "Token = abc" 会被 _AUTH_SCHEME_RE 当成
        # "Token + =" 只吞掉键名，把真实值留在明文里。
        text = _SECRET_RE.sub(
            lambda match: f"{match.group('quote')}{match.group('key')}"
            f"{match.group('quote')}{match.group('sep')}<REDACTED>",
            text,
        )
        text = _AUTH_SCHEME_RE.sub("<REDACTED>", text)
        text = _URL_USERINFO_RE.sub(r"\1<REDACTED>@", text)
        text = _URL_QUERY_RE.sub(r"\1?<REDACTED_QUERY>", text)
        text = _EMAIL_RE.sub("<EMAIL>", text)
        text = _QUOTED_WINDOWS_PATH_RE.sub(
            lambda match: f"{match.group('quote')}{_path_placeholder(match.group('path'))}"
            f"{match.group('quote')}",
            text,
        )
        return _WINDOWS_PATH_RE.sub(
            lambda match: _path_placeholder(match.group(0)),
            text,
        )


def _path_placeholder(raw_path: str) -> str:
    path = raw_path
    trailing = ""
    while path and path[-1] in _TRAILING_PATH_PUNCTUATION:
        trailing = path[-1] + trailing
        path = path[:-1]
    parts = [part for part in re.split(r"[\\/]", path) if part]
    basename = parts[-1] if parts else ""
    safe_name = basename if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", basename) else ""
    suffix = f"/{safe_name}" if safe_name else ""
    return f"<PATH>{suffix}{trailing}"
