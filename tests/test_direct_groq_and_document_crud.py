import io
import sys
import types
from unittest.mock import patch

import pytest

from visionguide.semantic_router import SemanticCommandRouter


class DirectRoutingTests:
    def test_unknown_voice_request_defaults_to_groq_general_query(self):
        router = SemanticCommandRouter(None, enable_local_semantic=False)
        result = router.route("Explain why the sky appears blue")
        assert result.action == "general_query"
        assert result.arguments["prompt"] == "Explain why the sky appears blue"
        assert result.source == "unmatched-to-groq"

    def test_word_save_phrases_route_locally(self):
        router = SemanticCommandRouter(None, enable_local_semantic=False)
        assert router.route("save it").action == "word_save_document"
        assert router.route("save the current Word document").action == "word_save_document"
        assert router.route("save Word document as report.docx").arguments == {"file_name": "report.docx"}

    def test_word_replace_and_delete_route_to_confirmable_operations(self):
        router = SemanticCommandRouter(None, enable_local_semantic=False)
        replace = router.route('replace "old phrase" with "new phrase" in Word')
        assert replace.action == "word_replace_text"
        assert replace.arguments == {"find_text": "old phrase", "replace_text": "new phrase"}
        delete = router.route("delete selected text in Microsoft Word")
        assert delete.action == "word_delete_selection"

    def test_groq_candidate_tool_menu_includes_word_crud_tools(self):
        names = {item["name"] for item in SemanticCommandRouter._groq_candidate_functions("save and update this Word document")}
        assert {"word_save_document", "word_replace_text", "word_delete_selection"}.issubset(names)


def test_voice_text_query_submits_directly_without_confirmation():
    from visionguide.app import ArthurApp

    captured = {}
    class Assistant:
        def available(self):
            return True
        def ask_text(self, prompt, *, use_web_search=False, conversation_context=""):
            captured.update(prompt=prompt, use_web_search=use_web_search, context=conversation_context)
            return "Here is the answer."

    app = object.__new__(ArthurApp)
    app._dispatch_turn_id = None
    app.conversation_context = types.SimpleNamespace(render=lambda **_kwargs: "local context")
    app.share_conversation_context = False
    app.gemini = Assistant()
    app.status_var = types.SimpleNamespace(set=lambda value: captured.setdefault("status", value))
    app._set_output = lambda value: captured.setdefault("output", value)
    app._ask_yes_no = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected confirmation dialog"))
    app._run_async = lambda action, function: captured.update(action=action, response=function())

    app._submit_voice_text_ai("Explain binary search trees")

    assert captured["action"] == "text_ai"
    assert captured["response"] == "Here is the answer."
    assert captured["prompt"] == "Explain binary search trees"
    assert captured["use_web_search"] is False
    assert captured["context"] == ""


def _fake_com_modules(word, calls):
    client_module = types.ModuleType("win32com.client")
    client_module.GetActiveObject = lambda _name: word
    win32_module = types.ModuleType("win32com")
    win32_module.client = client_module
    pythoncom_module = types.ModuleType("pythoncom")
    pythoncom_module.CoInitialize = lambda: calls.append("co_init")
    pythoncom_module.CoUninitialize = lambda: calls.append("co_uninit")
    return {
        "pythoncom": pythoncom_module,
        "win32com": win32_module,
        "win32com.client": client_module,
    }


def test_word_save_as_uses_safe_documents_folder_and_docx_extension():
    from visionguide.integrations import gui_automation

    calls = []
    document = types.SimpleNamespace(
        Name="Document1", Path="", SaveAs2=lambda **kwargs: calls.append(kwargs)
    )
    word = types.SimpleNamespace(Documents=types.SimpleNamespace(Count=1), ActiveDocument=document)
    with patch.dict(sys.modules, _fake_com_modules(word, calls)), \
         patch.object(gui_automation, "activate_window", return_value="Document1 - Word"), \
         patch("os.path.exists", return_value=False), \
         patch("os.makedirs"):
        result = gui_automation.save_active_word_document("report")
    save_call = next(call for call in calls if isinstance(call, dict))
    assert save_call["FileName"].endswith("Documents/ARTHUR/report.docx") or save_call["FileName"].endswith("Documents\\ARTHUR\\report.docx")
    assert save_call["FileFormat"] == 16
    assert "Saved the active Microsoft Word document" in result


