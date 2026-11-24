"""Local allow and deny policy for command text found next to a Cursor button.

The policy fails closed. A hard deny cannot be overridden by a custom rule.
No Cursor or Windows security setting is changed here; this module only decides
whether a button that is already on screen may be invoked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

MAX_CONTEXT_CHARS = 8000
MAX_COMMANDS = 4
MAX_CUSTOM_PATTERN = 200

HARD_BLOCK_SUBSTRINGS = (
    "reject",
    "cancel",
    "deny",
    "skip",
    "dismiss",
    "decline",
    "allowlist",
    "allow list",
    "allow-list",
    "add to allow",
    "keep all",
    "keep file",
    "accept all",
    "undo all",
    "discard",
    "outside sandbox",
    "outside the sandbox",
    "full permission",
    "without sandbox",
    "run and debug",
    "don't run",
    "do not run",
    "do not allow",
    "don't allow",
    "always run",
    "always allow",
)

DEFAULT_APPROVAL_LABELS = (
    "run",
    "allow",
    "allow once",
    "run command",
    "continue",
    "run in sandbox",
)

_CARD_CHROME = frozenset(
    {
        "skip",
        "skip step",
        "always run",
        "always allow",
        "allowlist",
        "allow list",
        "allow-list",
        "run",
        "run step",
        "reject",
        "cancel",
        "deny",
        "allow",
        "continue",
    }
)

_UI_NOISE = frozenset(
    DEFAULT_APPROVAL_LABELS
    + HARD_BLOCK_SUBSTRINGS
    + (
        "agent",
        "cursor",
        "terminal",
        "shell",
        "command",
        "pending",
        "approval",
        "copy",
        "edit",
        "show more",
        "accept",
        "keep",
        "undo",
        "sandbox",
        "yes",
        "no",
    )
)

_PROSE_TOKENS = frozenset({"type", "echo", "set", "format", "more", "time"})

_UNSANDBOXED_RE = re.compile(
    r"outside\s+(?:the\s+)?sandbox|full\s+permissions?|without\s+sandbox|"
    r"unsandboxed|run\s+outside|не\s+в\s+пісочниці|повн(?:і|ими)\s+права",
    re.IGNORECASE,
)
_PROSE_RE = re.compile(
    r"\b(?:the|this|that|please|you|your|want|should|click|will|with|from|into|button)\b"
    r".{0,48}\b(?:the|this|that|please|you|your|want|should|click|will|button|command)\b",
    re.IGNORECASE,
)
_PROMPT_RE = re.compile(
    r"^(?:PS\s+[A-Za-z]:\\[^>\n]*>|[A-Za-z]:\\[^>\n]*>|\$\s+|>\s+)",
    re.IGNORECASE,
)
_SECRET_NAME_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|access[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_TARGET_RE = re.compile(
    r"("
    r"(?:^|[\s/\\'\"`])\.env\b|"
    r"id_rsa|"
    r"(?:^|[\s/\\'\"`])[\w.-]*\.pem\b|"
    r"credentials\.(?:json|yml|yaml|txt|xml)|"
    r"secrets?\.(?:json|yml|yaml|txt)|"
    r"\.npmrc|\.pypirc|"
    r"(?:^|[\s/\\'\"`])\.aws\b|(?:^|[\s/\\'\"`])\.ssh\b|"
    r"BEGIN\s+(?:RSA\s+|OPENSSH\s+)?PRIVATE\s+KEY|"
    r"api[_-]?key|access[_-]?token|"
    r"(?:--?password|--?token|--?secret)\b|"
    r"(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)\s*[=:]\s*\S+|"
    r"\bcmdkey\b|\bprintenv\b|Get-ChildItem\s+Env:|\$env:|"
    r"\bbearer\s+\S+|authorization\s*[:=]"
    r")",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"(https?://|git\+|ftp://|\bssh://)", re.IGNORECASE)
_REDIRECT_RE = re.compile(r"(?:^|\s)>{1,2}(?:\s|$)", re.IGNORECASE)
_ASSIGN_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)=(?:'[^']*'|\"[^\"]*\"|\S+)\s+"
)
_SEGMENT_SPLIT_RE = re.compile(
    r"\s*(?:&&|\|\||;|(?<!>)&(?!>)|(?<!\|)\|(?!\|))\s*"
)
_HOTKEY_SUFFIX_RE = re.compile(
    r"\s*\((?:enter|return|shift\+enter|ctrl\+enter|alt\+enter)\)\s*$",
    re.IGNORECASE,
)

_READ_TOKENS = frozenset(
    {
        "dir",
        "ls",
        "pwd",
        "cd",
        "cat",
        "type",
        "get-childitem",
        "gci",
        "get-content",
        "get-location",
        "select-string",
        "write-output",
        "echo",
        "where",
        "where.exe",
        "which",
        "get-command",
        "rg",
        "findstr",
        "more",
        "less",
    }
)
_FILE_READ_TOKENS = frozenset({"cat", "type", "get-content"})
_DELETE_TOKENS = frozenset(
    {
        "rm",
        "rmdir",
        "rd",
        "unlink",
        "del",
        "erase",
        "rimraf",
        "remove-item",
    }
)
_DISK_TOKENS = frozenset(
    {
        "format",
        "format-volume",
        "clear-disk",
        "initialize-disk",
        "diskpart",
        "mkfs",
        "mkfs.ext4",
        "mkfs.ntfs",
        "dd",
        "cipher",
    }
)
_ADMIN_TOKENS = frozenset(
    {
        "sudo",
        "gsudo",
        "runas",
        "bcdedit",
        "netsh",
        "schtasks",
        "set-executionpolicy",
        "set-mppreference",
        "takeown",
        "icacls",
        "shutdown",
        "restart-computer",
        "stop-computer",
        "regedit",
        "wmic",
        "vssadmin",
    }
)
_SCRIPT_TOKENS = frozenset({"iex", "invoke-expression", "certutil", "bitsadmin"})
_PM_TOKENS = frozenset({"npm", "pnpm", "yarn"})
_SAFE_PM_SCRIPTS = frozenset({"build", "test", "lint", "typecheck", "check"})
_NORMAL_PM_SCRIPTS = frozenset({"dev", "start", "format", "fmt"})
_SAFE_GIT = frozenset(
    {"status", "diff", "log", "show", "branch", "rev-parse", "ls-files", "shortlog"}
)
_NORMAL_GIT = frozenset(
    {"add", "commit", "switch", "stash", "pull", "fetch", "merge", "tag", "checkout"}
)
_BROAD_REGEX_PROBES = ("a", "b", "zz", "12")


class RunMode(str, Enum):
    SAFE = "safe"
    NORMAL = "normal"
    MANUAL = "manual"

    @classmethod
    def parse(cls, value: object) -> "RunMode":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        try:
            return cls(text)
        except ValueError:
            return cls.SAFE


@dataclass(frozen=True)
class SegmentVerdict:
    outcome: str
    level: str
    category: str
    reason: str


def normalize_label(name: str) -> str:
    text = (name or "").replace("&", " ").replace("…", " ")
    text = text.replace("...", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = _HOTKEY_SUFFIX_RE.sub("", text).strip()
    return text


def is_approval_button(name: str, extra_labels: list[str] | None = None) -> tuple[bool, str]:
    """Return whether this accessible name is a command-approval button."""
    label = normalize_label(name)
    if not label:
        return False, "порожня назва кнопки"
    for blocked in HARD_BLOCK_SUBSTRINGS:
        if blocked in label:
            return False, f"кнопку «{name.strip()}» не натискаємо"
    allowed = set(DEFAULT_APPROVAL_LABELS)
    for item in extra_labels or []:
        extra = normalize_label(item)
        if not extra or any(blocked in extra for blocked in HARD_BLOCK_SUBSTRINGS):
            continue
        allowed.add(extra)
    if label in allowed or label.startswith("allow once") or label.startswith("run in sandbox"):
        return True, ""
    # Cursor names the blue button "Run" or "Run step", not only "Run".
    if label == "run" or label.startswith("run "):
        return True, ""
    return False, "не кнопка підтвердження команди"


def looks_like_visible_script(text: str) -> bool:
    """PowerShell shown inside one approval card, including a single wrapped line."""
    body = text or ""
    if re.search(r"(?i)\$[A-Za-z_][\w]*\s*=", body) is None:
        return False
    if body.count("\n") >= 1:
        return True
    return re.search(r"(?i)\bNew-Object\b|\b-ComObject\b|\bWrite-Output\b|\bforeach\b", body) is not None


def _script_body(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        label = normalize_label(line)
        if label in _UI_NOISE or label in _CARD_CHROME or label.startswith("skip "):
            continue
        if len(line) < 40 and is_approval_button(line)[0]:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def redact(command: str) -> str:
    redacted = re.sub(
        r"(?i)(password|passwd|secret|token|api[_-]?key|access[_-]?key)"
        r"(\s*[=:]\s*)(\S+)",
        r"\1\2<приховано>",
        command or "",
    )
    return redacted[:300]


def extract_commands(text: str, custom_rules: list[str] | None = None) -> list[str]:
    """Pull command lines out of the short text around one approval button."""
    rules = custom_rules or []
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*", "", cleaned)
    found: list[str] = []
    seen: set[str] = set()
    for raw in cleaned.split("\n"):
        line = raw.strip().strip("`").strip()
        if not line:
            continue
        if normalize_label(line) in _UI_NOISE:
            continue
        prepared = _strip_prompt(line)
        token, _args = _split_token(prepared)
        if token in _PROSE_TOKENS and _PROSE_RE.search(line):
            continue
        recognized = (
            _hard_deny(prepared) is not None
            or token in _known_tokens()
            or _custom_match(prepared, rules)
        )
        if not recognized:
            continue
        key = prepared.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(prepared)
    if looks_like_visible_script(cleaned):
        script = _script_body(cleaned)
        if script:
            return [script]
    return found


def classify_command(command: str, custom_rules: list[str] | None = None) -> SegmentVerdict:
    """Classify one command line. Deny is checked before any custom allow."""
    rules = custom_rules or []
    raw = _strip_prompt(command)
    if not raw:
        return SegmentVerdict("unknown", "", "context", "порожня команда")
    denied = _hard_deny(_mask_quotes(raw))
    if denied is not None:
        return denied
    if _URL_RE.search(raw):
        return SegmentVerdict(
            "deny",
            "",
            "remote",
            "завантаження або віддалений код потребує ручного підтвердження",
        )
    visible = _mask_quotes(raw)
    if looks_like_visible_script(raw):
        if "$(" in visible or "${" in visible:
            return SegmentVerdict(
                "unknown",
                "",
                "substitution",
                "підстановка команди прихована, потрібне ручне підтвердження",
            )
        if re.search(
            r"(?i)\b(?:remove-item|clear-item|clear-content|out-file|set-content|"
            r"add-content|tee-object)\b|\brm\s+-",
            raw,
        ):
            return SegmentVerdict(
                "deny",
                "",
                "deletion",
                "видалення або перезапис у скрипті потребує ручного підтвердження",
            )
        if re.search(r"(?i)\b(?:invoke-expression|start-process)\b|\biex\b", raw):
            return SegmentVerdict(
                "deny",
                "",
                "scripts",
                "запуск іншої команди зі скрипта потребує ручного підтвердження",
            )
        for line in raw.splitlines():
            piece = line.strip().rstrip("{").strip()
            if not piece or re.fullmatch(r"[{}]+", piece) or piece in {"else", "elseif"}:
                continue
            for segment in _split_segments(piece):
                line_verdict = _classify_segment(segment)
                if line_verdict.outcome == "deny":
                    return line_verdict
        return SegmentVerdict(
            "allow",
            "safe",
            "allowed",
            "видимий скрипт без заборонених дій",
        )
    if "$(" in visible or "${" in visible or "`" in visible:
        return SegmentVerdict(
            "unknown",
            "",
            "substitution",
            "підстановка команди прихована, потрібне ручне підтвердження",
        )

    levels: list[str] = []
    for segment in _split_segments(raw):
        verdict = _classify_segment(segment)
        if verdict.outcome == "deny":
            return verdict
        if verdict.outcome != "allow":
            matched, level = _custom_match_level(segment, rules)
            if not matched:
                return verdict
            verdict = SegmentVerdict(
                "allow",
                level,
                "custom",
                "команда збігається з вашим дозволеним правилом",
            )
        levels.append(verdict.level)
    if levels and all(level == "safe" for level in levels):
        return SegmentVerdict("allow", "safe", "allowed", "команда дозволена у безпечному режимі")
    if levels:
        return SegmentVerdict("allow", "normal", "allowed", "команда дозволена у звичайному режимі")
    return SegmentVerdict("unknown", "", "unknown", "команда не входить до дозволених правил")


def _known_tokens() -> frozenset[str]:
    return (
        _READ_TOKENS
        | _DELETE_TOKENS
        | _DISK_TOKENS
        | _ADMIN_TOKENS
        | _SCRIPT_TOKENS
        | _PM_TOKENS
        | frozenset(
            {
                "git",
                "pytest",
                "py.test",
                "python",
                "python3",
                "py",
                "pip",
                "pip3",
                "cargo",
                "go",
                "dotnet",
                "msbuild",
                "tsc",
                "cmake",
                "make",
                "mingw32-make",
                "ninja",
                "docker",
                "node",
                "npx",
                "ruff",
                "black",
                "mypy",
                "eslint",
                "prettier",
                "jest",
                "vitest",
                "phpunit",
                "mvn",
                "gradle",
                "powershell",
                "pwsh",
                "cmd",
                "bash",
                "sh",
                "curl",
                "wget",
                "iwr",
                "invoke-webrequest",
                "reg",
                "sc",
                "net",
                "sudo",
                "start-process",
                "set",
            }
        )
    )


def _mask_quotes(command: str) -> str:
    return re.sub(r""""(?:\\.|[^"])*"|'(?:\\.|[^'])*'""", " ", command)


