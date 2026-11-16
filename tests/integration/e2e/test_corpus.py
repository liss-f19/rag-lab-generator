"""
Role:   QA data-quality gate over the ingested corpus under data/raw and data/external.
Input:  data/raw/<course>/<lab>/{lab.xml,manifest.json,summary.md,summary.pdf,src/,slides/,extra/},
        docs/lab.xsd, data/external/kozlowski, ingestion/mapping.yaml.
Output: pytest assertions naming the offending lab and file.
Flow:   Enumerates the twelve expected labs, validates each lab.xml against the XSD, parses every
        manifest.json as LabManifest, checks summaries are non-empty, resolves every ref attribute
        to a file on disk, forbids leftover hugo shortcodes and checks the Kozlowski sidecars.
        Pdfs, the lab slides/ copies and data/external are not versioned, so on a git checkout
        (CI) the checks that need them are skipped or restricted to the text files.
"""

import json
from pathlib import Path

import pytest
import yaml
from lxml import etree

from rag_lab_generator.models import LabManifest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
XSD_PATH = REPO_ROOT / "docs" / "lab.xsd"
MAPPING_PATH = REPO_ROOT / "src" / "rag_lab_generator" / "ingestion" / "mapping.yaml"
KOZLOWSKI_DIR = REPO_ROOT / "data" / "external" / "kozlowski"

EXPECTED_LABS: list[tuple[str, str]] = [
    ("sop1", "l0_posix_environment"),
    ("sop1", "l1_filesystem"),
    ("sop1", "l2_processes_signals"),
    ("sop1", "l3_threads_mutexes_signals"),
    ("sop1", "l4_synchronization"),
    ("sop1", "sanitizers"),
    ("sop2", "l5_fifo_pipe"),
    ("sop2", "l5_5_posix_queues"),
    ("sop2", "l6_shm_mmap"),
    ("sop2", "l7_sockets_epoll"),
    ("sop2", "l8_datagram_servers"),
    ("sop2", "netcat"),
]
LAB_IDS = [f"{course}/{slug}" for course, slug in EXPECTED_LABS]
# A full local ingest has data/external; a git checkout has only the text of data/raw.
FULL_INGEST = KOZLOWSKI_DIR.is_dir()
UNVERSIONED_SUFFIXES = {".pdf"}
# Reference pages without example tasks (their "tasks" are tutorial sections) ...
LABS_WITHOUT_TASKS = {"sop1/l0_posix_environment", "sop1/sanitizers", "sop2/netcat"}
# ... and without downloadable sources: no src/ files, no refs, no provenance entries.
LABS_WITHOUT_SOURCES = {"sop1/sanitizers", "sop2/netcat"}


def _lab_dir(course: str, slug: str) -> Path:
    return RAW_DIR / course / slug


@pytest.fixture(scope="module")
def schema() -> etree.XMLSchema:
    if not XSD_PATH.exists():
        pytest.fail(f"missing XML schema {XSD_PATH}")
    return etree.XMLSchema(etree.parse(str(XSD_PATH)))


def _parse(path: Path) -> etree._ElementTree:
    return etree.parse(str(path))


def test_raw_corpus_exists() -> None:
    assert RAW_DIR.is_dir(), f"{RAW_DIR} missing: run `rag-lab ingest` first"


def test_exactly_twelve_labs_present() -> None:
    found = sorted(
        f"{p.parent.name}/{p.name}" for p in RAW_DIR.glob("*/*") if (p / "lab.xml").exists()
    )
    assert found == sorted(LAB_IDS), (
        f"lab set mismatch\nmissing: {sorted(set(LAB_IDS) - set(found))}\n"
        f"unexpected: {sorted(set(found) - set(LAB_IDS))}"
    )


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_lab_files_present_and_non_empty(course: str, slug: str) -> None:
    lab = _lab_dir(course, slug)
    names = ("lab.xml", "manifest.json", "summary.md") + (("summary.pdf",) if FULL_INGEST else ())
    for name in names:
        path = lab / name
        assert path.is_file(), f"{path} missing"
        assert path.stat().st_size > 0, f"{path} is empty"


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_lab_xml_validates_against_xsd(course: str, slug: str, schema: etree.XMLSchema) -> None:
    path = _lab_dir(course, slug) / "lab.xml"
    tree = _parse(path)
    if not schema.validate(tree):
        errors = "\n".join(f"  line {e.line}: {e.message}" for e in schema.error_log)
        pytest.fail(f"{path} does not validate against {XSD_PATH}:\n{errors}")


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_manifest_parses_as_lab_manifest(course: str, slug: str) -> None:
    path = _lab_dir(course, slug) / "manifest.json"
    manifest = LabManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert manifest.slug == slug, f"{path}: slug {manifest.slug!r} != folder {slug!r}"
    assert manifest.course.value == course, f"{path}: course {manifest.course} != {course}"
    if f"{course}/{slug}" not in LABS_WITHOUT_SOURCES:
        assert manifest.sources, f"{path}: no source provenance recorded"


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_no_leftover_hugo_shortcodes(course: str, slug: str) -> None:
    """Shortcodes must be expanded at ingestion; `{{<` in the XML means a parser gap."""
    path = _lab_dir(course, slug) / "lab.xml"
    text = path.read_text(encoding="utf-8")
    offenders = [
        f"{path}:{n}: {line.strip()[:120]}"
        for n, line in enumerate(text.splitlines(), start=1)
        if "{{<" in line or "{{%" in line
    ]
    assert not offenders, "unexpanded hugo shortcodes:\n" + "\n".join(offenders)


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_every_ref_points_at_an_existing_file(course: str, slug: str) -> None:
    """Every code/solution ref must resolve inside the lab folder (normally under src/)."""
    lab = _lab_dir(course, slug)
    tree = _parse(lab / "lab.xml")
    missing: list[str] = []
    seen = 0
    for element in tree.iter():
        ref = element.get("ref")
        if not ref:
            continue
        seen += 1
        if not (lab / ref).is_file():
            missing.append(f"{lab / 'lab.xml'}:{element.sourceline}: <{element.tag} ref={ref!r}>")
    assert not missing, "dangling refs:\n" + "\n".join(missing)
    if f"{course}/{slug}" not in LABS_WITHOUT_SOURCES:
        assert seen > 0, f"{lab}/lab.xml declares no code or solution refs at all"


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_lab_has_sections_and_tasks(course: str, slug: str) -> None:
    tree = _parse(_lab_dir(course, slug) / "lab.xml")
    sections = tree.findall(".//section")
    tasks = tree.findall(".//task")
    assert sections, f"{course}/{slug}: lab.xml has no <section>"
    if f"{course}/{slug}" not in LABS_WITHOUT_TASKS:
        assert tasks, f"{course}/{slug}: lab.xml has no <task>"
    for section in sections:
        assert "".join(section.itertext()).strip(), (
            f"{course}/{slug}: empty <section id={section.get('id')!r}>"
        )


