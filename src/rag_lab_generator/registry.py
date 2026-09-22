"""
Role:   Strategy registry: maps (kind, name) to the implementation class of a swappable component.
Input:  Classes decorated with @register(kind, name) at import time.
Output: create(kind, name, **kwargs) instances; available(kind) names.
Flow:   Decorators fill a two-level dict; load_all() imports every strategy package so their
        decorators run; create() looks up the class and instantiates it with the given kwargs.
"""

import importlib
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T", bound=type)

KINDS: tuple[str, ...] = ("source", "chunker", "embedder", "searcher", "rag", "llm")

# Packages whose __init__ imports every implementation module of that kind.
_STRATEGY_PACKAGES: tuple[str, ...] = (
    "rag_lab_generator.ingestion.sources",
    "rag_lab_generator.ingestion.chunking",
    "rag_lab_generator.retrieval.embeddings",
    "rag_lab_generator.retrieval.searchers",
    "rag_lab_generator.retrieval.rag",
    "rag_lab_generator.generation.llm",
)

_REGISTRY: dict[str, dict[str, type]] = defaultdict(dict)
_LOADED_PACKAGES: set[str] = set()


class UnknownStrategyError(LookupError):
    pass


def register(kind: str, name: str) -> Callable[[T], T]:
    if kind not in KINDS:
        raise ValueError(f"unknown strategy kind {kind!r}; allowed: {KINDS}")

    def decorator(cls: T) -> T:
        existing = _REGISTRY[kind].get(name)
        if existing is not None and existing is not cls:
            raise ValueError(f"{kind}:{name} already registered by {existing.__qualname__}")
        _REGISTRY[kind][name] = cls
        return cls

    return decorator


def load_all() -> None:
    for package in _STRATEGY_PACKAGES:
        if package not in _LOADED_PACKAGES:
            importlib.import_module(package)
            _LOADED_PACKAGES.add(package)


def get(kind: str, name: str) -> type:
    load_all()
    try:
        return _REGISTRY[kind][name]
    except KeyError as exc:
        raise UnknownStrategyError(
            f"no {kind} named {name!r}; available: {available(kind)}"
        ) from exc


def create(kind: str, name: str, **kwargs: Any) -> Any:
    return get(kind, name)(**kwargs)


def available(kind: str) -> list[str]:
    load_all()
    return sorted(_REGISTRY[kind])
