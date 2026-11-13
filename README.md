# MotherDuck Dive embed demo (Brandwatch)

A web page showing the MotherDuck Dive **Brandwatch Sentiment Intelligence** in an iframe. The page around it ("Insight Hub") is fictional decoration.

Hosted as an Azure Web App (Linux, Free F1 plan) behind company sign-in (Entra ID, our tenant only).

## How it works

1. A signed-in user opens the page. App Service Authentication ("Easy Auth") has already made them sign in with their company account.
2. `index.html` calls `/api/session`.
3. `app.py` asks MotherDuck's API for an embed session for the Dive, using the caller token (`svc_embed_caller`, Admin role) and running the Dive as `svc_embed_internal` (read-only). It reuses a session for up to 12h, so every user gets at least 12h before the 24h session expires.
4. The page loads the Dive in an iframe: `https://embed-motherduck.com/sandbox/#session=<session>`

`/api/session` also refuses any request that Easy Auth hasn't signed in, so the app stays locked even if Easy Auth is switched off by mistake.

| File | Purpose |
| --- | --- |
| `app.py` | Flask app: serves the page and `/api/session` |
| `motherduck_session.py` | Token checks and the MotherDuck API call |
| `index.html` | The page |
| `check_token.py` | Local check that a token file really is `svc_embed_caller`'s |
| `bitbucket-pipelines.yml` | Deploys `main` to Azure |

## Run it locally

```bash
make serve    # http://localhost:8000, no login; token from ~/.motherduck_svc_embed_caller_read_write_token_01 (or $TOKEN_FILE)
make check    # confirm the token file is svc_embed_caller's (needs the duckdb CLI)
```

## Token safety

**Only the `svc_embed_caller` token is ever used.** The app refuses any other token (checked against its account email) and any expired one, and never logs or returns a token. `make check` adds an online check that MotherDuck reports `current_user = svc_embed_caller`; run it on a token before putting it in Azure.

## Accounts

| Account | Role | Purpose |
| --- | --- | --- |
| `svc_embed_caller` | Admin | Creates embed sessions. Tested 2026-11-13: Explorer and Builder were refused. |
| `svc_embed_internal` | Explorer | The identity the Dive runs as. Has read access to the `brandwatch` share only. |

## Deploying to Azure

One-off setup, with the Azure CLI (`az login` first). Pick a globally unique app name.

```bash
RG=rg-dive-embed-demo
LOC=uksouth
PLAN=asp-dive-embed-demo
APP=ff-dive-embed-demo        # becomes https://$APP.azurewebsites.net

az group create -n $RG -l $LOC
az appservice plan create -g $RG -n $PLAN --is-linux --sku F1
az webapp create -g $RG -p $PLAN -n $APP --runtime "PYTHON:3.12"
az webapp update -g $RG -n $APP --https-only true
az webapp config set -g $RG -n $APP --ftps-state Disabled \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 app:app"
az webapp config appsettings set -g $RG -n $APP --output none --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  MOTHERDUCK_CALLER_TOKEN="$(cat ~/.motherduck_svc_embed_caller_read_write_token_01)"
```

Then turn on sign-in in the portal: **Web app → Authentication → Add identity provider → Microsoft**:
- App registration: create new
- Supported account types: **Current tenant – Single tenant**
- Restrict access: **Require authentication**; unauthenticated requests: **HTTP 302 redirect**

Deploys: push to `main` and Bitbucket Pipelines deploys it (see the variables listed in `bitbucket-pipelines.yml`). A deploy service principal scoped to just this app:

```bash
az ad sp create-for-rbac --name sp-dive-embed-demo-deploy --role "Website Contributor" \
  --scopes "$(az webapp show -g $RG -n $APP --query id -o tsv)"
```

To deploy by hand instead:

```bash
python3 -m zipfile -c app.zip app.py motherduck_session.py index.html requirements.txt
az webapp deploy -g $RG -n $APP --src-path app.zip --type zip
```

### Free tier limits

F1 apps sleep after about 20 minutes idle, so the first visit after a quiet spell takes a few extra seconds. There's also a daily CPU quota (60 minutes), which is plenty for this page because the dashboard itself is served by MotherDuck.

## Rules

- The caller token stays server-side only: an App Service setting (or a Key Vault reference), never in code, the repo, logs or the browser.
- `svc_embed_internal` is hard-coded as the run-as account; it is never taken from the browser.
- The site stays behind company sign-in (Entra ID, single tenant).
- Session strings are credentials: don't log them.
- New Dives start private; share them with `svc_embed_internal` before embedding.

Docs: https://motherduck.com/docs/key-tasks/dives/embedding-dives/
