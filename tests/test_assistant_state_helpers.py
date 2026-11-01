from visionguide.app import ArthurApp


def test_arthur_exit_phrases_are_recognized():
    assert ArthurApp._exit_phrase_kind("Arthur, go to sleep now") == "sleep"
    assert ArthurApp._exit_phrase_kind("Goodbye Arthur") == "goodbye"
    assert ArthurApp._exit_phrase_kind("Arthur, stop listening now") == "sleep"
    assert ArthurApp._exit_phrase_kind("Arthur, sleep") == "sleep"


def test_non_exit_commands_are_not_mistaken_for_sleep():
    assert ArthurApp._exit_phrase_kind("Arthur, open YouTube") is None
    assert ArthurApp._exit_phrase_kind("Can you tell me what sleep means, Arthur") is None


def test_arthur_addressing_is_removed_for_active_commands():
    assert ArthurApp._normalise_arthur_command("Hey Arthur, open YouTube") == "open YouTube"
    assert ArthurApp._normalise_arthur_command("Can you do this, Arthur?") == "Can you do this"
    assert ArthurApp._normalise_arthur_command("Arthur") == ""


def test_voice_confirmation_fails_closed_on_ambiguous_answers():
    assert ArthurApp._parse_voice_confirmation("yes, send it") is True
    assert ArthurApp._parse_voice_confirmation("no, cancel") is False
    assert ArthurApp._parse_voice_confirmation("maybe later") is None
