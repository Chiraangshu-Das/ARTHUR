from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from visionguide import desktop_actions
from visionguide.semantic_router import SemanticCommandRouter


def test_router_selects_numbered_youtube_result_locally():
    router = SemanticCommandRouter(enable_local_semantic=False)
    cases = {
        "Hey Arthur, play the first video": 1,
        "Open the second result": 2,
        "Watch video number 3": 3,
        "Choose the fifth video": 5,
    }
    for phrase, expected in cases.items():
        routed = router.route(phrase)
        assert routed.action == "youtube_select_result"
        assert routed.arguments["index"] == expected
        assert routed.source == "local-pattern"


def test_router_keeps_player_controls_separate_from_result_selection():
    router = SemanticCommandRouter(enable_local_semantic=False)
    selected = router.route("Play the first video")
    paused = router.route("Pause it")
    assert selected.action == "youtube_select_result"
    assert paused.action == "media_playback"
    assert paused.arguments["action"] == "pause"


def test_youtube_html_parser_extracts_ordered_video_ids_and_titles():
    data = {
        "contents": {"videoRenderer": {
            "videoId": "abcdefghijk",
            "title": {"runs": [{"text": "First song"}]},
        }},
        "next": [{"videoRenderer": {
            "videoId": "lmnopqrstuv",
            "title": {"simpleText": "Second song"},
        }}],
    }
    html = "<html><script>var ytInitialData = " + json.dumps(data) + ";</script></html>"
    assert desktop_actions._youtube_video_results_from_html(html) == [
        {"video_id": "abcdefghijk", "title": "First song"},
        {"video_id": "lmnopqrstuv", "title": "Second song"},
    ]


def test_search_youtube_remembers_query_for_follow_up_selection():
    desktop_actions._LAST_YOUTUBE_SEARCH_QUERY = None
    with patch.object(desktop_actions.webbrowser, "open", return_value=True):
        desktop_actions.search_youtube("Taylor Swift songs")
    assert desktop_actions._LAST_YOUTUBE_SEARCH_QUERY == "Taylor Swift songs"


def test_play_youtube_result_uses_last_search_and_opens_selected_watch_url():
    desktop_actions._LAST_YOUTUBE_SEARCH_QUERY = "Taylor Swift songs"
    html = "<script>var ytInitialData = " + json.dumps({
        "items": [{"videoRenderer": {
            "videoId": "abcdefghijk",
            "title": {"runs": [{"text": "Taylor Swift - Example (Official Video)"}]},
        }}]
    }) + ";</script>"
    response = Mock(text=html)
    response.raise_for_status.return_value = None
    with patch("requests.get", return_value=response) as get, patch.object(desktop_actions.webbrowser, "open", return_value=True) as open_url:
        result = desktop_actions.play_youtube_result(1)
    assert "Taylor Swift - Example" in result
    assert get.call_args.kwargs["timeout"] == 15
    assert open_url.call_args.args[0] == "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"


def test_play_youtube_result_requires_a_recent_search():
    desktop_actions._LAST_YOUTUBE_SEARCH_QUERY = None
    with pytest.raises(RuntimeError, match="active YouTube search"):
        desktop_actions.play_youtube_result(1)


def test_play_youtube_result_rejects_out_of_range_index():
    with pytest.raises(ValueError, match="between 1 and 20"):
        desktop_actions.play_youtube_result(21)
