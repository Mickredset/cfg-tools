from __future__ import annotations

import types
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from .codec import Codec, default_codec
from .parser import load_cfg, save_cfg


PathLike = Union[str, Path]


class Config:
    def __init__(self, path: Optional[PathLike] = None, codec: Optional[Codec] = None):
        self.codec = codec or default_codec
        self.data: Dict[str, Dict[str, Any]] = {}

        if path is not None:
            self.load(path)

    def load(self, path: PathLike) -> "Config":
        p = Path(path)

        if p.exists():
            self.data = load_cfg(p)
        else:
            self.data = {}

        return self

    def save(self, path: PathLike) -> "Config":
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        encoded: Dict[str, Dict[str, Any]] = {}

        for section, values in self.data.items():
            encoded[section] = {}

            for key, value in values.items():
                encoded[section][key] = self.codec.encode(value)

        save_cfg(p, encoded)

        return self

    def sections(self) -> List[str]:
        return list(self.data.keys())

    def has_section(self, section: str) -> bool:
        return section in self.data

    def section(self, section: str) -> Dict[str, Any]:
        return self.data.setdefault(section, {})

    def set(self, section: str, key: str, value: Any) -> None:
        self.data.setdefault(section, {})[key] = value

    def set_object(self, section: str, key: str, obj: Any) -> None:
        self.set(section, key, self.codec.encode(obj))

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.data.get(section, {}).get(key, default)

    def get_object(self, section: str, key: str, default: Any = None) -> Any:
        if section not in self.data or key not in self.data[section]:
            return default

        return self.codec.decode(self.data[section][key])


def save_variables(
    path_or_config: Union[PathLike, Config],
    variables: Dict[str, Any],
    section: str = "variables",
    exclude: Optional[
        Union[str, Iterable[Any], Callable[[str, Any], bool]]
    ] = None,
    exclude_prefixes: Optional[Union[str, Iterable[str]]] = ("_",),
    exclude_types: Optional[Union[type, Iterable[type]]] = None,
    include_modules: bool = False,
    include_callables: bool = False,
    on_error: str = "skip",
    codec: Optional[Codec] = None,
) -> Tuple[Config, List[Tuple[str, str]]]:
    if isinstance(path_or_config, Config):
        cfg = path_or_config
        should_save = False
        save_path = None
    else:
        save_path = Path(path_or_config)
        cfg = Config(save_path if save_path.exists() else None, codec=codec)
        should_save = True

    if codec is not None:
        cfg.codec = codec

    exclude_names = set()
    exclude_predicates: List[Callable[[str, Any], bool]] = []

    if exclude is not None:
        if isinstance(exclude, str):
            exclude_names.add(exclude)
        elif callable(exclude) and not isinstance(exclude, (set, list, tuple, frozenset)):
            exclude_predicates.append(exclude)
        else:
            for item in exclude:
                if callable(item):
                    exclude_predicates.append(item)
                else:
                    exclude_names.add(item)

    if exclude_prefixes is None:
        prefixes = ()
    elif isinstance(exclude_prefixes, str):
        prefixes = (exclude_prefixes,)
    else:
        prefixes = tuple(exclude_prefixes)

    if exclude_types is None:
        types_tuple = ()
    elif isinstance(exclude_types, type):
        types_tuple = (exclude_types,)
    else:
        types_tuple = tuple(exclude_types)

    skipped: List[Tuple[str, str]] = []

    for name, value in variables.items():
        if not isinstance(name, str):
            continue

        if name in exclude_names:
            continue

        if prefixes and any(name.startswith(prefix) for prefix in prefixes):
            continue

        if types_tuple and isinstance(value, types_tuple):
            continue

        if any(predicate(name, value) for predicate in exclude_predicates):
            continue

        if not include_modules and isinstance(value, types.ModuleType):
            continue

        if not include_callables and callable(value) and not isinstance(value, type):
            continue

        try:
            cfg.set_object(section, name, value)
        except Exception as exc:
            if on_error == "raise":
                raise

            skipped.append((name, f"{type(exc).__name__}: {exc}"))

    if should_save and save_path is not None:
        cfg.save(save_path)

    return cfg, skipped


def load_variables(
    path_or_config: Union[PathLike, Config],
    section: str = "variables",
    codec: Optional[Codec] = None,
    target: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if isinstance(path_or_config, Config):
        cfg = path_or_config
    else:
        cfg = Config(path_or_config, codec=codec)

    if codec is not None:
        cfg.codec = codec

    result: Dict[str, Any] = {}

    for key, value in cfg.data.get(section, {}).items():
        result[key] = cfg.codec.decode(value)

    if target is not None:
        target.update(result)

    return result