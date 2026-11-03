# Telegram source

## WebA source

`authorize_telegram_web.py` creates a fresh, owner-approved browser session without
an API application ID. Only allowlisted authentication fields are sent by stdin to
the repository secret `TELEGRAM_WEB_STATE`. No existing profile is accessed.
This is account-level authorization; revoke it in Telegram Settings > Devices.
The local browser closes before dispatching `telegram_web_probe=true` on the
existing workflow. Two sequential fresh runners restore the same authorization,
download a known public-channel attachment and verify PDF text extraction.
No state, PDF or extracted text is persisted in logs, artifacts or caches.
The scheduled source is not switched on by this helper. Two fresh-runner download
tests passed on run 41604153063. `TELEGRAM_SOURCE_MODE=web` selects the collector;
`TELEGRAM_ENABLED=true` enables it on the existing daily workflow. Manual
`telegram_only=true` tests collection without publishing, notification or saving
processed-state changes back to git.

### Publication and edition selection

Priority sources: Wall Street Journal, Washington Post, New York Times (including
its Book Review), Economist, Financial Times, Guardian, New Yorker; also New York
Review of Books, London Review of Books, Times Literary Supplement, Atlantic,
Literary Review and Publishers Weekly when identifiable attachments are available.

`telegram_publications.py` classifies filenames conservatively. The Web collector
checks approximately the most recent 800 attachments, then selects one latest
issue per publication, up to 12 issues. It does not claim exhaustive history coverage.
Regional editions with the same title/date are grouped before download. The smaller
usable edition is preferred; alternatives are tried only if the first fails.
Only the successfully processed issue key/message ID/hash/time is saved in
`data/telegram_web_seen.json`; a successful normal publication commits this state.
Subsequent runs skip a processed latest issue instead of downloading older backlogs.

Undated FT UK/US/EU files in the latest adjacent upload group are treated as
alternative editions provisionally. The first downloaded file must contain a
parseable recent date in its first-page header area; otherwise it is skipped.
Filename dates and month-only day-01 keys are deduplication candidates, not verified
publication dates. The summary must verify issue information from source text.
Unknown filenames/dates are excluded rather than guessed. Daily byte limits are
60 MiB/file and 250 MiB total, and the collection step is limited to 15 minutes.

Book/review/literary passages receive extra weight. Text is bounded to fit the
existing brief prompt, with source URLs and PDF file page numbers. Raw attachments
are deleted after extraction; excerpts remain only in runner temporary storage and
are sent to the existing GLM service for summarization. There is no OCR yet.
Partial failures produce a visible Actions warning and explicit skipped-source data.

`python -m unittest test_telegram_publications test_telegram_web_collection test_telegram_web_state test_telegram_source -v`

Only `demagazinesharing` is read. No messages are sent. No desktop session is accessed.

## First authorization

The account owner runs `authorize_telegram.py` interactively after installing
`requirements-telegram.txt`. Obtain an application ID/hash from
https://my.telegram.org/apps. Never paste credentials, login codes or session strings
into a chat, issue, source file or command line.

The helper asks for consent, logs in in memory, verifies channel access, uploads
one JSON secret `TELEGRAM_AUTH_JSON` through `gh secret set` standard input,
sets `TELEGRAM_ENABLED=true`, and dispatches the existing daily workflow with
`telegram_only=true`. This diagnostic neither generates a brief nor sends WeChat.
Review the diagnostic before claiming the integration works.

Telegram sessions provide account-level access, not channel-scoped authorization.
The collector enforces the channel in code; protect workflow/repository write access.
Revoke the session in Telegram Settings > Devices when no longer needed.
Set the repository variable `TELEGRAM_ENABLED=false` to stop collection.

## Collection and data handling

- Read up to 800 messages from the last seven days; prioritize relevant publications.
- Download up to eight PDF/DOCX attachments, at most 60 MiB per file / 250 MiB per run.
- Extract selectable PDF text and DOCX paragraphs. Scan-only documents require OCR
  and are explicitly reported as unreadable; OCR is not implemented in this version.
- Preserve PDF file-page numbers or Word paragraph positions, source message links,
  filenames and posting dates. Posting dates are not asserted as publication dates.
- Topic filtering is heuristic and bounded, not exhaustive article understanding.
- Only processed message IDs, dates and SHA-256 hashes go into `data/telegram_seen.json`.
  Exact duplicate files are skipped; different regional editions may still overlap.
- Attachments/excerpts stay in runner temporary storage, never in git, Pages,
  Actions artifacts or cache. Excerpts are supplied to the existing GLM endpoint
  for short Chinese summaries; output must not republish full magazine text.
- Missing/expired authorization or parsing failures are visibly warned; the existing
  brief continues with available sources. The diagnostic fails on collection errors.
- The existing 06:00 CST daily schedule is reused. No separate scheduled system.

## Validation

`python -m unittest test_telegram_source -v`

Fixtures test document extraction, source locations, allowlisted channel access,
duplicate suppression, private text exclusion from committed state, and stale-text
clearing on failed authorization. A real authenticated cloud diagnostic is also required.
