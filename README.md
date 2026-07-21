# Radar

Radar is a self-hosted Cineplex ticket-drop watcher with a real Android client.
It polls the current Cineplex public web contracts politely, de-duplicates drops in
SQLite, sends time-sensitive ntfy/UnifiedPush alerts, ranks showtimes and contiguous
seats deterministically, and gives the user a Cineplex deep link to finish checkout.

The safe build is complete through assisted-buy v2a. Authenticated login, seat holds,
CineClub application, final confirmation, and unattended buying remain intentionally
disabled until those flows are captured and redacted from a real logged-in session.

## What is included

- Python 3.12 FastAPI backend, SQLite state, async watcher, jitter, bounded burst mode,
  and exponential 403/429 backoff.
- Bearer-authenticated API plus public `/health` and generated OpenAPI docs at `/docs`.
- Kotlin/Jetpack Compose Android app (min SDK 26): Feed, Radar editor, Chat, Settings,
  error states, deep links, and high-priority UnifiedPush notifications.
- Server-backed Settings theatre selector with all current Toronto Cineplex locations;
  global on/off choices persist in SQLite and filter every watch.
- Daily TMDB discovery and nano-gpt/OpenAI-compatible strict-JSON LLM client.
- Pure showtime/seat ranking with accessibility exclusions and offline fixtures.
- Docker Compose deployment for Radar and ntfy, suitable for Unraid and Cloudflare Tunnel.

## Quick start on Unraid

For the shortest Git-repository installation, follow [UNRAID.md](UNRAID.md).

1. Copy this `radar` directory to an Unraid share and open a terminal in it.
2. Copy `.env.example` to `.env`. Set at minimum:
   `APP_AUTH_TOKEN`, `CINEPLEX_SUBSCRIPTION_KEY`, `NTFY_TOPIC`, and
   `PUBLIC_NTFY_BASE_URL`. Add TMDB/nano-gpt values to enable discovery and Chat.
3. Run `docker compose up -d --build`, or deploy `compose.unraid.yaml` through
   Dockhand/Compose Manager Plus.
4. Route the Radar service (`http://<unraid-host>:8000`) and ntfy service
   (`http://<unraid-host>:8080`) through separate HTTPS Cloudflare Tunnel hostnames.
   Do not expose port 8000 directly to the internet.
5. Confirm `https://<radar-host>/health`, then use the app Settings screen to save
   that HTTPS URL and the same bearer token.
6. Install an ntfy-compatible UnifiedPush distributor on the phone. In Radar,
   save connection settings first, then tap **Connect ntfy / UnifiedPush**. The app
   registers its private endpoint with the backend. A configured `NTFY_TOPIC` remains
   a parallel fallback for the standard ntfy app; tap **Send test notification**.

The starter ntfy configuration uses read/write access with an unguessable private
topic so first boot works. For stricter operation, create an ntfy user/token, set
`NTFY_AUTH_DEFAULT_ACCESS=deny-all`, put its publish token in `NTFY_TOKEN`, and restart.

## Add a watch

Use Chat when the LLM is configured, or call the API directly:

```powershell
$headers = @{ Authorization = "Bearer <APP_AUTH_TOKEN>" }
$body = @{
  movie_query = "Dune: Messiah"
  preferred_theatre_names = @("Scotiabank Theatre Toronto")
  format_preference = @("IMAX with Laser", "IMAX")
  preferred_dates = @("2026-08-14")
  time_start = "18:00"
  time_end = "23:00"
  party_size = 2
  armed_mode = "assisted_buy"
} | ConvertTo-Json
Invoke-RestMethod https://radar.example.com/radar -Method Post -Headers $headers -ContentType application/json -Body $body
```

The background watcher runs every five minutes by default. A one-off authenticated
diagnostic poll is available at `POST /internal/poll` but is intentionally omitted
from OpenAPI. Burst mode only takes effect when `BURST_MODE=true` and `BURST_UNTIL`
is a future ISO-8601 timestamp; its interval is clamped to at least 30 seconds.

## Local development and verification

Backend (PowerShell):

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Android (JDK 17 and Android SDK 36 required):

```powershell
cd android
.\gradlew.bat test assembleRelease assembleAndroidTest
```

The sideloadable APK is written to
`android/app/build/outputs/apk/release/app-release.apk`. The release variant is
currently signed with the Android debug key for personal sideloading; replace the
signing configuration with a private release keystore before distributing it.

## API contract

Authenticated unless noted:

- `GET /health` (public)
- `GET /settings/theatres` and `PUT /settings/theatres` (bearer-authenticated)
- `GET|POST /radar`, `PATCH|DELETE /radar/{id}`
- `GET /events?since=`, `GET /suggestions`
- `POST /suggestions/{id}/accept`, `POST /suggestions/{id}/decline`
- `POST /bookings/{id}/approve`, `POST /bookings/{id}/cancel`
- `POST /chat`, `POST /notifications/test`, `POST /push/register`

`/bookings/{id}/approve` returns a safe conflict while account/checkout flags are
off, and a deliberate not-implemented response if someone turns them on before the
authenticated flow is captured. No endpoint can implicitly enable unattended buy.

## Schema-drift field map

Phase 1 depends on catalog `items[].id/name/filmUrl/releaseDate`, bookable-date string
arrays, and showtime nesting `theatre/theatreId -> dates[].startDate -> movies[] ->
experiences[].experienceTypes -> sessions[]`. Session fields used are
`vistaSessionId`, `areaCode`, `showStartDateTime`, `isSoldOut`,
`isShowtimeEnabledOnline`, `seatsRemaining`, and ticketing URLs.

Phase 2 depends only on Radar's own OpenAPI models and ntfy/UnifiedPush endpoint URLs.
Phase 3 depends on TMDB `results[].id/title/release_date` and OpenAI-compatible
`choices[0].message.content`. LLM output is validated; malformed output becomes a
clarification instead of a guessed watch.

Phase 4 depends on seat layout `standardSeats/dboxSeats/balconySeats`, area
`top/left/columnWidth`, `rows[].number`, and seat `id/label/type/column`, plus
availability `seatAvailabilities[seatId]`. Missing or renamed data is logged and
skipped. Wheelchair and companion seats are never selected.

Phase 5 uses a returned ticketing URL when present, otherwise the current ticketing
routing contract with `vistaSessionId`, `areaCode`, and `theatreId`. Phase 6 has no
implemented dependencies: see `backend/docs/api-samples/authenticated-flows.PENDING.md`.

## Safety notes

- Keep `ENABLE_CINEPLEX_ACCOUNT=false`, `ENABLE_CHECKOUT=false`, and
  `ALLOW_UNATTENDED_BUY=false`.
- Secrets come only from `.env`, are gitignored, and are never logged.
- The committed samples are redacted excerpts. Re-capture when Cineplex schema drift
  is suspected; do not patch parsers by guessing private checkout behavior.
- CAPTCHA solving or bypass is outside scope. Future v2b must stop, notify, and hand
  control to the user whenever one appears.
