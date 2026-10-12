# Cloudflare two-minute live dispatcher (staged, not deployed)

This Cloudflare Cron Worker checks every two minutes whether the existing
GitHub live collection workflow is already active and dispatches it only when
idle. Existing GitHub five-minute scheduler is kept as fallback. It does **not**
move official scraping, six-boat scoring, Fujin/Raijin signal logic, storage,
or publication to Cloudflare, and does **not** guarantee timely prediction.

Deployment prerequisites: Cloudflare account access, Workers enabled, wrangler
CLI, and a separately provisioned GitHub fine-grained PAT with Actions write
permission on the private repository. Never commit the token.

In this directory:

    npx wrangler secret put GITHUB_TOKEN
    npx wrangler deploy

After deployment, confirm the Worker Cron trigger is active, recent scheduled
invocations succeed, and that Fast Live Collection V3 workflow starts at the
intended cadence. Do not turn off the GitHub fallback schedule before this
verification. The next phase to remove GitHub collection dependence is a
Cloudflare-native official beforeinfo collector and D1 writes.
