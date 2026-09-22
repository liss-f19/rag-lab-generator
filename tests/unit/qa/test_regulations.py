"""
Role:   QA gate that enforces the CLAUDE.md code regulations mechanically over the whole package.
Input:  Every .py file under src/rag_lab_generator and the strategy registry after load_all().
Output: pytest assertions; failures name the offending file and line.
Flow:   Collects source files once, parses each with ast to read its module docstring, checks the
        four required docstring fields, forbids os.environ outside config.py, forbids strategy-name
        dispatch outside registry.py, and asserts registry.available() lists the expected names.
"""

import ast
import re
from pathlib import Path

import pytest

from rag_lab_generator import registry

SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "rag_lab_generator"
REQUIRED_FIELDS = ("Role:", "Input:", "Output:", "Flow:")

EXPECTED_STRATEGIES: dict[str, set[str]] = {
    "chunker": {"fixed", "hierarchical", "semantic"},
    "embedder": {"bge_m3", "fake"},
    "searcher": {"lexical", "dense", "hybrid_rrf", "graph_walk"},
    "rag": {"vector", "graph"},
    "llm": {"fake", "anthropic"},
    "source": {"sop_site", "kozlowski"},
}

ALL_STRATEGY_NAMES: set[str] = {n for names in EXPECTED_STRATEGIES.values() for n in names}


def _source_files() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


SOURCE_FILES = _source_files()


def test_source_tree_is_not_empty() -> None:
    assert SOURCE_FILES, f"no python sources found under {SRC_ROOT}"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: str(p.relative_to(SRC_ROOT)))
def test_module_docstring_has_required_fields(path: Path) -> None:
    """Regulation 1: every module opens with a Role/Input/Output/Flow docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    doc = ast.get_docstring(tree, clean=False)
    assert doc is not None, f"{path}:1 has no module docstring"
    missing = [field for field in REQUIRED_FIELDS if field not in doc]
    assert not missing, f"{path}:1 module docstring misses {missing}"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: str(p.relative_to(SRC_ROOT)))
def test_no_os_environ_outside_config(path: Path) -> None:
    """Regulation 7: configuration is read only by config.py."""
    if path.name == "config.py":
        pytest.skip("config.py is the single allowed reader of the environment")
    hits = [
        f"{path}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"\bos\.(environ|getenv)\b|\bgetenv\(", line)
    ]
    assert not hits, "environment read outside config.py:\n" + "\n".join(hits)


# Matches `if <something>name == "fixed"` and `elif strategy == "vector"`-style dispatch.
_DISPATCH_RE = re.compile(
    r"\b(?:el)?if\s+[\w.\[\]\"']*\b"
    r"(?:name|strategy|chunker|embedder|searcher|rag|llm|source|provider|kind)\b"
    r"[\w.\[\]\"']*\s*(?:==|in)\s*",
)


def _dispatch_hits(path: Path) -> list[str]:
    hits: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not _DISPATCH_RE.search(line):
            continue
        quoted = set(re.findall(r"[\"']([A-Za-z0-9_]+)[\"']", line))
        if quoted & ALL_STRATEGY_NAMES:
            hits.append(f"{path}:{n}: {line.strip()}")
    return hits


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: str(p.relative_to(SRC_ROOT)))
def test_no_strategy_name_dispatch_outside_registry(path: Path) -> None:
    """Regulation 4: selection happens only through registry.create()."""
    if path.name == "registry.py":
        pytest.skip("registry.py owns strategy dispatch")
    hits = _dispatch_hits(path)
    assert not hits, "strategy-name dispatch outside registry.py:\n" + "\n".join(hits)


@pytest.mark.parametrize(("kind", "expected"), sorted(EXPECTED_STRATEGIES.items()))
def test_registry_exposes_expected_strategies(kind: str, expected: set[str]) -> None:
    """Regulation 4: every @register-ed class is reachable after load_all()."""
    registry.load_all()
    got = set(registry.available(kind))
    assert expected <= got, f"{kind}: missing {sorted(expected - got)} (registered: {sorted(got)})"


def test_registry_kinds_cover_expected_kinds() -> None:
    assert set(EXPECTED_STRATEGIES) <= set(registry.KINDS)


def test_unknown_strategy_error_lists_available_names() -> None:
    """A typo must produce an actionable message, not a bare KeyError."""
    with pytest.raises(registry.UnknownStrategyError) as excinfo:
        registry.get("chunker", "definitely-not-a-chunker")
    message = str(excinfo.value)
    assert "definitely-not-a-chunker" in message
    for name in EXPECTED_STRATEGIES["chunker"]:
        assert name in message, f"available names missing {name!r} in: {message}"
