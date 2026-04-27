#!/usr/bin/env bash
set -euo pipefail

# Bootstrap AWS CLI credentials from Codespaces Secrets on startup.
# Expected secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# Optional secrets: AWS_DEFAULT_REGION, AWS_SESSION_TOKEN

if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  aws configure set aws_access_key_id "${AWS_ACCESS_KEY_ID}" --profile default
  aws configure set aws_secret_access_key "${AWS_SECRET_ACCESS_KEY}" --profile default

  if [[ -n "${AWS_DEFAULT_REGION:-}" ]]; then
    aws configure set region "${AWS_DEFAULT_REGION}" --profile default
  fi

  # For temporary credentials (STS), include a session token when provided.
  if [[ -n "${AWS_SESSION_TOKEN:-}" ]]; then
    aws configure set aws_session_token "${AWS_SESSION_TOKEN}" --profile default
  fi

  chmod 600 "${HOME}/.aws/credentials" 2>/dev/null || true
  chmod 600 "${HOME}/.aws/config" 2>/dev/null || true
  echo "AWS CLI profile updated from Codespaces Secrets"
else
  echo "AWS secrets not found in environment; skipped AWS CLI bootstrap"
fi
