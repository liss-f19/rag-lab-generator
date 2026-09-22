# Corpus

How `data/` is produced, what it contains and which heuristics were used. Everything here is
rebuilt by `uv run rag-lab ingest` and read back by
`rag_lab_generator.ingestion.pipeline.load_documents()`.

## Sources

| source | strategy | what is taken |
| --- | --- | --- |
| `github.com/SOP-MINI/sop-site` (hugo sources of sop.mini.pw.edu.pl) | `sop_site` | English pages (`*.en.md`), C/shell/python sources, lecture PDFs, `static/files/*.zip` |
| `pages.mini.pw.edu.pl/~kozlowskim/unix/` | `kozlowski` | every `.pdf`, `.sh`, `.txt` |
| `pages.mini.pw.edu.pl/~kozlowskim/tcpip/` | `kozlowski` | `lecture_N.pdf` and `lab_N.pdf` |

The site repository stores its PDFs and ZIPs with **git-lfs**. A plain `git clone --depth 1`
therefore yields 130-byte pointer files. `SopSiteSource.resolve_lfs()` detects them and fetches
the real content from `media.githubusercontent.com`, so no `git-lfs` binary is needed.

Every `.pl.md` page is ignored: the corpus language is English.

## Layout of `data/`

```
data/external/sop-site/                 shallow clone, reused unless --force
data/external/kozlowski/{unix,tcpip}/   downloaded files
data/raw/<course>/_course/              syllabus.md zasady.md materialy.md harmonogram.md
                                        project.md index.md regulamin.md  (shortcodes expanded)
data/raw/<course>/_lectures/<topic>/    index.md, slides.md, code/*, *.pdf + <name>.txt sidecar
data/raw/<course>/_extra/               course-wide background material + .txt sidecars
data/raw/<course>/<lab_slug>/
    lab.xml        validated against docs/lab.xsd
    src/           every code file and zip attachment of the lab; the text sources of a zip
                   (.c/.h/Makefile, binaries skipped) are unpacked into src/<zip-stem>/
    slides/        lecture files mapped to this lab, named <course>_<topic>__<file>
    extra/         Kozlowski files mapped to this lab, each pdf with a .txt sidecar
    summary.md     deterministic outline plus the llm answer
    summary.pdf    summary.md rendered with markdown -> xhtml2pdf
    manifest.json  LabManifest with the sha256 of every copied source
```

Lab slugs: `l0_posix_environment`, `l1_filesystem`, `l2_processes_signals`,
`l3_threads_mutexes_signals`, `l4_synchronization`, `sanitizers`, `l5_fifo_pipe`,
`l5_5_posix_queues`, `l6_shm_mmap`, `l7_sockets_epoll`, `l8_datagram_servers`, `netcat`.
Lab ids are `<course>/<hugo dir>`, e.g. `sop1/l1`, `sop2/l5_5`, `sop2/netcat`.

## Document ids produced by `load_documents()`

| kind | id | `lab_id` |
| --- | --- | --- |
| `lab` | `sop1/l1` | - |
| `summary` | `sop1/l1/summary` | `sop1/l1` |
| `lecture_index` | `sop1/lecture/w2/index` | - |
| `lecture_slides` | `sop2/lecture/shm/slides` | - |
| `lecture_pdf` | `sop1/lecture/w2/OPS1_Filesystem_API` | - |
| `lecture_code` | `sop2/lecture/shm/code/anon.c` | - |
| `course_info` | `sop1/course/syllabus` | - |
| `external_pdf` | `external/kozlowski/unix/07-processes` | the mapped lab, or `None` for `_extra/` |

An external file mapped to several labs yields one document per lab, the id carrying the suffix
`@<lab id>` (for example `external/kozlowski/tcpip/lecture_4@sop2/l8`). Ids are stable across runs.

Shell scripts (`bash1.sh` ... `bash4.sh`) also become documents: kind `external_pdf`, one fenced
section holding the whole script, `metadata["format"] = "sh"`.

### `metadata["support"]`

Every document carries `support`, so retrieval can weight the two bodies of material differently:

- `"primary"` - everything coming from the course site: labs, summaries, lectures, course info.
- `"background"` - every `external_pdf`, that is the whole Kozlowski UNIX and TCP/IP material.
  It is reference reading for students who are new to Unix, not course material of SOP1/SOP2.

## Heuristics

