# Install Radar on Unraid

Repository: `https://github.com/BiggestFren/Cineplex-Radar`

Unraid does not include Docker Compose natively. If Portainer is already installed,
use its Git-backed Stacks feature. Dockhand and Compose Manager Plus are alternatives,
not requirements.

## Option A: Portainer Git stack

1. Open Portainer and select the local Docker environment.
2. Select **Stacks**, **Add stack**, then **Git repository**.
3. Use stack name `cineplex-radar` and repository URL
   `https://github.com/BiggestFren/Cineplex-Radar` with authentication disabled.
4. Use repository reference `refs/heads/main` and Compose path
   `compose.unraid.yaml`.
5. In **Environment variables**, add the four required values listed below.
6. Click **Deploy the stack**. Radar opens on `http://<unraid-ip>:8000/health`;
   ntfy opens on `http://<unraid-ip>:8080`.

## Option B: Dockhand Git deployment

1. In Unraid **Apps**, install **Dockhand**.
2. In Dockhand, create a stack from this Git repository:
   `https://github.com/BiggestFren/Cineplex-Radar`
3. Select branch `main` and Compose file `compose.unraid.yaml`.
4. In the Git stack's environment-variable panel, add the four required values
   listed below. Dockhand injects them without committing them to GitHub.
5. Deploy the stack. Radar opens on `http://<unraid-ip>:8000/health`; ntfy opens
   on `http://<unraid-ip>:8080`.

## Option C: Compose Manager Plus

1. In Unraid **Apps**, install **Compose Manager Plus**.
2. Add a stack named `cineplex-radar`.
3. Paste `compose.unraid.yaml` into its Compose editor.
4. Paste `.env.unraid.example` into its Env editor and fill every `replace-*` value.
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
