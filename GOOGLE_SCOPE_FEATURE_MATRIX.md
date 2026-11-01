# Arthur — Google OAuth Scope / Feature Matrix

This document describes the Google Workspace and Generative Language operations currently wired into Arthur. It is a local implementation inventory, **not** a claim that every Google API is enabled, verified, or approved for the signed-in account.

**Current registry snapshot:** 197 extended API operations, 118 extended state-changing operations, and 146 feature-specific OAuth scope profiles. All 118 extended state-changing operations are confirmation-gated. The semantic router exposes the full operation registry. These counts describe the local implementation at the time this document was prepared; they should be regenerated from the code whenever the registry or scope profiles change.

The 146 OAuth profiles are feature-specific authorization configurations. They should not be interpreted as 146 distinct Google scope strings.

This inventory describes local handlers and authorization configurations. Provider eligibility and service enablement still require live-account acceptance testing.

## Authorization model

- OAuth credentials are acquired with a feature-specific profile in `visionguide/integrations/google_workspace.py`; token files are isolated under `data/google_tokens/`.
- `google_workspace_feature` is exposed through the typed semantic-router tool. Its operation enum is generated from the finite operation allowlist in `google_workspace_extended.py`, keeping the router's declared operation set aligned with the registered operations.
- Externally visible or destructive writes require explicit confirmation. The current confirmation set covers the extended write operations and the core Docs/Sheets/Slides/Tasks/Meet/Forms actions.
- Confirmation is an Arthur application-level safeguard. It is separate from Google's OAuth authorization and API permission checks.
- A scope in Google Auth Platform does not itself enable the API or add a handler. Google Cloud API enablement, the correct consent scopes, OAuth verification, account eligibility, Workspace administrator policy, quotas, and resource permissions are separate prerequisites.
- The desktop OAuth app does **not** request the whole catalog on every login. It requests the profile for the specific capability being used. This avoids merging highly privileged scopes into a single default token.
- A registered operation does not establish that the signed-in account can use it. The actual result depends on the granted scopes, API availability, account type, administrator policy, resource permissions, and provider-side restrictions.

## Implemented API-backed capabilities

