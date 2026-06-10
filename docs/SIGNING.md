# Code signing the desktop installers

The release workflow (`.github/workflows/release.yml`) builds **unsigned** installers by
default. It signs (and notarizes on macOS) automatically once you add the matching
**repository secrets** (Settings → Secrets and variables → Actions). No workflow edits
needed — the steps are already conditional on these secrets.

## Windows (Authenticode)

| Secret | Value |
|---|---|
| `WIN_CSC_LINK` | base64 of your code-signing `.pfx`/`.p12`: `base64 -w0 cert.pfx` |
| `WIN_CSC_KEY_PASSWORD` | the `.pfx` password |

Get a cert from a CA (DigiCert, Sectigo, …) or an EV/OV token provider. Without this,
Windows SmartScreen shows an "unknown publisher" prompt on first run.

## macOS (Developer ID + notarization)

| Secret | Value |
|---|---|
| `MAC_CSC_LINK` | base64 of your **Developer ID Application** `.p12`: `base64 -i cert.p12` |
| `MAC_CSC_KEY_PASSWORD` | the `.p12` password |
| `APPLE_ID` | your Apple Developer account email |
| `APPLE_APP_SPECIFIC_PASSWORD` | an app-specific password (appleid.apple.com → Sign-In & Security) |
| `APPLE_TEAM_ID` | your 10-char Apple Team ID |

All five enable signing **and** notarization (the workflow passes
`--config.mac.notarize=true` only when `APPLE_ID` + `APPLE_TEAM_ID` are present). Requires
a paid Apple Developer account. Without these, Gatekeeper requires right-click → Open on
first launch.

## Build / re-build

Push a tag — the matrix builds Windows `.exe`, macOS arm64 `.dmg`, and macOS x64 `.dmg`,
then publishes them to the release for that tag:

```bash
git tag v0.1.2 && git push origin v0.1.2
```
