from visionguide.personalization import normalize_preferred_name, personalize_spoken_response


def test_name_is_normalized_and_bounded():
    assert normalize_preferred_name("  Chiraangshu   Das ") == "Chiraangshu Das"
    assert normalize_preferred_name(" ") is None
    assert normalize_preferred_name("X" * 61) is None


def test_direct_address_sir_is_replaced_without_rewriting_titles():
    assert personalize_spoken_response("Goodbye, sir.", "Chiraangshu") == "Goodbye, Chiraangshu."
    assert personalize_spoken_response("Sir Isaac Newton was a scientist.", "Chiraangshu") == "Sir Isaac Newton was a scientist."


def test_name_is_not_added_twice():
    assert personalize_spoken_response("Hello, Chiraangshu.", "Chiraangshu") == "Hello, Chiraangshu."
    assert personalize_spoken_response("Chiraangshu, YouTube is open.", "Chiraangshu") == "Chiraangshu, YouTube is open."


def test_long_content_is_not_given_a_new_salutation():
    content = "Document text. " * 100
    assert personalize_spoken_response(content, "Chiraangshu") == content.strip()
