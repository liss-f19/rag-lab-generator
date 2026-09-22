"""
Role:   Shared pytest fixtures for every test package (settings and in-memory documents).
Input:  pytest tmp_path.
Output: A Settings instance pointing at a temporary data dir and a small document corpus.
Flow:   `settings` builds Settings with the fake embedder and temporary directories;
        `sample_documents` builds one LabDocument with nested sections, tasks and code files plus
        a lecture and a course-info Document; `sample_lab` exposes the lab alone.
"""

from pathlib import Path

import pytest

from rag_lab_generator.config import Settings
from rag_lab_generator.models import (
    CodeFile,
    Course,
    Document,
    DocumentKind,
    LabDocument,
    Section,
    Stage,
    Task,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings isolated from the real corpus: temporary dirs and the deterministic embedder."""
    return Settings(
        data_dir=tmp_path / "data",
        results_dir=tmp_path / "results",
        embedding_provider="fake",
        embedding_dim=64,
        embedding_batch_size=4,
    )


@pytest.fixture
def sample_lab() -> LabDocument:
    return LabDocument(
        id="sop1/lab/l1_filesystem",
        course=Course.SOP1,
        kind=DocumentKind.LAB,
        title="Lab 1: Filesystem API",
        number="1",
        slug="l1_filesystem",
        lab_id="sop1/lab/l1_filesystem",
        source_url="https://sop.mini.pw.edu.pl/sop1/l1",
        topics=["opendir", "readdir", "stat"],
        sections=[
            Section(
                id="introduction",
                title="Introduction",
                level=2,
                order=0,
                text="This lab introduces the POSIX filesystem API and error handling.",
            ),
            Section(
                id="browsing-a-directory",
                title="Browsing a directory",
                level=2,
                order=1,
                text=(
                    "Directories are read with opendir and readdir.\n\n"
                    "Each call to readdir returns the next directory entry.\n\n"
                    "```c\nDIR* dirp = opendir(path);\nstruct dirent* dp;\n```\n\n"
                    "Remember to call closedir when the iteration is finished."
                ),
                code_refs=["src/prog1.c"],
            ),
            Section(
                id="reading-entry-metadata",
                title="Reading entry metadata",
                level=3,
                order=2,
                parent_id="browsing-a-directory",
                text="Call lstat on every entry to read its metadata without following links.",
            ),
            Section(
                id="error-handling",
                title="Error handling",
                level=2,
                order=3,
                text="Check errno after every failing call and report it with perror.",
            ),
        ],
        tasks=[
            Task(
                id="example1",
                title="Directory scanner",
                statement="Write a program that counts the entries of a directory by type.",
                stages=[
                    Stage(n=1, text="Open the directory given as the first argument."),
                    Stage(n=2, text="Iterate over the entries with readdir and classify them."),
                    Stage(n=3, text="Print the counters and close the directory."),
                ],
                solution_refs=["src/prog1.c"],
            ),
            Task(
                id="example2",
                title="Recursive walker",
                statement="Extend the scanner so that it descends into subdirectories.",
                stages=[
                    Stage(n=1, text="Use nftw or an explicit stack to walk the tree."),
                    Stage(n=2, text="Aggregate the counters over the whole subtree."),
                ],
                notes="Do not follow symbolic links.",
            ),
        ],
        code_files=[
            CodeFile(
                ref="src/prog1.c",
                lang="c",
                content=(
                    "#include <dirent.h>\n"
                    "int main(void) {\n"
                    '    DIR* d = opendir(".");\n'
                    "    return d ? 0 : 1;\n"
                    "}\n"
                ),
            ),
            CodeFile(
                ref="src/Makefile",
                lang="make",
                content="all: prog1\nprog1: prog1.c\n\t$(CC) -o prog1 prog1.c\n",
            ),
        ],
    )


@pytest.fixture
def sample_documents(sample_lab: LabDocument) -> list[Document]:
    """A lab, a lecture and a course-info document, all in memory."""
    lecture = Document(
        id="sop1/lecture/w2/filesystem",
        course=Course.SOP1,
        kind=DocumentKind.LECTURE_PDF,
        title="Lecture 2: Filesystems",
        sections=[
            Section(
                id="inodes",
                title="Inodes",
                level=2,
                order=0,
                text="An inode stores the metadata of a file: mode, owner, size and blocks.",
            ),
            Section(
                id="directories",
                title="Directories",
                level=2,
                order=1,
                text="A directory maps names to inode numbers; hard links share one inode.",
            ),
        ],
    )
    info = Document(
        id="sop1/info/rules",
        course=Course.SOP1,
        kind=DocumentKind.COURSE_INFO,
        title="SOP1 course rules",
        sections=[
            Section(
                id="grading",
                title="Grading",
                level=2,
                order=0,
                text="Each laboratory is graded from 0 to 10 points; three absences are allowed.",
            )
        ],
    )
    return [sample_lab, lecture, info]
