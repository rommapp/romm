---
name: security-audit
description: Audit a diff (a release tag range or a PR branch) for anything malicious or a serious security regression before shipping/merging. Use when asked to "check this release", "make sure nothing malicious slipped in", "security review this PR", or vet upstream/contributor changes. Covers supply chain, egress/exfiltration, auth/injection/traversal, CI/infra, and commit provenance — with a fast direct pass plus fanned-out deep review. Trigger on any "is this change safe?" request over a diff.
---

# Security Audit of a Diff

Goal: decide whether a set of changes contains anything **malicious** (backdoor, exfiltration, injection, obfuscated payload, supply-chain tamper) or a serious security **regression** (removed auth/ownership check). Assume most of it is legitimate work — your job is to find the needle if there is one, and give an **honest verdict**, not a vibe.

Two speeds, both required for anything non-trivial:

1. **Direct pass** (you, fast) — cheap high-signal sweeps that catch the obvious and scope the surface.
2. **Fanned-out deep review** (parallel subagents) — one per surface, reading actual files, when the diff is large.

Don't skip the direct pass even when delegating — it tells you where the risk lives and cross-checks the agents.

---

## 1. Establish the range

- Release: previous tag `..` new tag. Confirm the true predecessor with `git tag` + tag dates, don't assume.
- PR/branch: `git merge-base master HEAD` `..` `HEAD` (diff against the merge base, not raw `master..HEAD`).
- A remote PR you don't have locally: fetch the ref first (`git fetch origin pull/<n>/head` or `gh pr checkout <n>`), then set `$RANGE` as above so every sweep runs against it. `gh pr diff <n>` alone only prints the diff and leaves `$RANGE` unset, so the `git diff $RANGE` sweeps would fall back to the working tree, so don't rely on it.

```bash
RANGE=5.0.0..5.1.0-alpha.1            # or "$(git merge-base master HEAD)..HEAD"
git rev-list --count $RANGE           # how many commits
git diff --stat $RANGE | tail -30     # size + what area moved
```

Also pull the human context (release notes / PR description) — new env vars, new endpoints, and new deps named there tell you what to scrutinize.

---

## 2. Direct pass — high-signal sweeps

Run these yourself. The single most important signal for "malicious" is **unexpected outbound destinations**.

**Egress — every new host/IP/domain in added lines** (exclude lockfiles/tests/generated to cut noise):

```bash
git diff $RANGE -- . ':(exclude)*.lock' ':(exclude)**/tests/**' ':(exclude)**/__generated__/**' \
  | grep -E '^\+' | grep -vE '^\+\+\+' \
  | grep -oiE 'https?://[a-z0-9.:/_-]+' | sed -E 's#https?://##; s#/.*##' \
  | sort | uniq -c | sort -rn
```

Every hostname must resolve to a known-legit provider, the app's own origin, or a config-example placeholder. An unrecognized domain/raw IP is the finding — chase it.

**Code-exec / obfuscation in added lines** (ignore test files):

```bash
git diff $RANGE | grep -E '^\+' | grep -vE '^\+\+\+' \
  | grep -iE 'eval\(|new Function|exec\(|os\.system|subprocess|shell=True|child_process|atob\(|fromCharCode|base64|pickle\.loads|yaml\.unsafe|innerHTML|v-html|document\.write|createElement\(.script'
```

Base64/hex blobs, `eval(atob(...))`, hand-obfuscated strings = stop and dig. Subprocess/`create_subprocess_exec` hits: confirm they're `shell=False`, list-form args, and that no user-controlled value reaches the command.

**Dependencies / supply chain:**

```bash
git diff $RANGE -- '**/package.json' '**/pyproject.toml' 'uv.lock' '**/package-lock.json' '**/requirements*.txt'
```

- New deps must come from the official registry. Grep the lockfile diff for `git+`, non-`pythonhosted`/`pypi.org` / non-`registry.npmjs.org` URLs, alternate index URLs — any of those is a red flag.
- Watch for typosquats (name one char off a popular package) and unexpected new transitive sources.

