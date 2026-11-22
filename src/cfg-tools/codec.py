from __future__ import annotations

import base64
import datetime as dt
import importlib
import pickle
import types
from enum import Enum
from pathlib import Path, PurePath
from typing import Any, Callable, Dict, Optional, Tuple


BYTES = "@cfg/bytes"
BYTEARRAY = "@cfg/bytearray"
TUPLE = "@cfg/tuple"
SET = "@cfg/set"
FROZENSET = "@cfg/frozenset"
DICT_PAIRS = "@cfg/dict_pairs"
CLASS = "@cfg/class"
FUNCTION = "@cfg/function"
MODULE = "@cfg/module"
INSTANCE = "@cfg/instance"
PICKLE = "@cfg/pickle"
DATETIME = "@cfg/datetime"
DATE = "@cfg/date"
TIME = "@cfg/time"
TIMEDELTA = "@cfg/timedelta"
PATH = "@cfg/path"
ENUM = "@cfg/enum"


class CycleError(Exception):
    pass


def _qualname(obj: Any) -> Optional[str]:
    module = getattr(obj, "__module__", None)
    name = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", None)

    if module and name:
        return f"{module}.{name}"

    if name:
        return name

    return None


def _resolve_path(path: str) -> Any:
    if not isinstance(path, str) or not path:
        raise ImportError("Пустой путь к объекту")

    parts = path.split(".")
    last_error: Optional[Exception] = None

    for i in range(len(parts), 0, -1):
        module_name = ".".join(parts[:i])

        if not module_name:
            continue

        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
            continue

        obj = module

        try:
            for part in parts[i:]:
                obj = getattr(obj, part)

            return obj

        except AttributeError as exc:
            last_error = exc
            continue

    raise ImportError(f"Не удалось импортировать: {path}") from last_error


