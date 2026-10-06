"""Search (task P1-27): `simple` full text plus trigram title match."""

import shutil
from pathlib import Path

import pytest

from vault import indexer

GOLDEN = Path(__file__).resolve().parents[3] / "second-brain/fixtures/golden-vault"
SEARCH = "/api/search/"

pytestmark = pytest.mark.django_db

TICKET = "---\ntype: lesson\nid: 20260201000001\nstatus: active\ncreated: 2026-02-01\n---\n"


@pytest.fixture
def vault(isolated_vault):
    shutil.copytree(GOLDEN / "vault", isolated_vault, dirs_exist_ok=True)
    (isolated_vault / "05-Knowledge/Lessons/Ticket lesson.md").write_text(
        TICKET + "Fixed in LOADUP-123 by renaming get_user_by_id for the running lanterns.\n"
    )
    indexer.sync(isolated_vault)
    return isolated_vault


@pytest.fixture
def api(client, django_user_model):
    client.force_login(django_user_model.objects.create_user(username="tester", password="x"))
    return client


def search(api, q):
    response = api.get(SEARCH, {"q": q})
    assert response.status_code == 200
    assert response.json()["query"] == q.strip()
    return response.json()["results"]


def found(results, path):
    return path in [result["path"] for result in results]


def test_search_requires_a_session(client):
    assert client.get(SEARCH, {"q": "x"}).status_code == 403


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}])
def test_missing_or_blank_q_is_400(api, params):
    assert api.get(SEARCH, params).status_code == 400


def test_ticket_key_is_found(api, vault):
    assert found(search(api, "LOADUP-123"), "05-Knowledge/Lessons/Ticket lesson.md")
    assert found(search(api, "loadup-123"), "05-Knowledge/Lessons/Ticket lesson.md")


def test_identifier_is_found_whole(api, vault):
    assert found(search(api, "get_user_by_id"), "05-Knowledge/Lessons/Ticket lesson.md")


def test_path_fragments_are_found(api, vault):
    results = search(api, "Work/Projects")
    assert found(results, "02-Work/Projects/Night Owl.md")
    assert found(search(api, "Decisions"), "05-Knowledge/Decisions/Use warm white bulbs.md")


def test_no_stemming_a_stemmed_form_does_not_match_the_body(api, vault):
    # The body says "lanterns"; "lantern" is a different token under `simple`, and the
    # lesson's title does not resemble it enough for the trigram match.
    assert found(search(api, "lanterns"), "05-Knowledge/Lessons/Ticket lesson.md")
    assert not found(search(api, "lantern running"), "05-Knowledge/Lessons/Ticket lesson.md")
    assert not found(search(api, "renamed"), "05-Knowledge/Lessons/Ticket lesson.md")
    assert found(search(api, "renaming"), "05-Knowledge/Lessons/Ticket lesson.md")


def test_title_typo_is_found_by_trigram(api, vault):
    results = search(api, "Lantren Festival")
    assert found(results, "05-Knowledge/Decisions/Lantern Festival.md")


def test_results_have_the_contract_fields(api, vault):
    results = search(api, "festival")
    assert results
    for result in results:
        assert set(result) == {"path", "type", "title", "project", "snippet", "source"}
        assert result["source"] == "vault"
        assert "<b>" not in result["snippet"] and "</b>" not in result["snippet"]
        assert len(result["snippet"]) <= 200
    lesson = next(r for r in results if r["path"].endswith("Festival lighting lesson.md"))
    assert lesson["type"] == "lesson"
    assert lesson["project"] == "lantern-festival"
    assert lesson["title"] == "Festival lighting lesson"


def test_snippet_shows_text_around_the_match(api, vault):
    result = next(
        r for r in search(api, "get_user_by_id") if r["path"].endswith("Ticket lesson.md")
    )
    assert "get_user_by_id" in result["snippet"]


def test_results_are_capped_at_fifty_and_ties_ordered_by_path(api, vault):
    for number in range(60):
        (vault / f"00-Inbox/Zebrafish {number:02d}.md").write_text("zebrafish\n")
    indexer.sync(vault)
    results = search(api, "zebrafish")
    assert len(results) == 50
    assert [r["path"] for r in results] == sorted(r["path"] for r in results)


def test_no_match_returns_an_empty_list(api, vault):
    assert search(api, "qqzzxxnomatch") == []


def test_search_is_bounded_in_queries(api, vault, django_assert_max_num_queries):
    with django_assert_max_num_queries(3):
        assert api.get(SEARCH, {"q": "festival"}).status_code == 200


def add_notes(vault, notes):
    for name, text in notes.items():
        (vault / name).write_text(text)
    indexer.sync(vault)


def test_slash_in_a_body_term_is_found(api, vault):
    add_notes(vault, {"00-Inbox/Protocols.md": "Notes on TCP/IP framing.\n"})
    assert found(search(api, "TCP/IP"), "00-Inbox/Protocols.md")
    assert found(search(api, "TCP IP"), "00-Inbox/Protocols.md")


def test_body_path_fragments_are_found(api, vault):
    add_notes(
        vault,
        {"00-Inbox/Where.md": "The indexer lives in web-app/backend/vault/indexer.py today.\n"},
    )
    assert found(search(api, "vault/indexer.py"), "00-Inbox/Where.md")
    assert found(search(api, "indexer.py"), "00-Inbox/Where.md")


def test_a_one_mebibyte_body_is_searched_within_the_query_bound(
    api, vault, django_assert_max_num_queries
):
    big = "alpha beta gamma delta " * 46_000  # about 1 MiB
    assert len(big) > 1_000_000
    add_notes(vault, {"00-Inbox/Huge.md": big + " needle\n"})
    with django_assert_max_num_queries(3):
        response = api.get(SEARCH, {"q": "alpha"})
    assert response.status_code == 200
    result = next(r for r in response.json()["results"] if r["path"] == "00-Inbox/Huge.md")
    assert len(result["snippet"]) <= 200


def test_rank_orders_before_title_similarity(api, vault):
    # A: title is trigram-close to the query but never matches the vector (rank 0).
    # B: the body matches the vector, the title is unlike the query, and its path sorts later.
    add_notes(
        vault,
        {
            "00-Inbox/Zephyrin.md": "",
            "00-Inbox/Zz plain.md": "zephyrine zephyrine\n",
        },
    )
    paths = [r["path"] for r in search(api, "zephyrine")]
    assert paths.index("00-Inbox/Zz plain.md") < paths.index("00-Inbox/Zephyrin.md")
