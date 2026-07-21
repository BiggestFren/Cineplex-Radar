# Radar build contract

This repository implements the supplied Cineplex Radar plan: a personal Toronto
ticket-drop watcher, deterministic showtime/seat planner, Android client, TMDB
discovery, and nano-gpt-backed natural-language management.

## Delivery phases

1. Backend watcher, SQLite deduplication, ntfy/UnifiedPush, and Discord mirror.
2. Bearer-authenticated REST API and Kotlin/Compose Android app.
3. Daily TMDB discovery, strict-JSON LLM parsing, suggestion ranking, and tie notes.
4. Offline-tested deterministic showtime and contiguous-seat ranking, wired to drops.
5. Assisted-buy v2a using current Cineplex deep links.
6. Authenticated v2b and unattended v3 only after real, redacted account/checkout
   captures and an owner-observed successful purchase.

Phases 1-5 are implemented through safe v2a. Phase 6 is intentionally blocked by
default and by code. This follows the source plan's hard constraint that login,
seat-hold, CineClub, CAPTCHA handoff, and confirmation behavior must not be guessed.

Current public Cineplex traffic samples and contract notes live in
`backend/docs/api-samples/`. No subscription key, account token, credential, or
checkout payload is committed.
