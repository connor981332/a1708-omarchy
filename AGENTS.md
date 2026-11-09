# A1708 repair contribution workflow

This project preserves reproducible Linux fixes for the A1708 MacBook Pro.
When creating or modifying an A1708-specific patch or workaround during a
machine-repair session, complete this workflow, including the commit and PR.
The owner authorizes pushing a dedicated branch and opening the PR without
another confirmation. Do not merge it unless separately instructed.

## Scope and evidence

- Read the root README and relevant component documentation first. The recorded
  machine is a 2017 MacBookPro14,1; do not assume all A1708 revisions behave alike.
- Record the symptom, relevant hardware identifiers, OS/kernel and component
  versions, diagnostic evidence, and why the fix is hardware-specific. Keep
  observed facts separate from hypotheses.
- Preserve the actual patch, configuration, script, hook, or packaging change in
  the appropriate component directory. Add a component directory if needed.
  Include the base source revision and upstream provenance needed to reproduce
  the change. Respect existing licenses and third-party notices.
- Include installation/update steps and rollback or recovery instructions.
  Update relevant component READMEs and shared installation/verification docs
  when behavior or procedure changes. Keep the root overview accurate.
- Exclude credentials, private identifiers, raw personal logs, build outputs,
  and unrelated machine configuration. Sanitized diagnostic summaries belong in
  tracked documentation; ignored `local/` notes are not a substitute for the fix.
- For submodule changes, preserve reproducible source in an accessible upstream
  commit or a tracked local patch with application instructions. Never publish
  only a submodule pointer to an unpushed commit.

## Validation

- Run checks appropriate to the change: for example patch applicability against
  the recorded source, compilation or package build, script syntax, and targeted
  functional checks. Follow applicable system maintenance instructions and
  permission requirements for live changes.
- Record what was actually tested and the result, including relevant versions.
  Distinguish a successful build/load from a verified hardware fix. Identify
  pending checks explicitly; do not invent results or imply a reboot, sleep/wake,
  acoustic, or peripheral test happened when it did not.
- A pending hardware test does not prevent preserving the work. Open a draft PR
  if validation is incomplete or the proposed fix is still experimental, and
  explain what remains to be checked.

## Commit and publish

1. Inspect Git status, the configured remote, and the remote's default branch.
   The expected remote is `connor981332/a1708-omarchy`.
   Resolve an unexpected destination before pushing.
2. Use a dedicated descriptive branch, such as `fix/a1708-audio-resume`. Preserve
   unrelated user changes and existing commits; use an isolated worktree when
   needed. Never reset, discard, or include unrelated work to prepare the PR.
3. Review the diff for scope, secrets, and reproducibility. Stage explicit paths
   and commit the fix with its relevant documentation and validation evidence.
4. Push the branch and open a PR against the repository's default branch. If the
   session already has an open PR for the same fix, update that branch and PR
   instead of creating a duplicate. Do not push directly to the default branch
   or force-push without separate authorization.
5. Describe the symptom, resulting behavior, implementation, validation and its
   limitations, and installation/rollback implications. Link relevant upstream
   issues or source when available. Verify that the PR contains the intended diff.
6. End the chat with the PR URL, a brief explanation of the fix, tests performed,
   and any pending hardware checks or recovery steps the user needs.

If authentication, network access, permissions, or tooling prevents publication,
complete all feasible local work and report the exact blocker, branch/commit,
and remaining action. Never claim a PR exists without a returned or verified URL.

## Agent compatibility

This workflow uses standard Git and GitHub concepts and does not require a
particular agent, plugin, tool API, or installed skill. Use available tools
while respecting their security and permission controls. Keep these shared
rules in `AGENTS.md`. Harnesses that do not discover `AGENTS.md` must be
configured to load it explicitly.
