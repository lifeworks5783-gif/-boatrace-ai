# Family Page Trigger

Small Render web service used by the family prediction page.

POST /trigger updates config/run_fast_live_v3_now.txt in the main BOATRACE AI repo.
That push starts Fast Live Collection V3, which then starts live prediction and the family-page update.

Required environment variables:
- GITHUB_TOKEN
- GITHUB_OWNER=lifeworks5783-gif
- GITHUB_REPO=-boatrace-ai
- TRIGGER_PATH=config/run_fast_live_v3_now.txt
- ALLOWED_ORIGIN=https://lifeworks5783-gif.github.io

Start command:
gunicorn app:app --bind 0.0.0.0:$PORT

Render root directory:
render_trigger