| API / scope family | Operations wired in Arthur | Notes |
|---|---|---|
| OpenID Connect / `openid`, `userinfo.email`, `userinfo.profile` | `google_identity`, `people_user_profile`, core `profile` | The identity operation calls the OpenID Connect userinfo endpoint. Extra profile fields are opt-in and request the corresponding People API scope. |
| Calendar read/event scopes | `calendar_list`, `calendar_get`, `calendar_events_list`, `calendar_readonly_events`, `calendar_public_events`, `calendar_event_get`, `calendar_freebusy`, `calendar_events_freebusy`, `calendar_settings_list`, `calendar_setting_get` | Covers CalendarList, event lookup, free/busy and settings read. Public calendar lookup requires a public calendar ID and the public-readonly scope. |
| Calendar write/share scopes | `calendar_create`, `calendar_app_created_calendar_create`, `calendar_update`, `calendar_delete`, `calendar_subscribe`, `calendar_unsubscribe`, `calendar_event_create/update/delete`, `calendar_owned_events_list/get/create/update/delete`, `calendar_app_created_events_list/get/create/update/delete`, `calendar_acl_list/create/update/delete` | Owned-event operations use `calendar.events.owned[.readonly]`. App-created event operations use `calendar.app.created` and must target a calendar created by this app. ACL/calendar deletion and other writes require confirmation. |
| Gmail message/mail scopes | `gmail_messages_list`, `gmail_metadata_list`, `gmail_message_read/modify/delete/insert`, `gmail_send`, `gmail_compose_send`, `gmail_send_to_self`, `gmail_user_metadata` | Uses per-operation scopes including messages-readonly, messages-modify, messages, metadata, insert, send, compose, send-self and user-readonly. Message deletion is permanently destructive and confirmation-gated. |
| Gmail draft/label scopes | `gmail_drafts_list`, `gmail_draft_read/create/update/delete/send`, `gmail_compose_draft_create`, `gmail_labels_list/create/update/delete` | Draft creation can use the create-only or compose profile. Label creation uses the create-specific scope; update/delete uses the labels write scope. |
| Gmail settings / mail-management scopes | `gmail_settings_list`, `gmail_setting_get/update`, `gmail_filters_list/create/delete`, forwarding address list/create/delete, automatic-forwarding get/update, send-as list/create/update/delete, delegates list/create/delete, `gmail_notifications_watch/stop` | Write operations require explicit confirmation. Gmail push notifications also require a configured Pub/Sub topic and appropriate Cloud Pub/Sub/API permissions. |
| Drive read / metadata / item scopes | `drive_files_list`, `drive_file_get`, `drive_about`, `drive_item_list/get/update/delete`, `drive_collaboration_item_list/get`, `drive_metadata_update`, `drive_meet_files_list`, `drive_photo_files_list` | The item-scoped paths use `drive.item[.readonly]`. Metadata updates accept only selected metadata fields. `drive_photo_files_list` lists image/video files in Drive; it is not a Google Photos Library implementation. |
| Drive file/share scopes | `drive_file_create/update/copy/delete`, `drive_permission_list/create/update/delete` | File operations and permission/share changes are confirmation-gated. Broad restricted Drive access requires consent-screen verification and may require additional review. |
| Drive app data / Apps Script / Activity | `drive_appdata_list/create/delete`, `drive_apps_list`, `drive_script_get/create/update`, `drive_activity_list` | App data is constrained to the appDataFolder. Apps Script source update and creation require confirmation. Drive Activity is query-only in this adapter because its REST API exposes a query method, not an activity-write endpoint. |
| Google Docs | Core `docs_read`, `docs_create`; extended `docs_replace_text`, `docs_insert_text`, `docs_batch_update` | Write requests are limited to an explicit set of Docs API request types and require confirmation. |
| Google Sheets | Core `sheets_read`, `sheets_update`; extended `sheets_create`, `sheets_append`, `sheets_clear`, `sheets_batch_update` | Structural requests use an explicit request allowlist. Writes require confirmation. |
| Google Slides | Core `slides_read`, `slides_create`; extended `slides_batch_update` | Batch update request types are allowlisted and require confirmation. |
| Google Tasks | `tasks_list/create/update/delete/complete/reopen` | Task changes require confirmation. Current default task list is `@default`. |
| People / Contacts | `people_user_profile`, `people_contacts_search`, `people_contact_create/update/delete`, `people_other_contacts_list` | Profile data may include email/name/photo/phone/birthday/address/gender/age-range/organization fields only when those requested fields/scopes are enabled; `user.emails.read` is requested when emailAddresses are selected. Contacts writes require confirmation. |
| Google Classroom courses / rosters | `classroom_courses`, `classroom_course_get/create/update/delete`, `classroom_students_list`, `classroom_teachers_list`, `classroom_student_add/remove`, `classroom_teacher_add/remove`, `classroom_student_profile` | Course and roster writes require confirmation. Access is limited by the signed-in account role, Classroom API policies and the education domain. Email/photo fields need their corresponding profile scopes. |
| Google Classroom classwork | `classroom_coursework`, `classroom_coursework_create/update/delete`, `classroom_materials`, `classroom_material_create/update/delete`, `classroom_topics`, `classroom_topic_create/update/delete`, `classroom_announcements`, `classroom_announcement_create/update/delete` | Operations are subject to teacher/owner roles. Each mutation requires confirmation. |
| Google Classroom submissions / guardians / notifications | `classroom_submissions_list/update/turn_in/reclaim/return`, `classroom_guardians_me/list/create/delete`, `classroom_registration_create/delete` | The submissions read path selects the `me` scope for the current user's submission and the admin/student-submissions scope when a different student is requested. Guardian and roster access is restricted by Classroom role/policy. Push registration requires the configured Pub/Sub target. |
| Google Meet REST API | `meet_space_create/get/update`, `meet_end_conference`, `meet_conference_records`, `meet_recordings_list`, `meet_transcripts_list`, `meet_participants_list` | This is Meet REST metadata/artifact access; it is not live call audio/video capture. Recording/transcript resources only exist when the organization/account and conference produced them and the caller has permission. |
| YouTube Data API v3 | `youtube_search` (core), `youtube_channel`, `youtube_my_videos`, playlist list/create/update/delete/item add/remove, `youtube_upload`, `youtube_video_update/delete`, `youtube_comment_insert`, `youtube_memberships` | Uploads, publication, changes and deletes require confirmation. Channel-member endpoints and some YouTube account capabilities require specific account eligibility and approved API access. |
| Google Forms API | Core `forms_read/create`; extended `forms_responses_list/get`, `forms_update`, `forms_response_watch_create/delete` | Response data is private. Form edits and notification watch changes require confirmation. |
| Generative Language API | `generative_tuned_models_list`, `generative_tuned_model_get`, `generative_tuning_delete`, `generative_retriever_list/get/create/delete/query`, `generative_peruserquota_status` | Tuning/retriever operations use OAuth-specific profiles. `generative_peruserquota_status` honestly returns unavailable because that scope has no standalone quota-query endpoint in this adapter. Normal Gemini generation continues to use `GEMINI_API_KEY`. |
| Cloud Translation / Cloud Natural Language | Existing OAuth-backed translation and text-analysis adapters | Requires each corresponding Cloud API enabled and its feature profile consented. |
| Google Maps Platform / Cloud Vision | Existing Routes, Geocoding, Weather, Places, Air Quality, Pollen, Time Zone, Roads, consented Geolocation and Cloud Vision Web Detection adapters | Use API keys with API restrictions; these are separate from OAuth Workspace scopes. See `.env.example` and `INTEGRATIONS.md`. |

