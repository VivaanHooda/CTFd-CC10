from CTFd.plugins.flags import CTFdRegexFlag


def test_valid_regex_match_case_sensitive():
    """
    Test a valid regex match in a case-sensitive manner using CTFdRegexFlag
    """
    flag = CTFdRegexFlag()
    flag.content = r"^[A-Z]\d{3}$"
    flag.data = "case_sensitive"
    provided_flag = "A123"
    assert flag.compare(flag, provided_flag)


def test_valid_regex_match_case_insensitive():
    """
    Test a valid regex match in a case-insensitive manner using CTFdRegexFlag
    """
    flag = CTFdRegexFlag()
    flag.content = r"^[a-z]\d{3}$"
    flag.data = "case_insensitive"
    provided_flag = "A123"
    assert flag.compare(flag, provided_flag)


def test_invalid_regex_match():
    """
    Test an invalid regex match using CTFdRegexFlag
    """
    flag = CTFdRegexFlag()
    flag.content = r"^[A-Z]\d{3}$"
    flag.data = "case_sensitive"
    provided_flag = "invalid"
    assert not flag.compare(flag, provided_flag)


SECRET = "ab" * 32


def test_dynamic_tag_placement():
    """
    Test the per-team tag is inserted at %TAG%, before the last brace, or appended
    """
    from CTFd.plugins.flags import dynamic

    assert dynamic.place_tag("cc10{w4x}", "abc") == "cc10{w4x_abc}"
    assert dynamic.place_tag("cc10{a}{b}", "abc") == "cc10{a}{b_abc}"
    assert dynamic.place_tag("cc10{%TAG%_w4x}", "abc") == "cc10{abc_w4x}"
    assert dynamic.place_tag("plainflag", "abc") == "plainflag_abc"


def test_dynamic_tag_matches_legacy_scheme():
    """
    Test tags match the old rvce_flags.make_tag(secret, "", name) scheme
    """
    import hashlib
    import hmac

    from CTFd.plugins.flags import dynamic

    legacy = hmac.new(bytes.fromhex(SECRET), b"argonauts", hashlib.sha256)
    assert dynamic.make_tag(SECRET, "  ARGONAUTS ") == legacy.hexdigest()[:10]


def test_dynamic_prepare_data():
    """
    Test dynamic flag data gets a generated secret, keeps an admin key, rejects bad keys
    """
    import json

    import pytest

    from CTFd.plugins.flags import CTFdDynamicFlag, FlagException

    generated = json.loads(CTFdDynamicFlag.prepare_data(""))
    assert len(generated["secret"]) == 64
    assert generated["len"] == 10
    assert generated["bind"] == "team_name"
    assert json.loads(CTFdDynamicFlag.prepare_data("")) != generated

    own = json.loads(CTFdDynamicFlag.prepare_data({"secret": SECRET.upper()}))
    assert own["secret"] == SECRET

    for bad in ({"secret": "not-hex"}, {"len": 2}, {"bind": "nope"}, "{bad json"):
        with pytest.raises(FlagException):
            CTFdDynamicFlag.prepare_data(bad)


def test_dynamic_agent_prompt():
    """
    Test the AI-agent prompt carries the exact flag, key and correct worked examples
    """
    from CTFd.plugins.flags import agent_prompt, dynamic

    text = agent_prompt.build("rvcectf{abc}", SECRET)
    assert "Base flag:   rvcectf{abc}" in text
    assert f"Secret key:  {SECRET}" in text
    assert "rvcectf{abc_<TAG>}" in text
    assert dynamic.make_flag(SECRET, "hello", "rvcectf{abc}") in text
    assert "def make_flag" in text

    # Without a key it says so instead of inventing examples
    text = agent_prompt.build("rvcectf{abc}", "")
    assert "<SECRET_KEY" in text
    assert "Worked examples: none yet" in text
