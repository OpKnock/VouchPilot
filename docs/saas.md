# SaaS / hosted mode

VouchPilot remains local-first by default. The repository also supports a hosted frontend + FastAPI deployment for a private beta or internal service.

## Frontend

Build the React app with:

\`VITE_API_URL=https://api.example.com\`
\`VITE_DESKTOP_DOWNLOAD_URL=https://github.com/OpKnock/VouchPilot/releases/latest/download/VouchPilot-Windows.zip\`

When \`VITE_API_URL\` points at a different origin, the UI enters hosted mode. Recent runs and workspace preferences remain in the user's browser.

## API

Set:

\`VOUCH_SAAS_MODE=1\`
\`VOUCH_CORS_ORIGINS=https://app.example.com\`

Hosted mode does not persist the shared \`settings.json\` file; settings are treated as per-browser preferences by the frontend. Uploaded documents are still processed as request-scoped temporary files.

## Security boundary

Do not put the FastAPI service directly on the public internet without an authentication layer, rate limiting, TLS, logging and an appropriate reverse proxy/WAF. VouchPilot currently provides the application-level classification API and hosted-mode CORS boundary; it does not claim to implement multi-tenant identity, billing, compliance certification, or enterprise SSO.

A practical SaaS deployment is:

\`Browser -> authenticated reverse proxy / identity provider -> VouchPilot API\`

Keep the processing service stateless where possible, and add a tenant-owned database/object store only when persistent cloud history is actually required.

## Download-and-use experience

The Windows release workflow creates \`VouchPilot-Windows.zip\` containing the standalone executable and installation guide. The root \`Install-VouchPilot.ps1\` downloads the latest release, installs it under the user's LocalAppData programs folder, creates a desktop shortcut, and launches VouchPilot.

This is the supported zero-Python/zero-Node desktop path.