def test_word_replace_requires_confirmation_and_applies_replace_all():
    from visionguide.integrations import gui_automation

    calls = []
    find = types.SimpleNamespace(
        ClearFormatting=lambda: calls.append("find_clear"),
        Replacement=types.SimpleNamespace(ClearFormatting=lambda: calls.append("replace_clear")),
        Execute=lambda **kwargs: calls.append(kwargs),
    )
    document = types.SimpleNamespace(Name="Test.docx", Content=types.SimpleNamespace(Text="old old", Find=find))
    word = types.SimpleNamespace(Documents=types.SimpleNamespace(Count=1), ActiveDocument=document)
    modules = _fake_com_modules(word, calls)
    with patch.dict(sys.modules, modules), patch.object(gui_automation, "activate_window", return_value="Test.docx - Word"):
        with pytest.raises(PermissionError):
            gui_automation.replace_text_in_active_word_document("old", "new", confirmed=False)
        result = gui_automation.replace_text_in_active_word_document("old", "new", confirmed=True)
    execute_call = next(call for call in calls if isinstance(call, dict))
    assert execute_call["FindText"] == "old"
    assert execute_call["ReplaceWith"] == "new"
    assert execute_call["Replace"] == 2
    assert "2 occurrence(s)" in result


def test_word_selection_delete_is_confirmation_gated_and_checks_preview():
    from visionguide.integrations import gui_automation

    calls = []
    selection = types.SimpleNamespace(Text="remove me", Delete=lambda: calls.append("deleted"))
    document = types.SimpleNamespace(Name="Test.docx")
    word = types.SimpleNamespace(Documents=types.SimpleNamespace(Count=1), ActiveDocument=document, Selection=selection)
    modules = _fake_com_modules(word, calls)
    with patch.dict(sys.modules, modules), patch.object(gui_automation, "activate_window", return_value="Test.docx - Word"):
        assert gui_automation.get_active_word_selection_text() == "remove me"
        with pytest.raises(PermissionError):
            gui_automation.delete_active_word_selection("remove me", confirmed=False)
        result = gui_automation.delete_active_word_selection("remove me", confirmed=True)
    assert "deleted" in calls
    assert "Deleted the confirmed" in result


def test_google_docs_delete_range_requires_confirmation_and_uses_delete_content_range():
    from visionguide.integrations import google_workspace_extended as ext

    captured = {}
    class Request:
        def execute(self):
            return {"replies": [{}]}
    class Documents:
        def batchUpdate(self, **kwargs):
            captured.update(kwargs)
            return Request()
    service = types.SimpleNamespace(documents=lambda: Documents())
    with patch.object(ext, "_svc", return_value=service):
        with pytest.raises(PermissionError):
            ext.execute_google_workspace_extended_operation(
                "docs_delete_range", {"identifier": "docid123", "start_index": 4, "end_index": 9}, confirmed=False
            )
        result = ext.execute_google_workspace_extended_operation(
            "docs_delete_range", {"identifier": "docid123", "start_index": 4, "end_index": 9}, confirmed=True
        )
    assert captured["documentId"] == "docid123"
    assert captured["body"]["requests"][0]["deleteContentRange"]["range"] == {"startIndex": 4, "endIndex": 9}
    assert result["deleted_range"] == {"start_index": 4, "end_index": 9}


def test_drive_file_update_can_upload_text_content_after_confirmation():
    from visionguide.integrations import google_workspace_extended as ext

    captured = {}
    class Request:
        def execute(self):
            return {"id": "file123", "name": "notes.txt"}
    class Files:
        def update(self, **kwargs):
            captured.update(kwargs)
            return Request()
    service = types.SimpleNamespace(files=lambda: Files())
    package = types.ModuleType("googleapiclient")
    http_module = types.ModuleType("googleapiclient.http")
    class FakeUpload:
        def __init__(self, stream, mimetype, resumable):
            self.bytes = stream.read()
            self.mimetype = mimetype
            self.resumable = resumable
    http_module.MediaIoBaseUpload = FakeUpload
    package.http = http_module
    with patch.dict(sys.modules, {"googleapiclient": package, "googleapiclient.http": http_module}), patch.object(ext, "_svc", return_value=service):
        with pytest.raises(PermissionError):
            ext.execute_google_workspace_extended_operation(
                "drive_file_update", {"identifier": "file123", "content": "updated content"}, confirmed=False
            )
        result = ext.execute_google_workspace_extended_operation(
            "drive_file_update", {"identifier": "file123", "content": "updated content"}, confirmed=True
        )
    media = captured["media_body"]
    assert media.bytes == b"updated content"
    assert media.mimetype == "text/plain"
    assert result["file"]["id"] == "file123"
