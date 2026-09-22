"""
Role:   Unit tests of the source strategies that need no network.
Input:  A captured Apache listing snippet and a temporary fake clone.
Output: Assertions on the listing parser, the file filters and the registry wiring.
Flow:   Parses a listing, checks the per-directory filters, and lists the files of a minimal
        clone layout built in tmp_path.
"""

from pathlib import Path

from rag_lab_generator.config import Settings
from rag_lab_generator.ingestion.sources.kozlowski import KozlowskiSource
from rag_lab_generator.ingestion.sources.sop_site import SopSiteSource
from rag_lab_generator.registry import available, get

LISTING = """
<table>
<tr><td><a href="/~kozlowskim/">Parent Directory</a></td></tr>
<tr><td><a href="00-basics.pdf">00-basics.pdf</a></td></tr>
<tr><td><a href="bash1.sh">bash1.sh</a></td></tr>
<tr><td><a href="tutorial.gcc_make.txt">tutorial.gcc_make.txt</a></td></tr>
<tr><td><a href="lecture_4.pdf">lecture_4.pdf</a></td></tr>
<tr><td><a href="lab_9.pdf">lab_9.pdf</a></td></tr>
<tr><td><a href="eiatia568.jpg">eiatia568.jpg</a></td></tr>
<tr><td><a href="cisco/">cisco/</a></td></tr>
</table>
"""


def test_both_sources_are_registered() -> None:
    assert {"sop_site", "kozlowski"} <= set(available("source"))
    assert get("source", "sop_site") is SopSiteSource


def test_listing_parser_skips_the_parent_link_and_subdirectories() -> None:
    names = KozlowskiSource.parse_listing(LISTING)
    assert "00-basics.pdf" in names
    assert not any(name.endswith("/") for name in names)


def test_unix_and_tcpip_filters_keep_different_files() -> None:
    unix = KozlowskiSource.wanted_names("unix", LISTING)
    tcpip = KozlowskiSource.wanted_names("tcpip", LISTING)
    assert unix == [
        "00-basics.pdf",
        "bash1.sh",
        "lab_9.pdf",
        "lecture_4.pdf",
        "tutorial.gcc_make.txt",
    ]
    assert tcpip == ["lab_9.pdf", "lecture_4.pdf"]
    assert "eiatia568.jpg" not in unix


def test_sop_site_lists_only_english_pages_and_code(tmp_path: Path) -> None:
    content = tmp_path / "content" / "sop1" / "lab" / "l1"
    content.mkdir(parents=True)
    (content / "_index.en.md").write_text("en", encoding="utf-8")
    (content / "_index.pl.md").write_text("pl", encoding="utf-8")
    (content / "prog12.c").write_text("int main(void);", encoding="utf-8")
    (tmp_path / "static" / "files").mkdir(parents=True)
    (tmp_path / "static" / "files" / "a.zip").write_bytes(b"PK")
    (tmp_path / "regulamin-sop1-en.md").write_text("rules", encoding="utf-8")

    refs = SopSiteSource(Settings(data_dir=tmp_path)).list_files(tmp_path)
    names = sorted(Path(ref.local_path).name for ref in refs)
    assert names == ["_index.en.md", "a.zip", "prog12.c", "regulamin-sop1-en.md"]
    assert all(ref.sha256 for ref in refs)
