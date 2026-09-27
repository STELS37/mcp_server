# Security Policy

## Supported version

The `main` branch is the supported source line for this repository.

## Reporting a vulnerability

Do not open a public issue containing vulnerability details, credentials, private keys, access tokens, server addresses, or reproduction data that exposes infrastructure.

Use GitHub's private vulnerability reporting / Security Advisory flow when it is available for this repository. If private reporting is unavailable, contact the repository owner privately through GitHub before publishing technical details.

## Credential handling

Real credentials and runtime secrets must never be committed. If a secret is committed or exposed in Actions logs, treat it as compromised: revoke or rotate it first, then remove the exposed material from the repository/history as a separate cleanup step.

## Deployment invariant

Production deployment must originate from an exact, verified `main` commit and must fail closed on dirty/diverged production worktrees or source-SHA mismatch.
