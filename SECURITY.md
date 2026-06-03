# Security Policy

## Supported Versions

This project is currently in early MVP stage (`0.2.x`) and only `main` is supported.

## Reporting a Vulnerability

Please report security issues privately to the maintainers (Ralleh AI team) and avoid posting exploit details in public issues.

When reporting, include:
- affected commit/version
- reproduction steps
- impact assessment
- suggested mitigation if available

## Security Posture (current)

- Caddy-first reverse proxy posture
- service binds loopback by default
- no secrets should be committed to git
- malformed WebSocket events are handled with structured errors

## Current limitations (known)

- no authentication/authorization on WS path yet
- no production-grade rate limiting yet
- deterministic placeholder adapters by default

Do not deploy this MVP on a public internet endpoint without additional hardening.