**CI / infra** — these run with secrets, so they're a prime exfil vector:

```bash
git diff $RANGE -- .github/ '**/Dockerfile' '**/*entrypoint*.sh' docker/ examples/*.yml
```

Flag: `pull_request_target` (especially with a checkout of PR code), newly referenced `secrets.*`, `curl|bash` / `wget|sh` to unknown hosts, Actions repinned to a fork or downgraded to a mutable tag, changed package registries/mirrors, new privileged/host mounts. SHA-pinning actions is a _good_ sign.

**New binaries/blobs** (source repos rarely need them):

```bash
git diff --name-status $RANGE | grep -E '^A' | grep -iE '\.(bin|so|dll|exe|wasm|node|png|jpg|gif|zip|gz|woff2?)$'
```

**Commit provenance:**

```bash
git log --format='%h A:%ae C:%ce %s' $RANGE | sort   # author vs committer per commit
git shortlog -sne $RANGE                              # distinct authors + counts
```

Every author should be a plausible contributor. author≠committer with committer `noreply@github.com` is normal (squash-merge/bot). An unknown human committer overriding another author's commit is not.

---

## 3. Fan out deep review

Do this for any non-trivial diff. The direct pass alone only catches what its patterns match, so a regression that fits no grep still needs eyes on the actual files. Scale the effort to the diff: a big (hundreds of files) or sensitive-surface change wants one subagent per surface; a small non-trivial diff still gets a file-level read (yourself or a single agent) beyond the sweeps. Spawn **parallel subagents**, one per surface, in a single message. Each reads the **actual files**, not just the diff, and returns findings ranked by severity + an explicit `clean / needs-attention / malicious` verdict. Give each the exact `$RANGE` and a scoped file glob.

Typical split:

- **Backend** — new/changed endpoints missing `@protected_route` or with weakened scope/role/ownership checks; removed `assert_*_visible`; command/SQL injection; path traversal in new file ops (delete/upload/download endpoints are prime); SSRF where a request URL is user-influenced; secret handling.
- **Frontend** — off-app `fetch`/`sendBeacon`/`Image().src`/`WebSocket`; token/cookie/localStorage reads sent anywhere off-origin; `eval`/`Function`/`v-html`/`innerHTML`/dynamic `<script>`; external redirects; iframe `src`/`postMessage` trust.
- **Supply chain & provenance** — deps, lockfile sources, CI/infra, binaries, commit authorship (section 2, done thoroughly).

Prompt each agent to: assume legit-until-proven, cite `file:line`, say concretely whether each concern is **exploitable or benign**, and not to pad the report. See `docs/BACKEND_ARCHITECTURE.md` for the auth/scope model when judging backend changes.

---

## 4. Judge, then verdict

For each candidate finding, decide reachability before calling it: Is the input attacker-controlled or admin-config/DB-derived? Is the endpoint authed and scoped? Does the tainted value actually reach a sink? A scary-looking sink fed only by trusted server-side data is benign — say so.

Deliver one consolidated verdict:

- **What you checked and cleared** — grouped by surface, so the reader sees coverage, not just a green light.
- **Findings** — ranked by severity, each with `file:line`, what it does, and why it is/ isn't exploitable.
- **Overall:** `clean` / `needs attention` / `malicious`, plus any non-blocking belt-and-suspenders follow-ups (e.g. "enable `pinact run --check` in CI").

Be honest about coverage limits: if you verified SHA pins by publisher but didn't resolve them over the network, or sampled rather than read every file, say so.

## Anti-patterns

- Declaring "clean" from grep alone on a large diff — grep scopes risk, it doesn't clear it. Read the files at the sinks.
- Pasting raw diff dumps or agent transcripts back to the user instead of a judged summary.
- Treating a subprocess/`urlopen`/iframe as a finding without tracing whether user input reaches it.
- Ignoring CI/infra because "it's not app code" — it's where secrets leak.
- Skipping commit-authorship review — a malicious commit can hide among legitimate ones.