class Codec:
    def __init__(self, allow_pickle: bool = True):
        self.allow_pickle = allow_pickle
        self._encoders: Dict[type, Tuple[str, Callable[[Any], Any]]] = {}
        self._decoders: Dict[str, Callable[[Any], Any]] = {}

    def register(
        self,
        cls: type,
        encoder: Optional[Callable[[Any], Any]] = None,
        decoder: Optional[Callable[[Any], Any]] = None,
        tag: Optional[str] = None,
    ) -> type:
        tag = tag or _qualname(cls) or getattr(cls, "__name__", "Unknown")

        if encoder is not None:
            self._encoders[cls] = (tag, encoder)

        if decoder is not None:
            self._decoders[tag] = decoder

        return cls

    def _can_resolve(self, path: Optional[str]) -> bool:
        if not path:
            return False

        try:
            _resolve_path(path)
            return True
        except Exception:
            return False

    def _find_encoder(self, obj: Any) -> Optional[Tuple[str, Callable[[Any], Any]]]:
        for klass in type(obj).__mro__:
            if klass in self._encoders:
                return self._encoders[klass]

        return None

    def encode(self, obj: Any) -> Any:
        try:
            return self._encode(obj, active=set())
        except CycleError:
            return self._pickle_encode(obj)
        except (TypeError, ValueError, AttributeError, pickle.PicklingError, ImportError):
            return self._pickle_encode(obj)

    def _pickle_encode(self, obj: Any) -> Dict[str, str]:
        if not self.allow_pickle:
            raise TypeError("Сериализация через pickle запрещена")

        data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        return {PICKLE: base64.b64encode(data).decode("ascii")}

    def _pickle_decode(self, data: str) -> Any:
        if not self.allow_pickle:
            raise TypeError("Десериализация через pickle запрещена")

        return pickle.loads(base64.b64decode(data.encode("ascii")))

    def _encode(self, obj: Any, active: set) -> Any:
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        custom = self._find_encoder(obj)

        if custom is not None and not isinstance(obj, type):
            tag, encoder = custom
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                state = encoder(obj)
                return {INSTANCE: tag, "state": self._encode(state, active)}
            finally:
                active.remove(oid)

        if isinstance(obj, bytes):
            return {BYTES: base64.b64encode(obj).decode("ascii")}

        if isinstance(obj, bytearray):
            return {BYTEARRAY: base64.b64encode(bytes(obj)).decode("ascii")}

        if isinstance(obj, dt.datetime):
            return {DATETIME: obj.isoformat()}

        if isinstance(obj, dt.date):
            return {DATE: obj.isoformat()}

        if isinstance(obj, dt.time):
            return {TIME: obj.isoformat()}

        if isinstance(obj, dt.timedelta):
            return {TIMEDELTA: obj.total_seconds()}

        if isinstance(obj, PurePath):
            return {PATH: str(obj)}

        if isinstance(obj, Enum):
            cls_path = _qualname(type(obj))

            if self._can_resolve(cls_path):
                return {ENUM: [cls_path, obj.name]}

            return self._pickle_encode(obj)

        if type(obj) is list:
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                return [self._encode(item, active) for item in obj]
            finally:
                active.remove(oid)

        if type(obj) is tuple:
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                return {TUPLE: [self._encode(item, active) for item in obj]}
            finally:
                active.remove(oid)

        if type(obj) is set:
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                return {SET: [self._encode(item, active) for item in obj]}
            finally:
                active.remove(oid)

        if type(obj) is frozenset:
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                return {FROZENSET: [self._encode(item, active) for item in obj]}
            finally:
                active.remove(oid)

        if type(obj) is dict:
            oid = id(obj)

            if oid in active:
                raise CycleError

            active.add(oid)

            try:
                if all(isinstance(key, str) for key in obj.keys()):
                    return {
                        key: self._encode(value, active)
                        for key, value in obj.items()
                    }

                return {
                    DICT_PAIRS: [
                        [self._encode(key, active), self._encode(value, active)]
                        for key, value in obj.items()
                    ]
                }
            finally:
                active.remove(oid)

        if isinstance(obj, type):
            path = _qualname(obj)

            if self._can_resolve(path):
                return {CLASS: path}

            return self._pickle_encode(obj)

        if isinstance(obj, (types.FunctionType, types.BuiltinFunctionType)):
            path = _qualname(obj)

            if self._can_resolve(path):
                return {FUNCTION: path}

            return self._pickle_encode(obj)

        if isinstance(obj, types.ModuleType):
            name = getattr(obj, "__name__", None)

            if name:
                return {MODULE: name}

            return self._pickle_encode(obj)

        oid = id(obj)

        if oid in active:
            raise CycleError

        active.add(oid)

        try:
            cls_path = _qualname(type(obj))

            if not self._can_resolve(cls_path):
                return self._pickle_encode(obj)

            state = self._get_state(obj)

            return {
                INSTANCE: cls_path,
                "state": self._encode(state, active),
            }

        except CycleError:
            raise

        except Exception:
            return self._pickle_encode(obj)

        finally:
            active.remove(oid)

    def _get_state(self, obj: Any) -> Any:
        getstate = getattr(type(obj), "__getstate__", None)
        object_getstate = getattr(object, "__getstate__", None)

        if getstate is not None and getstate is not object_getstate:
            return obj.__getstate__()

        state: Dict[str, Any] = {}

        if hasattr(obj, "__dict__"):
            state.update(obj.__dict__)

        for slot in self._all_slots(type(obj)):
            if hasattr(obj, slot):
                state[slot] = getattr(obj, slot)

        return state

    def _all_slots(self, cls: type) -> list[str]:
        result = []

        for klass in cls.__mro__:
            slots = getattr(klass, "__slots__", [])

            if isinstance(slots, str):
                slots = [slots]

            for slot in slots:
                if slot in ("__dict__", "__weakref__"):
                    continue

                if slot not in result:
                    result.append(slot)

        return result

    def decode(self, data: Any) -> Any:
        return self._decode(data)

    def _decode(self, data: Any) -> Any:
        if isinstance(data, list):
            return [self._decode(item) for item in data]

        if not isinstance(data, dict):
            return data

        if len(data) == 1:
            if BYTES in data:
                return base64.b64decode(data[BYTES])

            if BYTEARRAY in data:
                return bytearray(base64.b64decode(data[BYTEARRAY]))

            if TUPLE in data:
                return tuple(self._decode(item) for item in data[TUPLE])

            if SET in data:
                return set(self._decode(item) for item in data[SET])

            if FROZENSET in data:
                return frozenset(self._decode(item) for item in data[FROZENSET])

            if DICT_PAIRS in data:
                return {
                    self._decode(key): self._decode(value)
                    for key, value in data[DICT_PAIRS]
                }

            if CLASS in data:
                return _resolve_path(data[CLASS])

            if FUNCTION in data:
                return _resolve_path(data[FUNCTION])

            if MODULE in data:
                return importlib.import_module(data[MODULE])

            if PICKLE in data:
                return self._pickle_decode(data[PICKLE])

            if DATETIME in data:
                return dt.datetime.fromisoformat(data[DATETIME])

            if DATE in data:
                return dt.date.fromisoformat(data[DATE])

            if TIME in data:
                return dt.time.fromisoformat(data[TIME])

            if TIMEDELTA in data:
                return dt.timedelta(seconds=float(data[TIMEDELTA]))

            if PATH in data:
                return Path(data[PATH])

            if ENUM in data:
                cls_path, member_name = data[ENUM]
                cls = _resolve_path(cls_path)
                return cls[member_name]

        if INSTANCE in data and "state" in data and len(data) == 2:
            tag = data[INSTANCE]
            state = self._decode(data["state"])

            if tag in self._decoders:
                return self._decoders[tag](state)

            cls = _resolve_path(tag)
            return self._restore_instance(cls, state)

        return {key: self._decode(value) for key, value in data.items()}

    def _restore_instance(self, cls: type, state: Any) -> Any:
        try:
            obj = cls.__new__(cls)
        except TypeError:
            obj = object.__new__(cls)

        if hasattr(obj, "__setstate__"):
            obj.__setstate__(state)
            return obj

        if isinstance(state, dict):
            for key, value in state.items():
                try:
                    setattr(obj, key, value)
                except AttributeError:
                    if hasattr(obj, "__dict__"):
                        obj.__dict__[key] = value
                    else:
                        raise

        return obj


default_codec = Codec()


def register_class(
    cls: Optional[type] = None,
    *,
    encoder: Optional[Callable[[Any], Any]] = None,
    decoder: Optional[Callable[[Any], Any]] = None,
    tag: Optional[str] = None,
):
    def wrapper(klass: type) -> type:
        return default_codec.register(
            klass,
            encoder=encoder,
            decoder=decoder,
            tag=tag,
        )

    if cls is None:
        return wrapper

    return wrapper(cls)