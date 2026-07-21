# Install Radar on Unraid

Repository: `https://github.com/BiggestFren/Cineplex-Radar`

Unraid does not include Docker Compose natively. The easiest Git-based installation
is **Dockhand** from Community Applications because it can deploy a stack directly
from a Git repository. **Compose Manager Plus** also works, but requires pasting the
Compose and environment files into its stack editor.

## Option A: Dockhand Git deployment

1. In Unraid **Apps**, install **Dockhand**.
2. In Dockhand, create a stack from this Git repository:
   `https://github.com/BiggestFren/Cineplex-Radar`
3. Select branch `main` and Compose file `compose.unraid.yaml`.
4. Copy `.env.unraid.example` to `.env` in the stack and fill every
   `replace-*` value. Use a long random `APP_AUTH_TOKEN`.
5. Deploy the stack. Radar opens on `http://<unraid-ip>:8000/health`; ntfy opens
   on `http://<unraid-ip>:8080`.

## Option B: Compose Manager Plus

1. In Unraid **Apps**, install **Compose Manager Plus**.
2. Add a stack named `cineplex-radar`.
3. Paste `compose.unraid.yaml` into its Compose editor.
4. Paste `.env.unraid.example` into its Env editor, rename it to `.env`, and
   fill every `replace-*` value.
5. Choose **Compose Up**. If the GHCR image is not yet available, the stack uses
   the public GitHub repository as its source-build fallback.

## Required first-run values

- `APP_AUTH_TOKEN`: generate a long random token; enter the same token in the app.
- `CINEPLEX_SUBSCRIPTION_KEY`: copy the current public subscription-key value from
  a redacted Cineplex browser Network request. Never post it to GitHub.
- `PUBLIC_NTFY_BASE_URL`: the HTTPS ntfy hostname exposed through Cloudflare.
- `NTFY_TOPIC`: a long, unguessable topic name.

TMDB and nano-gpt values are optional but required for movie suggestions and Chat.
Keep all three account/checkout safety flags set to `false`.

## Cloudflare Tunnel

Create two public hostnames in the existing tunnel:

- Radar hostname -> `http://<unraid-ip>:8000`
- ntfy hostname -> `http://<unraid-ip>:8080`

Enter only the Radar HTTPS hostname and `APP_AUTH_TOKEN` in the Android app.
Never expose the raw ports through router port forwarding.

## Updating

- Dockhand: pull/sync the repository and redeploy.
- Compose Manager Plus: choose **Pull** and then **Compose Up**.
- Terminal fallback: `docker compose -f compose.unraid.yaml pull` followed by
  `docker compose -f compose.unraid.yaml up -d --build`.
