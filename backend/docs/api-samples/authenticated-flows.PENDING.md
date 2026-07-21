# Owner action required

The capture browser was logged out. To preserve account and payment safety, no
login, seat reservation, CineClub-ticket application, or final-confirmation
request was attempted.

Capture these in DevTools Network while completing a normal purchase manually,
then redact cookies, bearer/session tokens, names, emails, loyalty identifiers,
payment details, and order numbers:

1. login/auth request and response;
2. `reserve-seats` request and response;
3. CineClub available-ticket request and ticket-application request/response;
4. final confirmation request/response (do not repeat a purchase for capture).

Do not enable the account or checkout flags before these samples have parser
fixtures and tests.

