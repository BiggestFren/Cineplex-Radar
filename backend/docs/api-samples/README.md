# Cineplex API capture manifest

Captured on 2026-07-21 from Cineplex's production web applications using a
browser-like request, a Cineplex page as `Referer`, and the public subscription
header redacted as `<redacted-public-web-key>`. No cookies, account identifiers,
credentials, payment data, or tokens are stored here.

The supplied build plan referenced the older `www.cineplex.com/api/v1` shape.
Current traffic uses:

- `https://apis.cineplex.com/prod/cpx/theatrical/api`
- `https://apis.cineplex.com/prod/ticketing/api`

Captured and parser-backed samples:

- movie catalog (`GET /v1/movies`)
- bookable dates (`GET /v1/dates/bookable`)
- per-date showtimes (`GET /v1/showtimes`)
- seat layout (`GET .../seat-layout`)
- seat availability (`GET .../seat-availability?preview=true`)

Pending owner-authenticated capture (therefore not implemented or enabled):

- login/auth exchange
- seat reservation/hold request body and response
- CineClub available-ticket and application flow
- final-confirmation request and response

The public bundle identifies a `POST .../reserve-seats` route, but Radar does
not guess its body or call it. Supply redacted DevTools exports for the pending
flows before enabling `ENABLE_CINEPLEX_ACCOUNT` or `ENABLE_CHECKOUT`.

