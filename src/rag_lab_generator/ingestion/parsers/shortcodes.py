"""
Role:   Hugo shortcode expander used by every markdown parser of the ingestion layer.
Input:  Raw markdown of one hugo page, the page directory (for includecode/resource/github_url)
        and the page URL path (for relative ref resolution).
Output: ShortcodeResult with the expanded markdown plus the file and link references it found.
Flow:   Splits the text into fenced and unfenced segments so code blocks stay untouched, expands
        paired shortcodes (hint, answer, details, katex) into plain markdown, then resolves the
        single shortcodes (includecode, resource, github_url, codeattachments, ref) and finally
        strips any shortcode that is still left over, recording it as unresolved.
"""

import re
from pathlib import Path

from pydantic import BaseModel, Field

SITE_BASE_URL = "https://sop.mini.pw.edu.pl"
REPO_TREE_URL = "https://github.com/SOP-MINI/sop-site/tree/master"

FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>```+|~~~+)", re.M)
SHORTCODE_RE = re.compile(r"\{\{[<%]\s*(/?)\s*([A-Za-z_][\w-]*)((?:\s[^>%]*?)?)\s*[>%]\}\}")
ARG_RE = re.compile(r"\"([^\"]*)\"|'([^']*)'|(\S+)")

LANG_BY_SUFFIX: dict[str, str] = {
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".py": "python",
    ".sh": "bash",
    ".txt": "text",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".zip": "zip",
    ".pdf": "pdf",
}


def lang_of(name: str) -> str:
    """Map a file name to the fenced-block language label used across the corpus."""
    stem = Path(name)
    if stem.suffix == "" and stem.name.lower().startswith("makefile"):
        return "make"
    if stem.suffix == "" and stem.name.lower().startswith("dockerfile"):
        return "docker"
    return LANG_BY_SUFFIX.get(stem.suffix.lower(), "text")


class ShortcodeResult(BaseModel):
    """Everything one expansion pass produced for a single page."""

    text: str
    code_refs: list[str] = Field(default_factory=list, description="files inlined by includecode")
    resources: list[str] = Field(default_factory=list, description="files named by resource")
    links: list[tuple[str, str]] = Field(default_factory=list, description="(url, title) from ref")
    answers: list[str] = Field(default_factory=list, description="answer / details inner text")
    unresolved: list[str] = Field(default_factory=list, description="shortcode names left over")


def _parse_args(raw: str) -> list[str]:
    return [a or b or c for a, b, c in ARG_RE.findall(raw.strip())]


def split_fences(text: str) -> list[tuple[bool, str]]:
    """Split markdown into (is_code, chunk) parts so fenced blocks can be skipped."""
    parts: list[tuple[bool, str]] = []
    pos = 0
    while True:
        opening = FENCE_RE.search(text, pos)
        if opening is None:
            parts.append((False, text[pos:]))
            return parts
        parts.append((False, text[pos : opening.start()]))
        marker = opening.group("fence")[0] * 3
        closing = re.compile(rf"^[ \t]*{re.escape(marker)}+[ \t]*$", re.M)
        end = closing.search(text, opening.end())
        if end is None:
            parts.append((True, text[opening.start() :]))
            return parts
        parts.append((True, text[opening.start() : end.end()]))
        pos = end.end()


def mask_fences(text: str) -> str:
    """Blank out fenced code blocks while keeping every character offset of the original text."""
    return "".join(
        re.sub(r"[^\n]", " ", chunk) if is_code else chunk for is_code, chunk in split_fences(text)
    )


def _resolve_ref(target: str, page_url_path: str) -> str:
    """Turn a hugo ref target into an absolute site URL."""
    clean = target.strip().strip('"').split("#")[0]
    clean = re.sub(r"\.(en|pl)\.md$|\.md$", "", clean)
    if clean.startswith(("http://", "https://")):
        return clean
    if clean.startswith("/"):
        path = clean.strip("/")
    else:
        path = f"{page_url_path.strip('/')}/{clean.strip('/')}".strip("/")
    return f"{SITE_BASE_URL}/en/{path}/"


def _render_paired(name: str, args: list[str], inner: str, result: ShortcodeResult) -> str:
    if name == "katex":
        return f"${inner.strip()}$"
    if name == "hint":
        body = "\n".join(f"> {line}" if line.strip() else ">" for line in inner.strip().split("\n"))
        return f"\n{body}\n"
    label = "Answer" if name == "answer" else (args[0] if args else "Details")
    result.answers.append(inner.strip())
    return f"\n**{label}:** {inner.strip()}\n"


PAIRED_RE = re.compile(
    r"\{\{[<%]\s*(katex|details|answer|hint)((?:\s[^>%]*?)?)\s*[>%]\}\}"
    r"(.*?)"
    r"\{\{[<%]\s*/\s*\1\s*[>%]\}\}",
    re.S,
)


def _expand_paired(text: str, result: ShortcodeResult) -> str:
    """Replace hint/answer/details/katex wrappers by plain markdown, in document order."""
    previous = None
    while previous != text:
        previous = text
        text = PAIRED_RE.sub(
            lambda m: _render_paired(m.group(1), _parse_args(m.group(2)), m.group(3), result),
            text,
        )
    return text


def _expand_single(
    text: str, base_dir: Path | None, page_dir: str, page_url_path: str, result: ShortcodeResult
) -> str:
    def replace(match: re.Match[str]) -> str:
        closing, name, raw_args = match.group(1), match.group(2), match.group(3)
        args = _parse_args(raw_args)
        if closing:
            result.unresolved.append(f"/{name}")
            return ""
        if name == "includecode" and args:
            target = args[0]
            result.code_refs.append(target)
            body = ""
            if base_dir is not None and (base_dir / target).is_file():
                body = (base_dir / target).read_text(encoding="utf-8", errors="replace")
            else:
                result.unresolved.append(f"includecode {target}")
            return f"\n```{lang_of(target)}\n{body.rstrip()}\n```\n"
        if name == "resource" and args:
            result.resources.append(args[0])
            return args[0]
        if name == "ref" and args:
            url = _resolve_ref(args[0], page_url_path)
            result.links.append((url, ""))
            return url
        if name == "github_url":
            suffix = f"/{args[0]}" if args else ""
            return f"{REPO_TREE_URL}/{page_dir.strip('/')}{suffix}"
        if name == "codeattachments":
            if base_dir is None:
                return ""
            names = sorted(p.name for p in base_dir.iterdir() if p.suffix in {".h", ".c"})
            result.resources.extend(names)
            return "\n" + "\n".join(f"- [{n}]({n})" for n in names) + "\n"
        result.unresolved.append(name)
        return ""

    return SHORTCODE_RE.sub(replace, text)


def expand_shortcodes(
    text: str,
    base_dir: Path | None = None,
    page_dir: str = "",
    page_url_path: str = "",
) -> ShortcodeResult:
    """Expand every hugo shortcode of one page, leaving fenced code blocks untouched."""
    result = ShortcodeResult(text="")
    pieces: list[str] = []
    for is_code, chunk in split_fences(text.replace("{{</", "{{< /").replace("{{%/", "{{% /")):
        if is_code:
            pieces.append(chunk)
            continue
        expanded = _expand_paired(chunk, result)
        pieces.append(_expand_single(expanded, base_dir, page_dir, page_url_path, result))
    result.text = "".join(pieces)
    return result
