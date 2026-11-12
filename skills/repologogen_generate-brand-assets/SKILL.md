---
name: repologogen_generate-brand-assets
description: Use this skill when the user wants to generate or regenerate a repository logo, web brand pack, favicon/app icons, OG image, or platform branding with the repologogen CLI in any repo. Prefer this skill when the user explicitly mentions repologogen or asks for repo branding assets from the command line.
---

# Repologogen

Use `repologogen` as a CLI-first branding workflow.

## Preconditions

- Use the repository's reviewed `scripts/infisical/agentbridge_vault.py` for every agent-operated command, following `AGENTS.md` and the protected Repologogen profile. Missing or changed bindings stop explicitly; no raw gateway/provider key or cached login is a fallback.
- Stage only selected non-secret inputs in a dedicated `.internal/agent-vault/work` subdirectory. The caller's repository is not the writable workspace. Inspect outputs there and copy only approved assets back after verification.
- Prepend the launcher form below to the argument examples; never start the installed global CLI directly. Keep CLI/model/output choices and application defaults unchanged. No project or user settings file is introduced.

```sh
# REPOLOGOGEN_ROOT is the canonical checkout in the protected Repologogen profile.
WORKSPACE="$REPOLOGOGEN_ROOT/.internal/agent-vault/work/branding"
# PROJECT_BASENAME retains the caller's existing project directory name.
STAGED_PROJECT="$WORKSPACE/$PROJECT_BASENAME"
mkdir -p "$STAGED_PROJECT"
python3 -I -S -B "$REPOLOGOGEN_ROOT/scripts/infisical/agentbridge_vault.py" check --workspace "$WORKSPACE"
# Run generation only after the usual approval of outbound content.
python3 -I -S -B "$REPOLOGOGEN_ROOT/scripts/infisical/agentbridge_vault.py" run --workspace "$WORKSPACE" -- "$STAGED_PROJECT" --web
```

The catalog check verifies transport, not provider authentication or inference.
Stop if upstream authentication is known to be unavailable. Ordinary `--dry-run`
can make text-model calls; planning without model requests requires `--dry-run --no-metadata
--var "PROJECT_DESCRIPTION=REVIEWED_DESCRIPTION"`. Real text/image requests still
need their usual content approval.

## Command Selection

Choose the shortest argument list after the Vault launcher's `--`.
`<staged-project>` is the selected project inside the reviewed workspace.

- README or root logo only:
  `<staged-project>`
- Web branding for a typical web app:
  `<staged-project> --web`
- Specific targets:
  `<staged-project> --target web-seo --target google-play --target apple-store`
- Custom asset root:
  `<staged-project> --target web-seo --assets-dir public/brand`
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

## Agent-operated credential access

Use the repository's opt-in `scripts/infisical/agentbridge_vault.py run` entrypoint
with an explicit staging workspace for AgentBridge calls, following AGENTS.md.
Keep the existing model/output choices. Do not load raw gateway keys or bypass a
failed vault mapping. Provider inference and output content still need approval;
catalog checks alone do not authorize generation. Only inline image responses
are supported by the reviewed route.
