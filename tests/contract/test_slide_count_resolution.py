"""
_resolve_slide_count — ADR-074.

The composer has no dedicated slide-count control; its own placeholder
text ("e.g. Create a 10-slide investor pitch deck...") invites typing
a count directly into the topic prompt instead. Before this, that
number was silently ignored everywhere: the frontend always sent a
hardcoded slide_count=10 (frontend/lib/api-client.ts's
topicRequestBody), and nothing on the backend looked at the topic text
either — so a request for "a 20-slide deck" always produced exactly 10
slides. These are the fast, direct unit tests for the regex/precedence
logic itself; tests/integration/test_api_http.py covers the same fix
end-to-end through the real HTTP endpoints.
"""

from backend.api.main import _resolve_slide_count, MIN_SLIDE_COUNT, MAX_SLIDE_COUNT


def test_hyphenated_form_is_recognized():
    assert _resolve_slide_count("Create a 12-slide deck about coral reefs", 10) == 12


def test_spaced_plural_form_is_recognized():
    assert _resolve_slide_count("Make an 8 slides overview of Rome", 10) == 8


def test_spaced_singular_form_is_recognized():
    assert _resolve_slide_count("A 15 slide presentation on jazz history", 10) == 15


def test_case_insensitive():
    assert _resolve_slide_count("A 9-SLIDE deck about bees", 10) == 9


def test_no_mention_falls_back_to_the_requested_value():
    assert _resolve_slide_count("The history of the printing press", 10) == 10
    assert _resolve_slide_count("The history of the printing press", 5) == 5


def test_topic_mention_takes_precedence_over_a_different_requested_value():
    """The exact reported bug: the client sends the frontend's
    hardcoded default (10) while the topic text asks for something
    else — the text must win, not the field."""
    assert _resolve_slide_count("Build a 20-slide investor deck", 10) == 20


def test_mentioned_count_is_still_clamped_to_the_normal_bounds():
    assert _resolve_slide_count("A 500-slide deck about everything", 10) == MAX_SLIDE_COUNT
    assert _resolve_slide_count("A 1-slide deck", 10) == MIN_SLIDE_COUNT


def test_unrelated_numbers_in_the_topic_are_not_mistaken_for_a_slide_count():
    """A year, a percentage, a plain number with no "slide" word next
    to it — none of these should be misread as a slide-count request."""
    assert _resolve_slide_count("The 1969 moon landing and its legacy", 10) == 10
    assert _resolve_slide_count("Why 95% of startups fail", 10) == 10
    assert _resolve_slide_count("The top 10 programming languages in 2024", 10) == 10


def test_first_mention_wins_when_multiple_numbers_could_plausibly_match():
    assert _resolve_slide_count("A 7-slide deck comparing 3 programming languages", 10) == 7