**Shortcodes** (`parsers/shortcodes.py`). `hint` keeps its inner text as a block quote,
`answer` and `details` become `**Answer:** ...` and are also collected separately (task `notes`),
`includecode` inlines the file as a fenced block and records the reference, `resource` resolves to
the plain file name, `ref` resolves to the public URL (relative targets against the page path),
`github_url` to the repository tree URL, `codeattachments` to the list of `.c`/`.h` files of the
page, `katex` to `$...$`. Anything else is dropped and recorded in `unresolved`. Nothing inside a
fenced code block is ever expanded.

**Section splitting** (`parsers/hugo_markdown.py`). Headings are found on a *length preserving*
mask of the body in which fenced blocks are blanked out, so a `#` line inside C or shell code
never starts a section. Ids are slugified headings, deduplicated with a `-2` suffix; `parent_id`
is the closest enclosing heading of a lower level. A body without headings yields one `overview`
section. Shortcodes are expanded per section, after the split, so `code_refs` are exact.

**Tasks.** The heading whose title matches *stages / graded stages / steps* separates the task:
everything before and after it becomes the `statement` (headings kept, so "Starting code" or
"Example output" are not lost), the list items under it become `stages`. `/files/*.zip` links
become `attachments` (`src/<name>`), `resource` references to `.c` files become `solution_refs`,
and the text of `answer`/`details` becomes `notes`. `sop2/lab/l8/example2/` is a directory page
and is parsed as the task `example2` of `sop2/l8`.

**Topics.** Candidates are the inline code spans of the prose plus `man N name` references, in
order of first appearance. A candidate is kept when it is an ALL_CAPS macro (`S_ISDIR`), or a
lowercase identifier `[a-z_][a-z0-9_]{2,}` that also appears followed by `(` somewhere in the
page's code (fenced blocks and inline spans). A stopword list removes C keywords and common
prose words. Tutorials written without any inline code span (SOP1 L4, `sanitizers`) would end up
with nothing, so when fewer than 8 topics are found the identifiers called inside the fenced code
blocks are appended; that also picks up local helper names such as `thread_func`.

**English PDF selection.** A lecture PDF referenced by the English index page is kept; one
referenced only by the Polish page is dropped; an unreferenced PDF is kept unless a sibling of the
same lecture carries an explicit `en` marker (this is what separates `Mem_1.pdf` from
`Mem_en_1.pdf` in `sop2/wyk/w11`).

**Lecture mapping** lives in `rag_lab_generator/ingestion/mapping.yaml` and is meant to be edited.
Its `labs:` section maps a lab id to `lectures` (`"<course>/<topic>"`, SOP1 lectures may support
SOP2 labs, e.g. pipes and message queues) and to `kozlowski` (`"<unix|tcpip>/<file>"`, copied into
the lab's `extra/`). Its `courses:` section maps a course to material that belongs to no single
lab; it is copied into `data/raw/<course>/_extra/` and loaded with `lab_id` unset.

Every one of the 26 files of `kozlowski/unix/` is mapped somewhere (a unit test enforces it):
the shell and command-line material to `sop1/l0`, users and files to `sop1/l1`, processes and the
system interface to `sop1/l2`, and the editor/awk reference (`09-vim`, `10-awk`, `awk-man-b5-1`)
course-wide to SOP1. The TCP/IP lectures were assigned from their title pages: 1 OSI Reference
Model, 3 IPv4 Addressing, 4 IP/TCP/UDP Packets, 5 TCP/IP Diagnostics Basics, 9 Application Layer
Protocols; the other TCP/IP lectures are downloaded but deliberately left out of the corpus.

A `.txt` sidecar is extracted next to **every** pdf under `data/external/kozlowski/`, including the
unmapped ones, so the raw text is always available for inspection.

## Known gaps

- `sop2/lab/netcat` and `sop1/lab/sanitizers` have no example tasks on the site, so their
  `<tasks>` element is empty; `sanitizers` has no headings either and yields one section.
- Task pages do not link their reference solution, so `solution_refs` is filled only where a
  `resource` shortcode points at a `.c` file (`sop2/l8/example2`).
- Images referenced by tasks (`/channel_schematic.png`) are not copied; the markdown link is kept.
- `sop2/wyk/servers/slides/` is empty upstream, so that lecture has no `slides.md`.
- Kozlowski material is in Polish (the TCP/IP lecture slides are in English); that is expected.
- TCP/IP lectures 2, 6, 7, 8, 10, 11, 12, 13 and every `tcpip/lab_N.pdf` are downloaded and have a
  `.txt` sidecar but are not mapped, so `load_documents()` does not emit them.
