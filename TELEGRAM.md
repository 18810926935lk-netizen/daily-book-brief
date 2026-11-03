# Telegram source

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
