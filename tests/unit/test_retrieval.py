import pytest

from app.domain.corpus import Authority, Source, SourceKind
from app.domain.retrieval import RefRouter, reciprocal_rank_fusion


def law(slug: str, prefix: str) -> Source:
    return Source(
        slug=slug,
        title=slug,
        authority=Authority.ACT,
        kind=SourceKind.LAW_XML,
        url=f"https://example.test/{slug}.xml",
        licence="test",
        ref_prefix=prefix,
        web_url=f"https://example.test/{slug}/",
    )


@pytest.fixture
def router() -> RefRouter:
    return RefRouter.from_sources([law("irpa", "A"), law("irpr", "R")])


@pytest.mark.parametrize(
    ("question", "refs"),
    [
        ("What does R205(c)(ii) cover?", ["R205(c)(ii)"]),
        ("Is A40(1) about misrepresentation?", ["A40(1)"]),
        ("explain r186(v).", ["R186(v)"]),
        ("How do A40.1 and R200(1)(b) interact, given R200(1)(b)?", ["A40.1", "R200(1)(b)"]),
        ("What does IRPR 205(c) say?", ["R205(c)"]),
        ("Under irpa s. 40(1)(a), what counts?", ["A40(1)(a)"]),
        ("IRPR section 216", ["R216"]),
        ("Keep the clause's case: R205(c)(i.2)(A)", ["R205(c)(i.2)(A)"]),
        (
            "Is a common-law partner defined in R1(1)#common-law-partner?",
            ["R1(1)#common-law-partner"],
        ),
        ("What is in RSch1.1 and ASch?", ["RSch1.1", "ASch"]),
    ],
)
def test_finds_the_refs_a_question_names(router, question, refs):
    assert router.refs(question) == refs


@pytest.mark.parametrize(
    "question",
    [
        "Can I work while studying?",
        "A 40 year old applicant with 3 years of experience",
        "I scored CLB 7 and my NOC is 21231",
        "Form IMM1294 and section 205",
        "My passport number is AR205",
    ],
)
def test_ignores_text_that_names_no_ref(router, question):
    assert router.refs(question) == []


def test_fusion_ranks_items_found_by_both_lists_first():
    assert reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]]) == ["a", "c", "b", "d"]


def test_fusion_keeps_first_seen_order_on_ties():
    assert reciprocal_rank_fusion([["a", "b"], ["c", "d"]]) == ["a", "c", "b", "d"]


def test_fusion_of_nothing_is_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_a_smaller_k_favours_the_top_of_each_list():
    rankings = [["top", "a", "b", "both"], ["c", "d", "e", "both"]]

    assert reciprocal_rank_fusion(rankings, k=60)[0] == "both"
    assert reciprocal_rank_fusion(rankings, k=1)[0] == "top"