## Scope features that cannot be provided by a desktop OAuth token alone

| Scope family / item | Status and reason |
|---|---|
| `gmail.addons.current.action.compose`, `gmail.addons.current.message.action`, `gmail.addons.current.message.metadata`, `gmail.addons.current.message.readonly` | Not desktop features. They are contextual scopes for a Google Workspace/Gmail add-on runtime and active-message/add-on interactions. Equivalent desktop Gmail operations are implemented through Gmail API scopes, but they cannot reproduce the add-on context lifecycle. |
| `calendar.settings` | The Calendar API settings resource exposes list/get operations in this adapter/API surface; the scope string does not create a settings-write method. `calendar.settings.readonly` is implemented. |
| `drive.activity` write permission | Drive Activity API v2 is exposed via its query operation. There is no activity-write operation in this adapter; viewing activity is implemented with `drive.activity.readonly`. |
| `drive.install` | Installation/integration permission rather than a general file CRUD REST operation. The desktop app does not claim to install an app into Drive. |
| `drive.photos.readonly` | The current operation lists Drive image/video files. It does not manage Google Photos albums or media; that separate product surface is not implemented here. |
| `classroom.addons.student`, `classroom.addons.teacher` | Classroom add-on attachment operations run in the Classroom add-on context and are not the same as the desktop Classroom REST integration. Not implemented as add-on attachment lifecycle handlers. |
| `classroom.practicesets` | The scope is listed in the consent catalogue, but a stable public API surface for the requested create/read/delete workflow is not exposed in this desktop adapter. Not claimed implemented. |
| `meetings.conference.media.readonly`, `.audio.readonly`, `.video.readonly` | Live media capture is separate from Meet REST records/participants/transcripts and requires its specific client/runtime and eligibility. Google currently says the Meet Media API is no longer accepting new Developer Preview signups. |
| `meetings.hardware` | Organization-level Meet hardware history/control needs product/admin-specific APIs and privileges; no hardware-control handler is exposed. |
| `generative-language.peruserquota` | The scope does not by itself provide a standalone quota-query REST endpoint. The capability report returns this as unavailable rather than fabricating quota data. |
| `youtube.download` | Arthur does not download YouTube media files. The YouTube Data API is not treated as an unrestricted video-file download API. |
| `youtube.third-party-link.creator`, `youtubepartner`, `youtubepartner-channel-audit` | Partner/content-owner or account-linking features require dedicated product access, account eligibility and often provider approval. They are not implemented as general-purpose channel administration. |
| `gmail.settings.sharing` | The adapter exposes the documented delegate list/create/delete workflow through the Gmail delegates scopes. It does not provide arbitrary mail delegation policy administration beyond those endpoints. |
| `drive.apps` write, broad organization administration | Only operations with a corresponding supported REST method are exposed. A scope being writable in the consent catalogue does not mean there is a general endpoint to create/install arbitrary Drive apps or administer a Workspace organization. |

## Third-party website launcher allowlist

These fixed website aliases are available to `open_website` and the local voice parser:

- Google Cloud Console — [https://console.cloud.google.com/](https://console.cloud.google.com/)
- Neon — [https://console.neon.tech/](https://console.neon.tech/)
- Google Classroom — [https://classroom.google.com/](https://classroom.google.com/)
- Google Contacts / Contacts — [https://contacts.google.com/](https://contacts.google.com/)
- LeetCode — [https://leetcode.com/](https://leetcode.com/)
- LinkedIn Learning (including the user's typed spelling `linkedln learning`) — [https://www.linkedin.com/learning/](https://www.linkedin.com/learning/)
- Coursera — [https://www.coursera.org/](https://www.coursera.org/)
- SWAYAM (including the voice/typing alias `swaym`) — [https://swayam.gov.in/](https://swayam.gov.in/)
- NPTEL — [https://nptel.ac.in/](https://nptel.ac.in/)

This is a trusted browser-launch allowlist, not OAuth/API access to Neon, LeetCode, LinkedIn Learning, Coursera, SWAYAM, or NPTEL. These sites remain subject to their own login, terms, and supported APIs.

## First-run checklist

1. Put your Desktop OAuth JSON at `credentials/google_oauth_client.json` or point `GOOGLE_OAUTH_CLIENT_FILE` to your existing path.
2. Merge new variables from `.env.example` into your existing `.env`; do not replace a populated `.env` with a template.
3. Enable each Cloud API you actually use. Configure OAuth consent scopes separately from API-key restrictions.
4. Start Arthur and invoke one requested feature; complete the feature-specific consent flow and verify the result against the resource in Google's own UI.
5. Test read and write operations separately. For write operations, verify that Arthur presents the confirmation details before making the change.
6. Do not share `credentials/`, `data/google_tokens/`, `.env`, or any token file in issues, screenshots, source control or archives.