def _strip_prompt(line: str) -> str:
    text = (line or "").strip()
    text = _PROMPT_RE.sub("", text).strip()
    text = re.sub(r"^&\s+", "", text)
    return text


def _split_token(segment: str) -> tuple[str, str]:
    parts = segment.split(None, 1)
    if not parts:
        return "", ""
    token = parts[0].strip().strip('"').strip("'")
    token = token.replace("\\", "/").split("/")[-1].lower()
    if token.endswith(".exe"):
        token = token[:-4]
    if token.endswith(".cmd"):
        token = token[:-4]
    args = parts[1] if len(parts) > 1 else ""
    return token, args


def _split_segments(command: str) -> list[str]:
    parts = [part.strip() for part in _SEGMENT_SPLIT_RE.split(command) if part.strip()]
    return parts or [command.strip()]


def _first_word(text: str) -> tuple[str, str]:
    parts = text.strip().split(None, 1)
    if not parts:
        return "", ""
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _hard_deny(command: str) -> SegmentVerdict | None:
    command = _mask_quotes(command)
    patterns: tuple[tuple[str, str, str], ...] = (
        (
            r"(?:^|&&|\|\||[;|&])\s*(?:sudo|gsudo|runas)\b",
            "admin",
            "команда з правами адміністратора потребує ручного підтвердження",
        ),
        (
            r"-verb\s+runas",
            "admin",
            "запуск із підвищенням прав потребує ручного підтвердження",
        ),
        (
            r"\b(?:bcdedit|netsh|schtasks|set-executionpolicy|set-mppreference|"
            r"takeown|icacls|shutdown|restart-computer|stop-computer|regedit|wmic)\b",
            "system",
            "зміна системних налаштувань потребує ручного підтвердження",
        ),
        (
            r"\breg(?:\.exe)?\s+(?:add|delete|import)\b",
            "system",
            "зміна реєстру потребує ручного підтвердження",
        ),
        (
            r"\bnet(?:\.exe)?\s+(?:user|localgroup)\b",
            "admin",
            "зміна облікових записів потребує ручного підтвердження",
        ),
        (
            r"\bsc(?:\.exe)?\s+(?:config|delete|create|stop)\b",
            "system",
            "зміна служб Windows потребує ручного підтвердження",
        ),
        (
            r"\b(?:format-volume|clear-disk|initialize-disk|diskpart|mkfs(?:\.\w+)?)\b|"
            r"\bformat(?:\.exe)?\s+[a-z]:|\bcipher\s+/w\b|\bdd\s+if=|\bvssadmin\s+delete\b",
            "disk",
            "операція з диском потребує ручного підтвердження",
        ),
        (
            r"\bgit\s+push\b|\b(?:npm|pnpm|yarn)\s+publish\b|\bdocker\s+push\b|"
            r"\bkubectl\b|\bhelm\s+(?:install|upgrade|uninstall|delete|rollback)\b|"
            r"\bterraform\s+apply\b|\bpulumi\s+up\b|"
            r"\b(?:serverless|sls)\s+deploy\b|\bfly(?:ctl)?\s+deploy\b|"
            r"\bwrangler\s+(?:publish|deploy)\b|\bfirebase\s+deploy\b|"
            r"\baz\s+(?:webapp|deployment|aks|group)\b|"
            r"\bgcloud\s+(?:app|run|compute|container)\s+deploy\b|"
            r"\b(?:scp|rsync)\b|\bgh\s+(?:pr|release|repo)\b|"
            r"\bvercel\s+(?:deploy|--prod)\b|\bdotnet\s+nuget\s+push\b|"
            r"\bcargo\s+publish\b|\btwine\s+upload\b",
            "publish",
            "публікація або розгортання потребує ручного підтвердження",
        ),
        (
            r"\b(?:curl|wget|iwr|invoke-webrequest)\b.*\|\s*(?:(?:ba|z|pw)?sh|powershell|pwsh|iex)\b|"
            r"\|\s*(?:iex|invoke-expression)\b|\binvoke-expression\b|\biex\b|"
            r"-encodedcommand|\b(?:certutil|bitsadmin)\b",
            "scripts",
            "невідомий або закодований скрипт потребує ручного підтвердження",
        ),
        (
            r"\bgit\s+clean\b|\bgit\s+reset\b|\bgit\s+restore\b|\bgit\s+checkout\s+--|"
            r"\b(?:make|gradle|mvn|npm|pnpm|yarn)\s+clean\b|\bnpm\s+ci\b|"
            r"\bpip(?:3)?\s+uninstall\b|\bdocker\s+(?:rm|rmi|system\s+prune)\b|"
            r"\b(?:rimraf|shutil\.rmtree)\b",
            "deletion",
            "видалення файлів потребує ручного підтвердження",
        ),
    )
    for pattern, category, reason in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return SegmentVerdict("deny", "", category, reason)
    if _SECRET_TARGET_RE.search(command):
        return SegmentVerdict(
            "deny",
            "",
            "secrets",
            "команда торкається секретів або облікових даних і потребує ручного підтвердження",
        )
    return None