def test_sop1_l1_covers_the_directory_api() -> None:
    """The canonical retrieval target of the e2e query must actually carry the API names."""
    tree = _parse(_lab_dir("sop1", "l1_filesystem") / "lab.xml")
    text = "".join(tree.getroot().itertext()).lower()
    for api in ("opendir", "readdir", "closedir"):
        assert api in text, f"sop1/l1_filesystem lab.xml does not mention {api}"
    stages = tree.findall(".//task//stage")
    assert stages, "sop1/l1_filesystem: no <stage> under any <task>"


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_src_directory_is_populated(course: str, slug: str) -> None:
    src = _lab_dir(course, slug) / "src"
    if f"{course}/{slug}" in LABS_WITHOUT_SOURCES:
        return  # an empty src/ is not versioned by git
    assert src.is_dir(), f"{src} missing"
    files = [p for p in src.rglob("*") if p.is_file()]
    assert files, f"{src} holds no source files"


def _mapping() -> dict[str, object]:
    if not MAPPING_PATH.exists():
        pytest.skip(f"{MAPPING_PATH} missing")
    loaded = yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


@pytest.mark.parametrize(("course", "slug"), EXPECTED_LABS, ids=LAB_IDS)
def test_slides_and_extra_match_the_manifest(course: str, slug: str) -> None:
    """A lab that claims slides/extra in its manifest must have the files on disk."""
    lab = _lab_dir(course, slug)
    manifest = LabManifest.model_validate(json.loads((lab / "manifest.json").read_text("utf-8")))
    for folder, declared in (("slides", manifest.slides), ("extra", manifest.extra)):
        if not FULL_INGEST:
            # slides/ is not versioned at all; extra/ is versioned without its pdfs
            if folder == "slides":
                continue
            declared = [n for n in declared if Path(n).suffix.lower() not in UNVERSIONED_SUFFIXES]
        if not declared:
            continue
        directory = lab / folder
        assert directory.is_dir(), f"{directory} missing although manifest lists {declared}"
        on_disk = {p.name for p in directory.rglob("*") if p.is_file()}
        assert on_disk, f"{directory} is empty although manifest lists {declared}"
        for name in declared:
            assert Path(name).name in on_disk, f"{directory}: manifest lists missing {name!r}"


def test_mapping_covers_every_lab() -> None:
    """mapping.yaml is keyed by lab_id (sop1/l0), not by folder slug (l0_posix_environment)."""
    labs = _mapping().get("labs")
    assert isinstance(labs, dict) and labs, f"{MAPPING_PATH} has no 'labs' mapping"
    declared = set(labs)
    on_disk = {
        LabManifest.model_validate(
            json.loads((_lab_dir(course, slug) / "manifest.json").read_text("utf-8"))
        ).lab_id
        for course, slug in EXPECTED_LABS
    }
    assert on_disk <= declared, f"{MAPPING_PATH} does not map {sorted(on_disk - declared)}"
    assert declared <= on_disk, f"{MAPPING_PATH} maps unknown labs {sorted(declared - on_disk)}"


def test_kozlowski_pdfs_have_text_sidecars() -> None:
    if not FULL_INGEST:
        pytest.skip(f"{KOZLOWSKI_DIR} is not versioned; run `rag-lab ingest` for this check")
    pdfs = sorted(KOZLOWSKI_DIR.rglob("*.pdf"))
    assert pdfs, f"no pdfs under {KOZLOWSKI_DIR}"
    missing = [str(p) for p in pdfs if not p.with_suffix(".txt").is_file()]
    assert not missing, "pdfs without a .txt sidecar:\n" + "\n".join(missing)
    empty = [
        str(p.with_suffix(".txt"))
        for p in pdfs
        if p.with_suffix(".txt").is_file() and p.with_suffix(".txt").stat().st_size < 200
    ]
    assert not empty, "suspiciously small text sidecars:\n" + "\n".join(empty)
