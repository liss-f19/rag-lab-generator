"""
Role:   Groups the chunks attached to a graph node by document for the node details panel.
Input:  The node's chunks and the DocumentHeader of every document they belong to.
Output: list[NodeSource], labs first, each with one readable location per chunk.
Flow:   Buckets chunks by document_id, names every chunk after its breadcrumb, task title,
        lecture page or code ref, then orders the groups by document kind and title.
"""

from rag_lab_generator.models import (
    Chunk,
    ChunkKind,
    DocumentHeader,
    DocumentKind,
    NodeSource,
    NodeSourceLocation,
)

KIND_ORDER: dict[DocumentKind, int] = {
    DocumentKind.LAB: 0,
    DocumentKind.SUMMARY: 1,
    DocumentKind.LECTURE_SLIDES: 2,
    DocumentKind.LECTURE_PDF: 3,
    DocumentKind.LECTURE_INDEX: 4,
    DocumentKind.LECTURE_CODE: 5,
    DocumentKind.COURSE_INFO: 6,
    DocumentKind.EXTERNAL_PDF: 7,
}
FALLBACK_KIND: dict[ChunkKind, DocumentKind] = {
    ChunkKind.LECTURE: DocumentKind.LECTURE_PDF,
    ChunkKind.SUMMARY: DocumentKind.SUMMARY,
    ChunkKind.INFO: DocumentKind.COURSE_INFO,
}


def group_sources(chunks: list[Chunk], headers: dict[str, DocumentHeader]) -> list[NodeSource]:
    """Turn a flat chunk list into one NodeSource per document, labs first."""
    groups: dict[str, NodeSource] = {}
    for chunk in sorted(chunks, key=lambda c: (c.document_id, c.idx)):
        group = groups.get(chunk.document_id)
        if group is None:
            group = _new_group(chunk, headers.get(chunk.document_id))
            groups[chunk.document_id] = group
        group.locations.append(
            NodeSourceLocation(chunk_id=chunk.id, label=location_label(chunk), kind=chunk.kind)
        )
    return sorted(groups.values(), key=lambda g: (KIND_ORDER.get(g.kind, 9), g.title.lower()))


def _new_group(chunk: Chunk, header: DocumentHeader | None) -> NodeSource:
    slug = header.metadata.get("slug") if header is not None else None
    return NodeSource(
        document_id=chunk.document_id,
        title=header.title if header is not None else chunk.document_id,
        kind=header.kind if header is not None else FALLBACK_KIND.get(chunk.kind, DocumentKind.LAB),
        course=header.course if header is not None else chunk.course,
        lab_id=header.lab_id if header is not None else chunk.lab_id,
        slug=str(slug) if slug else None,
        locations=[],
    )


def location_label(chunk: Chunk) -> str:
    """Name a chunk the way a reader would look it up inside its document."""
    metadata = chunk.metadata
    if chunk.kind is ChunkKind.CODE and metadata.get("ref"):
        label = str(metadata["ref"])
    elif chunk.kind is ChunkKind.TASK and metadata.get("title"):
        label = f"Task: {metadata['title']}"
    elif chunk.section_id and chunk.section_id.startswith("page-"):
        label = chunk.section_id.replace("-", " ", 1)
    elif metadata.get("breadcrumb"):
        # "Document title > A > B" -> "A > B"
        parts = str(metadata["breadcrumb"]).split(" > ")
        label = " > ".join(parts[1:]) if len(parts) > 1 else parts[0]
    elif metadata.get("title"):
        label = str(metadata["title"])
    else:
        label = chunk.section_id or f"chunk {chunk.idx}"
    n_parts = int(metadata.get("n_parts") or 1)
    if n_parts > 1:
        label = f"{label} (part {int(metadata.get('part') or 0) + 1}/{n_parts})"
    return label
