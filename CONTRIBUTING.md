Contributing and collaborator access

Purpose
- Ensure new collaborators can start working quickly without SSH friction.

Recommended repository and org practices

1. Use HTTPS clone URLs in docs and onboarding scripts (simpler for most users).
2. Add team-based access in the GitHub organization and assign new members to the "developers" team with repo access.
3. Add a `CODEOWNERS` file for critical paths to request reviews from maintainers.
4. Publish a `Start_DEV.md` (or link to this file) that explains local vs Codespace setup.

Onboarding checklist for new developer

1. Join the GitHub org and the `developers` team (owner action required).
2. Clone repos using HTTPS:
   git clone https://github.com/f2fintech-tech/f2-therapist-chatbot-backend.git
   git clone https://github.com/f2fintech-tech/f2-therapist-chatbot-frontend.git
3. Set up local environment (see each repo README.dev.md).
4. If SSH is required for some workflows, add your SSH public key in GitHub profile -> SSH keys.

Automation suggestions (long-term)

- Provide a `bootstrap-dev.sh` script that:
  - Installs required tooling (node, pnpm, python venv)
  - Copies `.env.example` to `.env` and prompts user to fill important values
  - Runs database migrations or seeds (if any)

- Store non-sensitive defaults in `.env.example` and keep secrets in CI/secret managers.

If you want, I can implement a `bootstrap-dev.sh` and `Start_DEV.md` next.