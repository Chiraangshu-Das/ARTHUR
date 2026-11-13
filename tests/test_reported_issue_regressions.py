from visionguide.semantic_router import SemanticCommandRouter
from visionguide.personalization import normalize_preferred_name, personalize_spoken_response


def make_router():
    return SemanticCommandRouter(enable_local_semantic=False)


def test_wake_word_prefixed_browser_open_is_local_and_deterministic():
    routed = make_router().route("Hey Arthur, open YouTube")
    assert routed.action == "open_website"
    assert routed.arguments["name"] == "youtube"
    assert routed.source != "unmatched"


def test_reduce_volume_routes_to_negative_adjustment():
    router = make_router()
    assert router.route("reduce system volume").arguments == {"delta": -10}
    assert router.route("reduce volume by 20 percent").arguments == {"delta": -20}
    assert router.route("set volume to 35 percent").arguments == {"level": 35}


def test_typing_and_calculation_are_not_confused():
    router = make_router()
    typed = router.route("type 2+2")
    calculated = router.route("calculate 2+2")
    assert typed.action == "type_text"
    assert typed.arguments["text"] == "2+2"
    assert calculated.action == "calculate_expression"
    assert calculated.arguments["expression"] == "2+2"


def test_finger_tracking_and_calibration_have_voice_routes():
    router = make_router()
    assert router.route("enable finger tracking").action == "gesture_control"
    assert router.route("enable finger tracking").arguments["enabled"] is True
    assert router.route("disable finger tracking").arguments["enabled"] is False
    assert router.route("calibrate finger tracking").action == "gesture_calibrate"


def test_camera_face_and_app_management_have_voice_routes():
    router = make_router()
    assert router.route("turn on camera").action == "camera_start"
    assert router.route("turn off camera").action == "camera_stop"
    assert router.route("enroll my face").action == "face_enroll"
    assert router.route("enable face recognition").arguments["enabled"] is True
    assert router.route("close Excel").arguments["name"] == "excel"


def test_memory_note_retrieval_and_profile_preference_do_not_collide():
    router = make_router()
    note = router.route("remember that I kept my keys in the bag")
    assert note.action == "memory_save"
    assert note.arguments["text"] == "I kept my keys in the bag"
    recall = router.route("where did I leave my keys")
    assert recall.action == "memory_search"
    assert recall.arguments["query"] == "my keys"
    preference = router.route("remember that I prefer to be called Sir")
    assert preference.action == "profile_preference_set"
    assert preference.arguments["value"] == "Sir"


def test_isl_voice_start_phrase_routes_to_isolated_sign_mode():
    routed = make_router().route("start sign language translation")
    assert routed.action == "sign_start"


def test_preferred_name_phrase_routes_for_immediate_profile_update():
    routed = make_router().route("Arthur, I prefer you to call me Chiraangshu")
    assert routed.action == "profile_preference_set"
    assert routed.arguments == {"key": "preferred_name", "value": "Chiraangshu"}


def test_profile_preferred_name_replaces_vocative_sir_and_addresses_short_replies():
    assert personalize_spoken_response("Yes, sir?", "Chiraangshu") == "Yes, Chiraangshu?"
    assert personalize_spoken_response("YouTube is open.", "Chiraangshu") == "Chiraangshu, YouTube is open."
    assert personalize_spoken_response("Hello, Chiraangshu.", "Chiraangshu") == "Hello, Chiraangshu."


def test_personalization_does_not_change_document_content_when_disabled():
    text = "Sir Isaac Newton formulated the laws of motion."
    assert personalize_spoken_response(text, "Chiraangshu", address_user=False) == text


def test_invalid_or_missing_preferred_name_does_not_personalize():
    assert normalize_preferred_name("") is None
    assert normalize_preferred_name("Chiraangshu") == "Chiraangshu"
    assert personalize_spoken_response("Camera is on.", None) == "Camera is on."
