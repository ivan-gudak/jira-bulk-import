import re

from jira_markup_converter import JiraMarkupConverter


def make_converter():
    return JiraMarkupConverter(jira_base_url="https://example.atlassian.net")


def test_bracketed_id_marker_is_not_link_wrapped():
    conv = make_converter()
    out = conv.convert("### [US-1]: View OneAgent configuration state")
    assert out == "### [US-1]: View OneAgent configuration state"
    assert "[US-1](" not in out


def test_bare_issue_key_is_still_linkified():
    conv = make_converter()
    out = conv.convert("See PRODUCT-18503 for details")
    assert out == "See [PRODUCT-18503](https://example.atlassian.net/browse/PRODUCT-18503) for details"


def test_bare_browse_url_is_not_corrupted():
    conv = make_converter()
    out = conv.convert("See https://dt-rnd.atlassian.net/browse/MGD-8605 for details")
    assert out == "See https://dt-rnd.atlassian.net/browse/MGD-8605 for details"
    assert "[MGD-8605](" not in out


def test_bare_browse_url_with_trailing_punctuation():
    conv = make_converter()
    out = conv.convert("Ref https://dt-rnd.atlassian.net/browse/MGD-8605.")
    assert out == "Ref https://dt-rnd.atlassian.net/browse/MGD-8605."


HASH_IDS = "[US#1] [AC#1] [SM#1] [SMC#1] [UC#3] [FR#2] [AD#1]"


def test_hash_form_ids_pass_through_untouched():
    conv = make_converter()
    assert conv.convert(HASH_IDS) == HASH_IDS


def test_hash_form_id_in_heading_survives():
    conv = make_converter()
    assert conv.convert("h3. [US#1]: Export the thing") == "### [US#1]: Export the thing"


def test_hash_form_id_in_table_cell_survives():
    conv = make_converter()
    out = conv.convert("||h1||h2||\n|[AC#1]|[US#2]|\n")
    assert "[AC#1]" in out and "[US#2]" in out
    assert "[AC#1](" not in out


def test_unbracketed_hash_id_is_not_linkified():
    conv = make_converter()
    assert conv.convert("Bare AC#2 outside brackets") == "Bare AC#2 outside brackets"


def test_real_key_still_linkifies_alongside_hash_ids():
    conv = make_converter()
    out = conv.convert("[AC#1] traces PRODUCT-456")
    assert out == "[AC#1] traces [PRODUCT-456](https://example.atlassian.net/browse/PRODUCT-456)"


def _hostile_jira(md):
    """Model Jira's paste: linkify every issue key, ignoring markdown brackets."""
    return re.sub(r"\b([A-Z]{2,10}-\d+)\b", r"[\1|smart-link]", md)


def test_hash_ids_never_accumulate_brackets_over_rounds():
    """The historical bug: markdown -> Jira -> markdown grew brackets each round.

    A single-pass test cannot see it. Five rounds under a hostile Jira model can.
    """
    conv = make_converter()
    text = "- [AC#1] and [US#2] and [AD#3]\n"
    for _ in range(5):
        text = conv.convert(_hostile_jira(text))
    assert text.count("[") == 3
    assert text.count("]") == 3
    for token in ("[AC#1]", "[US#2]", "[AD#3]"):
        assert token in text
