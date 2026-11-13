---
name: repologogen_generate-brand-assets
description: Use this skill when the user wants to generate or regenerate a repository logo, web brand pack, favicon/app icons, OG image, or platform branding with the repologogen CLI in any repo. Prefer this skill when the user explicitly mentions repologogen or asks for repo branding assets from the command line.
---

# Repologogen

Use `repologogen` as a CLI-first branding workflow.

## Preconditions

Use an installed `repologogen` command, or run `uv run repologogen` from its
checkout. The AgentBridge gateway must be available; configure its API URL and
optional access token through the application's normal environment settings.

Ordinary `--dry-run` can make text-model calls. Planning without model requests
requires `--dry-run --no-metadata --var "PROJECT_DESCRIPTION=REVIEWED_DESCRIPTION"`.
Review outbound content before submitting model requests.

## Command Selection

Choose the shortest argument list after `repologogen`.
`<project>` is the selected target repository.

- README or root logo only:
  `<project>`
- Web branding for a typical web app:
  `<project> --web`
- Specific targets:
  `<project> --target web-seo --target google-play --target apple-store`
- Custom asset root:
  `<project> --target web-seo --assets-dir public/brand`
- Custom style:
  add `-s "..."`.
- Custom project name:
  add `-n "..."`.
- Dry run:
  add `--dry-run`.

`--target ...` already implies `core-brand`. `--web` is the shortest web preset and implies `core-brand`, `web-seo`, and `public/brand`.

## Execution Rules

- Inspect the repo first to see whether it already has `logo.png`, `public/brand/`, `web-seo-metadata.ts`, or similar branding outputs.
- Preserve existing output locations unless the user asks to move them.
- If the repo uses a root `logo.png` for README/social display and you generate a full brand pack, sync the root `logo.png` from `<assets-dir>/logo/logo-1024.png` so the README matches the generated pack.
- If the repo already imports `web-seo-metadata.ts`, keep the import path consistent with the generated file location.

## Verification

After generation:

- Confirm the expected output files exist.
- Report the main generated paths.
- If the repo has a typed web app, run a lightweight verification step only when it is cheap and clearly relevant, such as `npm run typecheck`.
