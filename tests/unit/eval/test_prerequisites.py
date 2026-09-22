"""
Role:   Unit tests for the eval prerequisites check that decides which configs can run.
Input:  Hand-built Prerequisites and EvalConfigSpec objects; no database.
Output: Assertions; no side effects.
Flow:   Checks that a remote embedder sharing another embedder's vector space (bge_m3_hf ->
        bge_m3) is accepted when only bge_m3 vectors exist, and that an unknown name is kept as is.
"""

from rag_lab_generator.eval.runner import EvalConfigSpec, Prerequisites, vector_space


def _spec(embedder: str) -> EvalConfigSpec:
    return EvalConfigSpec(
        rag="vector", searcher="dense", chunker="hierarchical", embedder=embedder, k=8
    )


def test_vector_space_maps_the_remote_bge_m3_onto_the_local_one() -> None:
    assert vector_space("bge_m3_hf") == "bge_m3"
    assert vector_space("bge_m3") == "bge_m3"
    assert vector_space("no_such_embedder") == "no_such_embedder"


def test_remote_embedder_config_runs_on_local_vectors() -> None:
    prerequisites = Prerequisites(chunks={"hierarchical": 10}, vectors={"bge_m3/hierarchical": 10})
    assert prerequisites.missing(_spec("bge_m3_hf")) is None
    assert prerequisites.missing(_spec("bge_m3")) is None
    assert prerequisites.missing(_spec("fake")) == "no fake embeddings for strategy hierarchical"
