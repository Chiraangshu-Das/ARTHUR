# ARTHUR — Direct Groq fallback and confirmed Save/Update/Delete upgrade

## What changes

### 1. No repeated confirmation for ordinary text requests

- Local deterministic commands continue to run locally.
- If Groq function calling identifies a registered tool, ARTHUR validates and dispatches that typed action through the existing executor.
- If the request is not a local command and does not resolve to a registered operation, ARTHUR sends the current text request directly to Groq.
- The desktop no longer asks “Would you like to send this to Groq?” and no longer announces “local command not found; sending to Groq”. It responds with the result or a provider error.
- The authenticated FastAPI `/api/v1/command` text-only fallback follows the same policy. The API still requires its configured bearer token when authentication is enabled.
- Prior conversation context is not sent by default. Keep `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=0`; set it to `1` only if you intentionally want recent turns included in Groq routing and text prompts.

**Privacy consequence:** the current non-local text request/transcript is automatically transmitted to Groq. Do not speak passwords, API keys, private credentials, or text you do not want sent to the provider. This change does not upload camera frames or screenshots as part of ordinary text Q&A.

### 2. Confirmations that remain

ARTHUR still asks before actions that change data or affect other people/services, including:

- Sending email or WhatsApp messages.
- Creating/updating/deleting Google Workspace data (Docs, Drive, Calendar, Gmail, Sheets, Tasks, Contacts and other exposed operations).
- Saving a Word document, replacing its text, or deleting selected text.
- Submitting a form, publishing/uploading content, or changing network adapter state.
- Pasting dictated/generated content into a target application.
- Uploading a camera image or screenshot to Groq/Cloud Vision.
- Saving or deleting local memory where the existing workflow requests confirmation.

Text-only AI questions are the exception; those no longer prompt for provider consent.

### 3. New Microsoft Word operations

Speak these with Word open and a document active:

- `Arthur, save it.` — saves the active document. If it has never been saved, ARTHUR creates `Documents/ARTHUR/ARTHUR-Document-YYYYMMDD-HHMMSS.docx`.
- `Arthur, save the Word document as report.docx.` — saves under `Documents/ARTHUR/report.docx`.
- `Arthur, replace old phrase with new phrase in Word.` — previews and asks for confirmation, replaces all matching occurrences in the active document, and leaves it modified but unsaved.
- `Arthur, delete selected text in Word.` — previews the current selection, asks for confirmation, and checks that the selection has not changed before deletion. The document remains modified but unsaved.

Save As is restricted to `Documents/ARTHUR`; an existing destination file is not overwritten. These operations require Windows desktop Microsoft Word and `pywin32`.

### 4. Google Drive and Docs update/delete coverage

The extended Workspace registry now exposes:

- `drive_file_update`: metadata update via `payload_json`, or UTF-8 text content replacement via `content` (maximum 1,000,000 characters). A confirmation is required.
- `docs_delete_range`: delete a specified content range using `start_index` and `end_index`. A confirmation is required.

Existing Drive file deletion, Docs insert/replace/batch update, Gmail draft update/delete/send, Calendar update/delete, Sheets updates, Tasks update/delete, Contacts updates/deletes and other allowlisted CRUD operations remain behind their central confirmation gate. Each operation still requires the appropriate Google OAuth scopes, resource ID and API enablement.

Google Docs API updates are saved automatically by Google. Local Word replace/delete actions remain unsaved until you say `save it` and confirm.

## Installation

1. Close ARTHUR completely.
2. Back up `E:\Chiraangshu\MyWorkspace\ARTHUR`.
3. Extract `ARTHUR_Direct_Groq_and_Word_CUD_Upgrade_Patch.zip`.
4. Open the extracted `ARTHUR-main` folder and copy its contents into the existing ARTHUR project root, preserving the folder structure and allowing replacements.
5. Preserve your real `.env`, `.venv`, `data`, `models`, and `credentials` folders. Do not replace them.
6. No dependency-manifest changes are required by this overlay. If Word COM reports that `win32com` is missing, install `pywin32` inside the existing virtual environment:

```powershell
python -m pip install pywin32
```

## Validate and launch

From PowerShell in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m compileall -q visionguide tests
python -m pytest -q
python main.py
```

The merged source was verified in the build container with **149 passed, 4 existing FastAPI lifecycle deprecation warnings**. This automated run does not validate Windows COM, actual Word UI focus, live Groq availability, or real Google OAuth/API account permissions.

## Suggested acceptance tests

1. `Arthur, explain recursion with an example.` — should go to Groq without a consent dialog.
2. `Arthur, what is 25 multiplied by 48?` — should use the local arithmetic route.
3. `Arthur, save it.` — should show a save confirmation and save the active Word document only after approval.
4. `Arthur, replace draft with final in Word.` — should preview and ask before replacement.
5. Select a disposable phrase in Word, then say `Arthur, delete selected text in Word.` — should preview and confirm; the selection must still match before deletion.
6. Use a disposable Google Drive text file to test `drive_file_update`, and a disposable Google Doc to test `docs_delete_range`. Inspect the preview carefully before confirming.
7. Test Gmail/WhatsApp sends only with your own test account/contact and verify the recipient and entire message before confirming.

If Groq is unavailable, ARTHUR should report the provider failure; direct routing removes the extra consent prompt, not the provider's service limits or outages.