def _classify_segment(segment: str) -> SegmentVerdict:
    segment, env_error = _strip_env(segment)
    if env_error:
        return SegmentVerdict("deny", "", "secrets", env_error)
    segment = _unwrap_shell(segment)
    denied = _hard_deny(segment)
    if denied is not None:
        return denied
    if _REDIRECT_RE.search(segment) or re.search(
        r"\b(?:out-file|set-content|add-content|tee-object)\b",
        segment,
        re.IGNORECASE,
    ):
        return SegmentVerdict(
            "deny",
            "",
            "deletion",
            "перезапис файлу потребує ручного підтвердження",
        )
    token, args = _split_token(segment)
    if not token:
        return SegmentVerdict("unknown", "", "unknown", "порожній фрагмент команди")
    if token in _DELETE_TOKENS:
        return SegmentVerdict("deny", "", "deletion", "видалення файлів потребує ручного підтвердження")
    if token in _DISK_TOKENS:
        return SegmentVerdict("deny", "", "disk", "операція з диском потребує ручного підтвердження")
    if token in _ADMIN_TOKENS or token == "start-process" and re.search(r"-verb\s+runas", args, re.I):
        return SegmentVerdict("deny", "", "admin", "команда з правами адміністратора потребує ручного підтвердження")
    if token in _SCRIPT_TOKENS:
        return SegmentVerdict("deny", "", "scripts", "невідомий скрипт потребує ручного підтвердження")
    if token in {"curl", "wget", "iwr", "invoke-webrequest"}:
        return SegmentVerdict("deny", "", "remote", "завантаження з мережі потребує ручного підтвердження")
    if token in {"powershell", "pwsh"} and re.search(r"-encodedcommand|(?:^|\s)-e(?:nc)?(?:\s|$)", args, re.I):
        return SegmentVerdict("deny", "", "scripts", "закодована команда PowerShell потребує ручного підтвердження")
    if token == "set" and not args.strip():
        return SegmentVerdict("deny", "", "secrets", "вивід змінних середовища потребує ручного підтвердження")

    classified = _allow_known(token, args)
    if classified is not None:
        return classified
    return SegmentVerdict("unknown", "", "unknown", "команда не входить до дозволених правил")


