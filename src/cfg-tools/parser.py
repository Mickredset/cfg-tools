from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union


PathLike = Union[str, Path]

_ALLOWED_KEY_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789_.-"
)


def _format_key(key: Any) -> str:
    key = str(key)

    if key and all(ch in _ALLOWED_KEY_CHARS for ch in key):
        return key

    return json.dumps(key, ensure_ascii=False)


def _format_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def dump_cfg(data: Dict[str, Dict[str, Any]]) -> str:
    lines = []

    for section, values in data.items():
        lines.append(f"[{section}]")

        for key, value in values.items():
            lines.append(f"{_format_key(key)}={_format_value(value)}")

        lines.append("")

    return "\n".join(lines)


def _read_quoted_string(line: str) -> tuple[str, str]:
    # line начинается с двойной кавычки
    i = 1
    n = len(line)

    while i < n:
        ch = line[i]

        if ch == "\\":
            i += 2
            continue

        if ch == '"':
            raw = line[: i + 1]

            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw[1:-1]

            return value, line[i + 1 :]

        i += 1

    raise ValueError(f"Не закрыта кавычка в строке: {line}")


def _split_key_value(line: str) -> tuple[str, str]:
    line = line.strip()

    if not line:
        raise ValueError("Пустая строка")

    if line[0] == '"':
        key, rest = _read_quoted_string(line)
        rest = rest.lstrip()

        if not rest.startswith("="):
            raise ValueError(f"Ожидался '=' после ключа: {line}")

        value = rest[1:].strip()
        return key, value

    key, sep, value = line.partition("=")

    if not sep:
        raise ValueError(f"Нет '=' в строке: {line}")

    return key.strip(), value.strip()


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()

    if raw == "":
        return ""

    # Сначала пробуем JSON.
    # Это корректно обрабатывает строки в двойных кавычках,
    # числа, true/false/null, списки и словщики.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Одинарные кавычки для ручного формата.
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1]

    # Если двойные кавычки были, но JSON не смог распарсить,
    # просто снимаем их.
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]

    low = raw.lower()

    if low == "true":
        return True

    if low == "false":
        return False

    if low in ("none", "null"):
        return None

    try:
        return int(raw)
    except ValueError:
        pass

    try:
        return float(raw)
    except ValueError:
        pass

    return raw


def parse_cfg(text: str) -> Dict[str, Dict[str, Any]]:
    data: Dict[str, Dict[str, Any]] = {}

    section = "DEFAULT"
    data[section] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line[0] in "#;":
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data.setdefault(section, {})
            continue

        key, value_raw = _split_key_value(line)
        data[section][key] = _parse_scalar(value_raw)

    if not data["DEFAULT"]:
        data.pop("DEFAULT", None)

    return data


def load_cfg(path: PathLike) -> Dict[str, Dict[str, Any]]:
    return parse_cfg(Path(path).read_text(encoding="utf-8"))


def save_cfg(path: PathLike, data: Dict[str, Dict[str, Any]]) -> None:
    Path(path).write_text(dump_cfg(data), encoding="utf-8")