# Zero-Cost Demo Deployment (Vercel)

The Tek Watch dashboard ships as a Next.js **static export** (`output: 'export'`)
that runs in **demo mode** — realistic mock data, no backend, no API or Cognito
calls. That makes it a fully self-contained static site, ideal for a free,
always-on demo (investor/visa showcase) with **$0 running cost**.

Demo mode is forced by [`dashboard/.env.production`](../dashboard/.env.production)
(`NEXT_PUBLIC_DEMO_MODE=true`), so a plain production build is the demo — no
extra configuration needed.

## One-time Vercel setup (~2 minutes)

1. Sign in at <https://vercel.com> with your GitHub account (free Hobby tier).
2. **Add New → Project** → import the `Mide69/Tek-Watch` repo.
3. In the project settings, set:
   - **Root Directory**: `dashboard`
   - **Framework Preset**: Next.js (auto-detected)
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: leave default (Vercel detects the static export)
   - **Environment Variables**: none required — `.env.production` already sets
     demo mode. (You can add them in the UI to override, but you don't need to.)
4. **Deploy.** You get `https://tek-watch.vercel.app` (or your chosen project
   name). Every push to `main` auto-redeploys.

## Custom domain (optional, when ready)

Vercel → Project → **Domains** → add `app.tekwatch.io` (or any domain you own),
then point a CNAME at Vercel as instructed. Free, automatic HTTPS.

## Admin portal (second demo project)

The admin portal (`admin-portal/`) is also a demo-mode static export, with its
own `admin-portal/.env.production` already forcing demo mode. To demo it,
create a **second** Vercel project from the same repo with **Root Directory** =
`admin-portal`. No env vars needed.

On the admin login page, click **"Enter demo (no credentials needed)"** — or
sign in with any email/password. It loads sample customers, thresholds, and
platform-operations data with no backend (see `admin-portal/src/lib/demoData.ts`).

## Relationship to the AWS deployment

The full AWS stack (ECS API + DynamoDB + Cognito + agent, in account
`409415530028`) is the *real product* and is provisioned by
[`infrastructure/terraform/`](../infrastructure/terraform/). The Vercel demo and
the AWS backend are independent: the demo never calls AWS. The AWS dev stack can
be torn down (`terraform destroy`) to save cost while the Vercel demo stays live,
and re-applied (`terraform apply`) any time — the Terraform state backend and the
GitHub OIDC role are intentionally left in place so re-deploy is a single command.
See [GUIDE.md](GUIDE.md) for the full AWS bootstrap/deploy sequence.
