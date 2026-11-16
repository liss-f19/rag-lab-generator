"""End-to-end trace through the running HTTP API.

Uploads the course corpus from dataset/, waits for the ingestion jobs, runs
retrieval queries, and reports latencies, job timings, and the evidence found.
It only talks to the public API, so it works against a local server or the
Docker Compose stack alike.

    uv run python scripts/e2e_trace.py --base-url http://localhost:8000 \\
        --token "$TOKEN" --output trace.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_QUERIES = [
    "How do I create a named pipe with mkfifo and read from it?",
    "How can threads protect a shared counter with a mutex?",
    "How does a UDP server receive datagrams with recvfrom?",
]
TOPIC_LINE = re.compile(r"^\*Topic:\s*(?P<topic>.+?)\s*\*\s*$", re.MULTILINE)


def document_type(name: str) -> str:
    if "_Tutorial_" in name:
        return "tutorial"
    if "_Sample_Task_" in name:
        return "sample_task"
    if name.startswith("Test_Task"):
        return "test_task"
    return "lab_task"


def metadata_for(path: Path, course_id: str) -> dict[str, Any]:
    match = TOPIC_LINE.search(path.read_text(encoding="utf-8"))
    return {
        "course_id": course_id,
        "knowledge_base": "primary",
        "document_type": document_type(path.name),
        "topic": match.group("topic")[:256] if match else None,
        "version": "2026",
        "authority_level": "course",
    }


def wait_for_job(client: httpx.Client, url: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        job = client.get(url).raise_for_status().json()
        if job["status"] in ("succeeded", "failed"):
            return job
        if time.monotonic() > deadline:
            raise TimeoutError(f"Job {url} still {job['status']} after {timeout} s")
        time.sleep(0.2)


def seconds_between(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def upload_corpus(
    client: httpx.Client, files: list[Path], course_id: str, timeout: float
) -> list[dict[str, Any]]:
    uploads = []
    for path in files:
        started = time.perf_counter()
        response = client.post(
            "/api/v1/documents",
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
            data={"metadata": json.dumps(metadata_for(path, course_id))},
        )
        latency_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        uploads.append({"file": path.name, "upload_ms": latency_ms, **response.json()})

    records = []
    for upload in uploads:
        job = wait_for_job(client, upload["status_url"], timeout)
        result = job["result"] or {}
        records.append(
            {
                "file": upload["file"],
                "document_id": upload["document_id"],
                "upload_ms": round(upload["upload_ms"], 2),
                "status": job["status"],
                "error": job["error"],
                "queue_wait_s": seconds_between(job["created_at"], job["started_at"]),
                "processing_s": seconds_between(job["started_at"], job["completed_at"]),
                "chunk_count": result.get("chunk_count", 0),
                "embedding_model": result.get("embedding_model"),
                "timings_ms": result.get("timings_ms", {}),
            }
        )
    return records


def run_queries(
    client: httpx.Client, course_id: str, queries: list[str], timeout: float
) -> list[dict[str, Any]]:
    results = []
    for query in queries:
        started = time.perf_counter()
        accepted = client.post(
            f"/api/v1/courses/{course_id}/retrieval",
            json={"query": query, "top_k": 3, "purpose": "context"},
        ).raise_for_status()
        job = wait_for_job(client, accepted.json()["status_url"], timeout)
        round_trip_ms = (time.perf_counter() - started) * 1000
        result = job["result"] or {}
        results.append(
            {
                "query": query,
                "status": job["status"],
                "round_trip_ms": round(round_trip_ms, 2),
                "retrieval_ms": result.get("latency_ms"),
                "evidence": [
                    {
                        "file": item["filename"],
                        "section": " > ".join(item["section_path"]),
                        "similarity": item["similarity"],
                    }
                    for item in result.get("evidence", [])
                ],
            }
        )
    return results


def summarise(documents: list[dict[str, Any]]) -> dict[str, Any]:
    succeeded = [item for item in documents if item["status"] == "succeeded"]
    uploads = [item["upload_ms"] for item in documents]
    processing = [item["processing_s"] for item in succeeded if item["processing_s"]]
    return {
        "documents": len(documents),
        "indexed": len(succeeded),
        "failed": [item["file"] for item in documents if item["status"] != "succeeded"],
        "chunks": sum(item["chunk_count"] for item in succeeded),
        "upload_ms_median": round(statistics.median(uploads), 2),
        "upload_ms_p95": round(percentile(uploads, 0.95), 2),
        "processing_s_median": round(statistics.median(processing), 3)
        if processing
        else None,
        "processing_s_total": round(sum(processing), 3),
        "embedding_model": succeeded[0]["embedding_model"] if succeeded else None,
    }


def print_report(trace: dict[str, Any], focus: str) -> None:
    summary = trace["summary"]
    print(f"API {trace['base_url']}  version {trace['health']['version']}")
    print(f"health: {trace['health']['checks']}")
    print(
        f"corpus: {summary['indexed']}/{summary['documents']} documents indexed, "
        f"{summary['chunks']} fragments, embeddings {summary['embedding_model']}"
    )
    print(
        f"upload (202 Accepted): median {summary['upload_ms_median']} ms, "
        f"p95 {summary['upload_ms_p95']} ms"
    )
    print(
        f"ingestion job: median {summary['processing_s_median']} s per document, "
        f"total {summary['processing_s_total']} s"
    )
    for item in trace["documents"]:
        if item["file"] == focus:
            print(f"traced document {focus}: {json.dumps(item, indent=2)}")
    for query in trace["queries"]:
        print(
            f"query: {query['query']} -> {query['status']} in {query['round_trip_ms']} ms "
            f"(retrieval {query['retrieval_ms']} ms)"
        )
        for rank, evidence in enumerate(query["evidence"], start=1):
            print(
                f"  {rank}. {evidence['file']} | {evidence['section']} | "
                f"similarity {evidence['similarity']:.3f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.environ.get("E2E_TOKEN"))
    parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    parser.add_argument("--course-id", default="operating-systems")
    parser.add_argument("--focus", default="L5_Tutorial_FIFO_Pipe.md")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.token:
        parser.error("a bearer token is required (--token or E2E_TOKEN)")

    files = sorted(args.dataset.glob("*.md"))
    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60) as client:
        health = client.get("/api/v1/health").raise_for_status().json()
        documents = upload_corpus(client, files, args.course_id, args.timeout)
        queries = run_queries(client, args.course_id, DEFAULT_QUERIES, args.timeout)

    trace = {
        "base_url": args.base_url,
        "health": health,
        "summary": summarise(documents),
        "documents": documents,
        "queries": queries,
    }
    print_report(trace, args.focus)
    if args.output:
        args.output.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return 0 if not trace["summary"]["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
