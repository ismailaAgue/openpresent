from backend.adapters.http_headers import with_user_agent, USER_AGENT


def test_with_user_agent_sets_default_when_no_headers():
    headers = with_user_agent()
    assert headers["User-Agent"] == USER_AGENT


def test_with_user_agent_adds_to_existing_headers():
    headers = with_user_agent({"Content-Type": "application/json"})
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == USER_AGENT


def test_with_user_agent_never_overrides_an_explicit_one():
    headers = with_user_agent({"User-Agent": "SomethingElse/1.0"})
    assert headers["User-Agent"] == "SomethingElse/1.0"


def test_with_user_agent_does_not_mutate_the_input_dict():
    original = {"Content-Type": "application/json"}
    with_user_agent(original)
    assert "User-Agent" not in original  # input untouched — a new dict is returned
