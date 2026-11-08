"""Phase 12: dataset explorer and duplicate-overlap safeguards.

The failure these tests prevent is a plausible-looking one: counting OSD-320 and OSD-46
as two studies and reporting a "replication" that compared a deposit against itself.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import explorer
from app.main import app

RELATIONS = {explorer.INDEPENDENT, explorer.DUPLICATE, explorer.SHARED_ASSAY,
             explorer.UNVERIFIED}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def overlaps(client):
    return client.get("/api/explorer/overlaps").json()


def test_relation_vocabulary_is_closed_and_every_class_is_explained(overlaps):
    assert set(overlaps["relationMeaning"]) == RELATIONS
    for name, meaning in overlaps["relationMeaning"].items():
        assert len(meaning) > 40, f"{name} needs a plain-language meaning"
    for relation in overlaps["relations"]:
        assert relation["relation"] in RELATIONS
        assert relation["relation"] != explorer.INDEPENDENT


def test_osd_320_is_never_presented_as_an_independent_study(client, overlaps):
    relation = client.post("/api/explorer/independent-set",
                           json={"ids": ["OSD-320", "OSD-46"]}).json()
    assert relation["independentCount"] == 1
    dropped = {row["id"]: row for row in relation["dropped"]}
    assert dropped["OSD-320"]["relation"] == explorer.DUPLICATE
    assert dropped["OSD-320"]["conflictsWith"] == "OSD-46"

    redundant = overlaps["redundantDeposits"]["OSD-320"]
    assert redundant["redundantWith"] == "OSD-46"
    # The claim must cite the numeric proof rather than assert equality by name.
    assert "22,810" in redundant["reason"] and "1.000000" in redundant["reason"]


def test_osd_320_detail_flags_redundancy_and_links_the_duplicate(client):
    detail = client.get("/api/explorer/datasets/OSD-320").json()
    assert detail["countsAsIndependentStudy"] is False
    assert detail["redundantWith"] == "OSD-46"
    duplicate = next(row for row in detail["relations"]
                     if row["relation"] == explorer.DUPLICATE)
    assert duplicate["sharedSamples"] == 44
    assert duplicate["fractionOfSmaller"] == 1.0
    assert duplicate["localReference"].endswith("#overlaps")


def test_independent_study_count_is_below_the_accession_count(overlaps):
    assert overlaps["accessionCount"] > overlaps["independentStudyCount"]
    assert overlaps["relationCounts"][explorer.DUPLICATE] == 1


def test_shared_material_is_reported_as_shared_not_as_a_duplicate(client):
    relation = explorer.relation_between("OSD-655", "OSD-780")
    assert relation["relation"] == explorer.SHARED_ASSAY
    assert relation["sharedSamples"] and relation["sharedSamples"] > 0
    assert relation["countsAsIndependent"] is False

    reduced = client.post("/api/explorer/independent-set",
                          json={"ids": ["OSD-655", "OSD-780"]}).json()
    assert reduced["independentCount"] == 1
    assert reduced["dropped"][0]["relation"] == explorer.SHARED_ASSAY


def test_an_unaudited_accession_is_unverified_not_independent():
    relation = explorer.relation_between("OSD-895", "OSD-46")
    assert relation["relation"] == explorer.UNVERIFIED
    assert relation["countsAsIndependent"] is False
    assert relation["sharedSamples"] is None


def test_shared_identifiers_without_a_numeric_check_stay_unverified():
    """OSD-267/OSD-269 share nine sample names; Phase 11 never proved equivalence."""
    relation = explorer.relation_between("OSD-267", "OSD-269")
    assert relation["relation"] == explorer.UNVERIFIED
    assert relation["auditClassification"] == "shared-sample-needs-numeric-check"
    assert relation["sharedSamples"] == 9
    assert relation["countsAsIndependent"] is False


def test_a_dataset_compared_with_itself_is_one_study():
    relation = explorer.relation_between("OSD-46", "OSD-46")
    assert relation["relation"] == explorer.DUPLICATE
    assert relation["countsAsIndependent"] is False


def test_audited_pairs_with_no_shared_identifiers_are_independent():
    relation = explorer.relation_between("OSD-46", "OSD-655")
    assert relation["relation"] == explorer.INDEPENDENT
    assert relation["countsAsIndependent"] is True
    assert relation["conflicts"] is False


def test_independent_set_keeps_order_and_shrinks_the_request(client):
    response = client.post("/api/explorer/independent-set",
                           json={"ids": ["OSD-46", "OSD-320", "OSD-267", "OSD-269",
                                         "OSD-655", "OSD-780"]})
    body = response.json()
    assert body["requested"] == 6
    assert body["independent"] == ["OSD-46", "OSD-267", "OSD-655"]
    assert body["independentCount"] == 3
    assert all(row["reason"] for row in body["dropped"])


def test_independent_set_ignores_unknown_ids_without_silently_counting_them(client):
    body = client.post("/api/explorer/independent-set",
                       json={"ids": ["OSD-46", "OSD-9999"]}).json()
    assert body["independent"] == ["OSD-46"]
    assert body["unknown"] == ["OSD-9999"]
    assert body["independentCount"] == 1


def test_independent_set_rejects_malformed_bodies(client):
    assert client.post("/api/explorer/independent-set",
                       json={"ids": "OSD-46"}).status_code == 422
    assert client.post("/api/explorer/independent-set",
                       json={"ids": ["OSD-46"], "extra": 1}).status_code == 422


def test_explorer_dataset_list_exposes_redundancy_per_row(client):
    rows = client.get("/api/explorer/datasets").json()["datasets"]
    by_id = {row["id"]: row for row in rows}
    assert by_id["OSD-320"]["countsAsIndependentStudy"] is False
    assert by_id["OSD-46"]["countsAsIndependentStudy"] is True
    assert by_id["OSD-46"]["uniqueSampleCount"] == 44
    assert by_id["OSD-320"]["identifierAudited"] is True


def test_explorer_search_is_case_insensitive_and_bounded(client):
    rows = client.get("/api/explorer/datasets?q=ARABIDOPSIS").json()["datasets"]
    assert rows and all("arabidopsis" in (row["title"] or "").lower()
                        or any("arabidopsis" in organism.lower()
                               for organism in row["organisms"])
                        for row in rows)


def test_explorer_rejects_an_unknown_dataset(client):
    assert client.get("/api/explorer/datasets/OSD-0000").status_code == 404


def test_manifest_dataset_endpoint_carries_the_safeguard_fields(client):
    rows = client.get("/api/datasets").json()["datasets"]
    assert rows
    for row in rows:
        assert isinstance(row["countsAsIndependentStudy"], bool)
        assert "redundantWith" in row


def test_models_that_use_a_redundant_deposit_are_reported(client):
    body = client.get("/api/explorer/overlaps").json()
    usage = body["redundantDepositUse"]["OSD-320"]
    assert usage["reachableThrough"] == "OSD-46"
    # No served model may claim to be trained on the redundant deposit itself.
    assert "OSD-320" not in usage["usedByModels"]
