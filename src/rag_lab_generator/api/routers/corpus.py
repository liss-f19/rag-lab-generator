"""
Role:   Corpus endpoints: browse courses, one lab and its attachments.
Input:  HTTP requests; the corpus tree under settings.raw_dir.
Output: CoursesResponse, LabDetailResponse and raw file responses.
Flow:   Each route reads Settings from app.state, delegates the filesystem work to api.corpus,
        returns 404 when the lab or file is absent and serves attachments only after the
        resolved path has been proven to stay inside the lab folder.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from rag_lab_generator.api import corpus
from rag_lab_generator.api.schemas import CoursesResponse, LabDetailResponse
from rag_lab_generator.config import Settings

router = APIRouter(prefix="/api", tags=["corpus"])

INLINE_TYPES = ("application/pdf", "image/", "text/")


def settings_of(request: Request) -> Settings:
    state: Settings = request.app.state.settings
    return state


@router.get("/courses", response_model=CoursesResponse)
def list_courses(request: Request) -> CoursesResponse:
    """Every course folder of data/raw with its labs."""
    settings = settings_of(request)
    courses = corpus.list_courses(settings)
    return CoursesResponse(
        data_dir=str(settings.data_dir),
        corpus_present=bool(courses),
        courses=courses,
    )


@router.get("/labs/{course}/{slug}", response_model=LabDetailResponse)
def get_lab(course: str, slug: str, request: Request) -> LabDetailResponse:
    """Full lab.xml content plus summary.md, manifest.json and the attachment listing."""
    detail = corpus.load_lab(settings_of(request), course, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"no lab {course}/{slug} under data/raw")
    return detail


@router.get("/labs/{course}/{slug}/files/{path:path}")
def get_lab_file(course: str, slug: str, path: str, request: Request) -> FileResponse:
    """Serve one file of src/, slides/ or extra/; pdfs and text render inline."""
    resolved = corpus.resolve_file(settings_of(request), course, slug, path)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"no file {path!r} in {course}/{slug}")
    media = corpus.media_type(resolved)
    disposition = "inline" if media.startswith(INLINE_TYPES) else "attachment"
    return FileResponse(
        resolved,
        media_type=media,
        filename=resolved.name,
        content_disposition_type=disposition,
    )
