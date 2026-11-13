# ARTHUR — Cross-application typing and Enter follow-up

This cumulative overlay extends the Direct Groq + Word/Workspace Save-Update-Delete patch.

## Behaviour

1. ARTHUR accepts a targeted typing command for a supported application or website, opens/activates that allowlisted target, focuses a known field or a uniquely identifiable Windows UI Automation field, and pastes the exact dictated text. It does not submit the text at this stage.
2. After a successful paste, ARTHUR stores the target top-level window, target type, field type, focused UI Automation runtime ID, and timestamp in memory for up to 120 seconds.
3. The next command can be `search it`, `submit it`, `press Enter`, or `hit the Enter key`. ARTHUR presses Enter only when the same window is still foreground and the same UI Automation control still has focus. The pending context is one-shot and is cleared by an unrelated command.
4. If the window or focused control changes, the target expires, or Windows cannot provide a stable focus identity, ARTHUR refuses to press Enter. The user can return to the field and repeat the typing command or press Enter manually.

## Known shortcuts and generic field access

- YouTube search: `/` focuses YouTube search.
- File Explorer / Recycle Bin search: `Ctrl+E`; address/location bar: `Ctrl+L`.
- Chrome / Edge / browser address bar: `Ctrl+L`. A page search field is treated separately and is located through UI Automation.
- Word, Excel, Notepad, Google Docs, Google Sheets, VS Code, WPS Writer/Spreadsheets, Windows Settings and selected Windows tools: `Ctrl+F` for their supported Find/Search box.
- Gmail and GitHub: `/` focuses search. Gmail's keyboard shortcuts must be enabled in Gmail settings.
- WhatsApp Web: `Ctrl+F` focuses search.
- Other allowlisted applications/websites: ARTHUR uses Windows UI Automation (`pywinauto`) to locate a visible, enabled Edit/ComboBox control by its accessible name (for example, `Search`). It accepts a unique matching control, or a sole editable control when the label is unavailable. It refuses ambiguous matches rather than guessing coordinates.

## Example commands

### YouTube

1. `Arthur, type Taylor Swift in YouTube search field.`
2. `Arthur, search it.`

Equivalent second commands: `press Enter`, `hit the Enter key`, or `submit it`.

### File Explorer

1. `Arthur, type quarterly report in File Explorer search field.`
2. `Arthur, press Enter.`

For navigation, use `File Explorer address bar` instead of `search field`.

### Excel

1. `Arthur, type Q4 revenue in Excel search field.` — opens Find with `Ctrl+F`.
2. `Arthur, press Enter.` — runs the Find query.

To enter a value in a cell, target the active cell (or focus the cell yourself and use `type exactly ...`); Enter commits the cell edit.

### Word

1. `Arthur, type recursion in Word search field.` — opens Find with `Ctrl+F`.
2. `Arthur, search it.` — runs the Find query.

To insert text into the document, say `type ... in Word document`; Enter then creates a new paragraph at the insertion point. Typing into a Word document uses Word COM and does not save the document automatically.

### Other websites and text fields

Use the site/app name and the field type, for example:

- `Arthur, type machine learning in Google search field.`
- `Arthur, type Python course in LinkedIn Learning search field.`
- `Arthur, type my question in ChatGPT text box.`
- `Arthur, type a command in VS Code editor.`

A follow-up Enter on an ordinary search field runs the search. Enter in a chat/message composer or an ambiguous form field asks for confirmation first because it may send a message or submit data.

## Supported targets

The target allowlist includes File Explorer; Microsoft Word, Excel and PowerPoint; Notepad; VS Code; WPS apps; Calculator; Task Manager; Windows Settings pages; Paint; Snipping Tool; Terminal, PowerShell and Command Prompt; Control Panel; Device Manager; Resource Monitor; Recycle Bin; AutoCAD; Arduino IDE; Python IDLE; Picasa; Photos; Media Player; Clock; and supported websites including YouTube, Google, GitHub, ChatGPT, Gemini, Claude, LeetCode, Netlify, Render, Gmail, Drive, Docs, Sheets, Maps, Meet, Classroom, Contacts, Google Cloud Console, Stack Overflow, Wikipedia, Reddit, LinkedIn, Instagram, WhatsApp Web, Coursera, SWAYAM, NPTEL, LinkedIn Learning and Neon.

Only built-in allowlisted targets can be launched by name. ARTHUR does not execute arbitrary spoken executable paths.

## Safety and limitations

- The initial dictated paste still asks for confirmation.
- Search/address fields can be submitted without another confirmation. Typing into Gmail/WhatsApp message composers, ChatGPT-like message boxes, or an ambiguous website form keeps a confirmation gate before Enter.
- Saving, deleting, updating, sending, publishing and other data-changing actions keep their existing confirmation gates.
- ARTHUR does not inspect arbitrary website DOMs. Generic field targeting depends on Windows accessibility metadata being exposed by the application/browser. If the control is not exposed or more than one candidate matches, ARTHUR refuses and asks the user to click the intended field and use `type exactly ...`.
- The remembered target is session-only, expires after 120 seconds, and is invalidated by any unrelated command.
- Actual Windows UIA, Office COM, browser behavior and live website layouts must be verified on the user's Windows machine. The automated build tests mock these Windows-specific controls.

## Added dependency

`requirements-integrations.txt` now includes the Windows-only dependency `pywinauto>=0.6.9,<0.7.0`. Install the updated integration requirements in the existing virtual environment.