def _strip_env(segment: str) -> tuple[str, str | None]:
    text = segment.strip()
    while True:
        match = _ASSIGN_RE.match(text)
        if match is None:
            return text, None
        if _SECRET_NAME_RE.search(match.group(1)):
            return text, "секрет у змінній середовища потребує ручного підтвердження"
        text = text[match.end() :]


def _unwrap_shell(segment: str) -> str:
    match = re.match(
        r"^(?:powershell|pwsh)(?:\.exe)?\s+(?:(?:-[A-Za-z]+)\s+)*-(?:command|c)\s+(.+)$",
        segment,
        re.IGNORECASE,
    )
    if match:
        return _strip_quotes(match.group(1))
    match = re.match(r"^cmd(?:\.exe)?\s+/c\s+(.+)$", segment, re.IGNORECASE)
    if match:
        return _strip_quotes(match.group(1))
    return segment


def _strip_quotes(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _allow_known(token: str, args: str) -> SegmentVerdict | None:
    if token in _FILE_READ_TOKENS:
        if not args.strip():
            return SegmentVerdict("unknown", "", "unknown", "не вказано, який файл читати")
        return _safe("читання файлу")
    if token in _READ_TOKENS:
        return _safe("читання або локальний перегляд")
    if token == "git":
        return _classify_git(args)
    if token in _PM_TOKENS:
        return _classify_pm(args)
    if token in {"pytest", "py.test", "phpunit", "jest", "vitest"}:
        return _safe("запуск тестів")
    if token in {"python", "python3", "py"}:
        return _classify_python(args)
    if token in {"pip", "pip3"}:
        return _classify_pip(args)
    if token == "cargo":
        return _classify_cargo(args)
    if token == "go":
        return _classify_go(args)
    if token == "dotnet":
        return _classify_dotnet(args)
    if token in {"msbuild", "tsc"}:
        return _safe("локальна збірка")
    if token == "cmake":
        if args.strip().startswith("--build") or args.strip() in {"--version", "-version"}:
            return _safe("локальна збірка")
        return None
    if token in {"make", "mingw32-make"}:
        return _classify_make(args)
    if token == "ninja":
        return _classify_ninja(args)
    if token == "docker":
        return _classify_docker(args)
    if token == "node":
        return _classify_node(args)
    if token == "npx":
        return _classify_npx(args)
    if token in {"ruff", "mypy", "eslint"}:
        return _safe("локальна перевірка коду")
    if token in {"black", "prettier"}:
        return _normal("форматування коду в проєкті")
    if token in {"mvn", "gradle"}:
        sub, _rest = _first_word(args)
        if sub in {"test", "verify"} or (token == "gradle" and sub in {"test", "check", "build"}):
            return _safe("запуск тестів або локальна збірка")
        if sub in {"package", "assemble", "install"} and "publish" not in args.lower():
            return _normal("локальна збірка проєкту")
        return None
    return None


def _classify_git(args: str) -> SegmentVerdict:
    sub, rest = _first_word(args)
    sub = sub.lower()
    if sub in {"clean", "reset", "restore"}:
        return SegmentVerdict("deny", "", "deletion", "видалення або скидання файлів потребує ручного підтвердження")
    if sub == "push":
        return SegmentVerdict("deny", "", "publish", "публікація коду потребує ручного підтвердження")
    if sub == "checkout" and ("--" in rest.split() or re.search(r"(?:^|\s)-(?:f|-force)\b", rest)):
        return SegmentVerdict("deny", "", "deletion", "скидання файлів через git checkout потребує ручного підтвердження")
    if sub == "switch" and re.search(r"(?:^|\s)-(?:f|-force|-discard-changes)\b", rest):
        return SegmentVerdict("deny", "", "deletion", "втрата локальних змін потребує ручного підтвердження")
    if sub in _SAFE_GIT:
        return _safe("читання стану git")
    if sub == "remote" and (not rest or re.match(r"(?:-v|show|get-url)\b", rest)):
        return _safe("читання стану git")
    if sub == "config" and re.match(r"(?:--get|--list|-l)\b", rest):
        return _safe("читання налаштувань git")
    if sub in _NORMAL_GIT:
        return _normal("звичайна команда git у репозиторії")
    return SegmentVerdict("unknown", "", "unknown", "ця команда git не входить до дозволених правил")


def _classify_pm(args: str) -> SegmentVerdict:
    sub, rest = _first_word(args)
    sub = sub.lower()
    if sub == "publish":
        return SegmentVerdict("deny", "", "publish", "публікація пакета потребує ручного підтвердження")
    if sub == "ci":
        return SegmentVerdict("deny", "", "deletion", "npm ci видаляє наявні залежності і потребує ручного підтвердження")
    if sub in {"test", "t"}:
        return _safe("запуск тестів")
    if sub in {"--version", "-v", "version", "ls", "list", "outdated"}:
        return _safe("перегляд пакета")
    if sub == "run":
        script, _tail = _first_word(rest)
        script = script.lower()
        if script in _SAFE_PM_SCRIPTS:
            return _safe("тести, перевірка або локальна збірка")
        if script in _NORMAL_PM_SCRIPTS:
            return _normal("звичайний сценарій розробки")
        return SegmentVerdict("unknown", "", "scripts", "невідомий npm-скрипт потребує ручного підтвердження")
    if sub in {"install", "i", "add", "update"}:
        return _normal("встановлення залежностей проєкту")
    return SegmentVerdict("unknown", "", "unknown", "ця команда пакетного менеджера не входить до дозволених правил")


def _classify_python(args: str) -> SegmentVerdict:
    text = args.strip()
    if re.match(r"(?:-c|--command)\b", text):
        return SegmentVerdict("deny", "", "scripts", "вбудований скрипт Python потребує ручного підтвердження")
    if re.match(r"-m\s+pytest\b", text) or re.match(r"-m\s+unittest\b", text):
        return _safe("запуск тестів")
    pip_match = re.match(r"-m\s+pip(?:3)?\b\s*(.*)$", text, re.IGNORECASE)
    if pip_match:
        return _classify_pip(pip_match.group(1))
    if text in {"--version", "-V", "-VV", "-v"} or text.lower() == "version":
        return _safe("перегляд версії")
    return SegmentVerdict("unknown", "", "scripts", "невідомий скрипт Python потребує ручного підтвердження")


def _classify_pip(args: str) -> SegmentVerdict:
    sub, _rest = _first_word(args)
    sub = sub.lower()
    if sub == "uninstall":
        return SegmentVerdict("deny", "", "deletion", "видалення пакета потребує ручного підтвердження")
    if sub == "install":
        return _normal("встановлення залежностей Python")
    if sub in {"freeze", "list", "show", "check", "--version", "-v"}:
        return _safe("перегляд пакетів Python")
    return SegmentVerdict("unknown", "", "unknown", "ця команда pip не входить до дозволених правил")


def _classify_cargo(args: str) -> SegmentVerdict:
    sub, _rest = _first_word(args)
    sub = sub.lower()
    if sub == "publish":
        return SegmentVerdict("deny", "", "publish", "публікація crate потребує ручного підтвердження")
    if sub in {"test", "build", "check", "clippy"}:
        return _safe("тести або локальна збірка Cargo")
    if sub in {"fmt", "add", "update", "fetch"}:
        return _normal("звичайна команда Cargo")
    if sub in {"--version", "-V"}:
        return _safe("перегляд версії")
    return SegmentVerdict("unknown", "", "unknown", "ця команда Cargo не входить до дозволених правил")


def _classify_go(args: str) -> SegmentVerdict:
    sub, _rest = _first_word(args)
    sub = sub.lower()
    if sub in {"test", "build"}:
        return _safe("тести або локальна збірка Go")
    if sub in {"fmt", "vet", "get", "mod"}:
        return _normal("звичайна команда Go")
    if sub == "version":
        return _safe("перегляд версії")
    return SegmentVerdict("unknown", "", "unknown", "ця команда Go не входить до дозволених правил")


def _classify_dotnet(args: str) -> SegmentVerdict:
    lowered = args.lower()
    if "nuget" in lowered and "push" in lowered:
        return SegmentVerdict("deny", "", "publish", "публікація пакета NuGet потребує ручного підтвердження")
    sub, _rest = _first_word(args)
    sub = sub.lower()
    if sub in {"test", "build"}:
        return _safe("тести або локальна збірка .NET")
    if sub in {"run", "restore", "format"}:
        return _normal("звичайна команда .NET")
    if sub in {"--version", "-v", "--info"}:
        return _safe("перегляд версії")
    return SegmentVerdict("unknown", "", "unknown", "ця команда dotnet не входить до дозволених правил")


def _classify_make(args: str) -> SegmentVerdict:
    target, _rest = _first_word(args)
    target = target.lower()
    if target in {"clean", "distclean", "mrproper"}:
        return SegmentVerdict("deny", "", "deletion", "очищення збірки видаляє файли і потребує ручного підтвердження")
    if not target or target in {"all", "build", "test", "check"}:
        return _safe("локальна збірка або тести")
    return SegmentVerdict("unknown", "", "unknown", "невідома ціль make потребує ручного підтвердження")


def _classify_ninja(args: str) -> SegmentVerdict:
    target, _rest = _first_word(args)
    target = target.lower()
    if target == "clean":
        return SegmentVerdict("deny", "", "deletion", "очищення збірки потребує ручного підтвердження")
    if not target or target in {"all", "build", "test"}:
        return _safe("локальна збірка")
    return SegmentVerdict("unknown", "", "unknown", "невідома ціль ninja потребує ручного підтвердження")


def _classify_docker(args: str) -> SegmentVerdict:
    sub, rest = _first_word(args)
    sub = sub.lower()
    if sub == "push" or sub in {"rm", "rmi"} or (sub == "system" and "prune" in rest.lower()):
        return SegmentVerdict("deny", "", "publish" if sub == "push" else "deletion", "ця команда Docker потребує ручного підтвердження")
    if sub == "build":
        return _normal("локальна збірка образу Docker")
    if sub in {"ps", "images", "version", "info"}:
        return _safe("перегляд Docker")
    return SegmentVerdict("unknown", "", "unknown", "ця команда Docker не входить до дозволених правил")


def _classify_node(args: str) -> SegmentVerdict:
    text = args.strip()
    if re.match(r"(?:-e|-p|--eval)\b", text):
        return SegmentVerdict("deny", "", "scripts", "вбудований скрипт Node потребує ручного підтвердження")
    if text in {"--version", "-v"}:
        return _safe("перегляд версії")
    return SegmentVerdict("unknown", "", "scripts", "невідомий скрипт Node потребує ручного підтвердження")


def _classify_npx(args: str) -> SegmentVerdict:
    tool, _rest = _first_word(args)
    tool = tool.lower()
    if tool in {"tsc", "eslint", "vitest", "jest"}:
        return _safe("локальна перевірка або тести")
    if tool == "prettier":
        return _normal("форматування коду в проєкті")
    return SegmentVerdict("unknown", "", "scripts", "невідома команда npx потребує ручного підтвердження")


def _safe(reason: str) -> SegmentVerdict:
    return SegmentVerdict("allow", "safe", "allowed", reason)


def _normal(reason: str) -> SegmentVerdict:
    return SegmentVerdict("allow", "normal", "allowed", reason)


def _custom_match(command: str, rules: list[str]) -> bool:
    matched, _level = _custom_match_level(command, rules)
    return matched


def _custom_match_level(command: str, rules: list[str]) -> tuple[bool, str]:
    for raw in rules:
        parsed = _parse_rule(raw)
        if parsed is None:
            continue
        level, kind, pattern = parsed
        if kind == "prefix" and _prefix_match(command, pattern):
            return True, level
        if kind == "regex":
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return True, level
            except re.error:
                continue
    return False, ""


def _prefix_match(command: str, pattern: str) -> bool:
    if not command.lower().startswith(pattern.lower()):
        return False
    rest = command[len(pattern) :]
    return rest == "" or rest[0].isspace()


def _parse_rule(raw: str) -> tuple[str, str, str] | None:
    text = (raw or "").strip()
    if not text or text.startswith("#"):
        return None
    level = "normal"
    if text.lower().startswith("safe:"):
        level = "safe"
        text = text[5:].strip()
    if text.lower().startswith("re:"):
        pattern = text[3:].strip()
        if not _regex_is_usable(pattern):
            return None
        return level, "regex", pattern
    if len(text) < 2:
        return None
    return level, "prefix", text


def _regex_is_usable(pattern: str) -> bool:
    if not pattern or len(pattern) > MAX_CUSTOM_PATTERN:
        return False
    if pattern in {".*", ".+", "^.*$", "^.*", "^", "$", r"\w+", "."}:
        return False
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return False
    if compiled.search(""):
        return False
    if all(compiled.search(probe) for probe in _BROAD_REGEX_PROBES):
        return False
    return True


def context_is_unsandboxed(button_name: str, context: str) -> bool:
    return bool(_UNSANDBOXED_RE.search(button_name or "") or _UNSANDBOXED_RE.search(context or ""))
