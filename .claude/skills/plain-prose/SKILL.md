---
name: plain-prose
description: Make every sentence a reader sees in RomM read on the first pass, without the code open. Catches compression rather than AI tells - clipped conditionals ("Unset, keeps the value"), "X, else Y" chains, dropped subjects ("Only the fields sent change"), label fragments where a sentence belongs ("Exact artist.", "Rom internal id."), slash lists and internal slang. Covers API descriptions, docstrings, comments, en_US UI strings and error messages, over a diff or the whole codebase, with backend/tools/prose_check.py to extract the prose and a Trunk check for the rules a regex can decide. Use before opening a PR, when reviewing reader-facing text, or when asked to clean up wording across an area.
---

# Plain prose

Short is good. Clipped is not. A sentence is clipped when the writer dropped the
words a reader needs to parse it: the subject, the verb, the "if", the "or". The
writer still has the code in their head and doesn't notice. The reader has only
the sentence.

The test for every sentence: **would someone reading the API docs, the UI or the
file cold understand it on the first pass?** If they would have to reread it or
open the code, rewrite it.

`humanizer` looks for AI tells. This skill looks for compression. A string can
pass one and fail the other, so run both: this one first, then `humanizer`.

## Where it applies

| Surface                                                                                                            | Sentence or label?                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Route docstrings, schema field docstrings, `description=` on `Query`, `PathVar`, `Path`, `Header`, `Form`, `Field` | Sentences. They are the public API docs.                                                                                                                                                                                                                                                       |
| `HTTPException(detail=...)`, raised error messages, log messages                                                   | Sentences.                                                                                                                                                                                                                                                                                     |
| Docstrings and comments                                                                                            | Sentences, kept to one or two lines (`AGENTS.md`). Fix clipping with whole words, then cut content if it no longer fits.                                                                                                                                                                       |
| `frontend/src/locales/en_US/*.json`                                                                                | Labels are fragments by design: buttons, titles, menu items, column headers, chips ("Add labels", "Achievements"). Text that ends in a period, and keys ending in `-desc`, `-hint`, `-help`, `-tooltip`, `-empty`, `-subtitle`, `-error`, `-warning`, `-confirm` or `-message`, are sentences. |

Leave alone: identifiers and code in backticks, lint and type directives,
commented-out code, provider text quoted verbatim, test fixtures, other locales
(`en_US` is the source; see `frontend-i18n`), and `__generated__` files, which
you regenerate instead.

## What to fix

Each example below is a string rewritten on #5660 or flagged on `master`.

**1. Clipped conditionals.** A state word, a comma, then the result.
`prose_check` flags these.

- "Unset keeps the current value." becomes "Leave it out to keep the current value."
- "Left out, the push expects..." becomes "If left out, the server uses..."
- "Off, the chevron only keeps its..." becomes "When it is off, the chevron..."

**2. "X, else Y" chains.** `prose_check` flags these too.

- "The device to clear, else the client token's." becomes "The device to clear. Defaults to the client token's device."
- "the latest save's screenshot, else the title screen, else the first gameplay screenshot" becomes "the screenshot of the latest save, or else the title screen, or else the first gameplay screenshot"

**3. A missing subject, object or verb.**

- "Update a device. Only the fields sent change." becomes "Update a device. Fields left out of the request keep their current values."
- "The code is used up and the previous secret is replaced." becomes "The code cannot be used again, and the token's previous secret stops working."
- "No hash returns 400" becomes "Returns 400 if no hash is given"
- "Needs `device_id`." becomes "Requires `device_id`."

**4. A label where a sentence belongs.** Mostly field and parameter descriptions.

- "Exact artist." becomes "Only tracks by this artist, matched exactly."
- "Page size limit" becomes "The maximum number of items per page."
- "asc or desc." becomes "The sort direction, `asc` or `desc`."
- "Rom internal id." becomes "The ID of the rom." (`prose_check` flags "internal id")

**5. Slash lists in prose.** "title/artist/album/duration" becomes "`title`,
`artist`, `album` or `duration`" for values, or "title, artist or album" for
words. Paths, MIME types and `and/or` stay.

**6. Internal slang.** Words that mean something only inside the code:
"the row" (say what it is), "picks", "comes free" ("is filled in at no extra
cost"), "the named device" ("the device given in `device_id`"), "minus any"
("excluding any"), "a stale device" ("a device with an outdated copy"), "the
watcher" ("the file watcher").

**7. Verb-free noun stacks.** "Platform-native identity, e.g. SLUS-20152."
becomes "The game's ID on its own platform, such as `SLUS-20152`."

**8. Pronouns with two candidates.** "It looks up the title when no name is
given." Does "it" mean the barcode or the server? Write "The barcode of a
physical game, used to look up its title when no name is given."

Keep a short sentence when it is complete: "Delete a device." is fine.

## One phrasing per idea

API text repeats the same ideas. Use the same words each time.

| Idea                  | Phrasing                                                   |
| --------------------- | ---------------------------------------------------------- |
| An ID parameter       | The ID of the rom.                                         |
| An optional parameter | If left out, ... / Leave it out to keep the current value. |
| A partial update      | Fields left out of the request keep their current values.  |
| A default             | Defaults to 50.                                            |
| A filter              | Only tracks from this year or later.                       |
| A request boolean     | Whether to include each rom's `files`.                     |
| A response boolean    | True when at least one provider has matched the rom.       |
| A route error         | See below.                                                 |
| A parameter error     | An unknown or expired code returns 404.                    |
| A nullable field      | Null when `with_total` is false.                           |
| An example            | such as `snes` (not "e.g.")                                |

A route's error statuses go in `responses=` on its decorator, not in its
docstring. FastAPI lists them in the Responses table, and the schema carries
them as data:

```python
@protected_route(
    router.get,
    "/pkgj/psvita/games",
    [Scope.ROMS_READ],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The library has no PlayStation Vita platform."
        }
    },
)
def pkgj_psv_games_feed(request: Request) -> Response:
    """Get the PKGj feed of PlayStation Vita games as tab-separated text."""
```

Give each entry a `description`, since an empty `{}` shows only "Not Found".
Keep an error in a parameter's description when that parameter causes it, as
in the table. A hidden rom, platform or firmware answers like a missing one,
so describe the 404 as "No rom the caller can see matches", never as "the rom
is hidden".

Route and schema docstrings take no `Args:`, `Returns:` or `Raises:` blocks.
FastAPI and Pydantic publish the docstring verbatim, so those sections reach
the API docs as plain text.

## How to run it

**1. Mechanical rules.** `trunk check` runs `prose-check` (defined in
`.trunk/trunk.yaml`) on changed files and reports only new issues. Fix what it
flags first.

**2. Extract the prose.** One JSON line per prose unit, with its path, line,
kind (`comment`, `docstring`, `description`, `detail`, `error`, `log`,
`locale:<key>`...) and text. A directory expands to the source files under it:

```bash
python3 backend/tools/prose_check.py extract --diff origin/master... > /tmp/prose.jsonl
python3 backend/tools/prose_check.py extract backend/endpoints/roms/   # an area, whole files
```

`--diff` keeps only the units that overlap lines added since the base. Give it
paths too, before or after the option, to limit the diff to them.

**3. Review.** Read every unit against "What to fix". Up to about 150 units,
do it yourself. Beyond that, split the JSONL into batches of about 100 by file,
and give each batch to a subagent with this file's path and the instruction to
return only the units that need a change, as `path`, `line`, the old text and
the new text. A subagent proposes; you apply and check, because it cannot see
the other batches and drifts from the phrasing table.

**4. Apply.** Edit the source, never the extract. Then:

- API text: regenerate the frontend types. With no server running, dump the
  schema with `backend/tools/dump_openapi.py` and feed it to the `openapi`
  command from the `generate` script in `frontend/package.json`. The generated
  diff must be comment-only.
- `en_US` text: follow `frontend-i18n`.
- `trunk fmt && trunk check`, and `backend/tests/endpoints/test_openapi_docs.py`
  when API text changed.

**5. Run `humanizer`** over the same prose.

For a codebase-wide pass, go one area at a time (a router, a component folder,
a locale file), one PR each, so a reviewer can read the rewrites.

## Adding a rule to `prose_check`

Keep the script stdlib only: Trunk runs it on the Python runtime pinned in
`.trunk/trunk.yaml`, with no project dependencies installed.

A regex rule fails CI, so it has to be right almost every time. Before adding
one, run it over the whole codebase (`python3 backend/tools/prose_check.py
check $(git ls-files 'backend/*.py' 'frontend/src/*.ts' 'frontend/src/*.vue')`)
and read every hit. Add it only if nearly all of them are real, with a passing
and a failing case in `backend/tests/tools/test_prose_check.py`. Everything
else belongs in "What to fix" above.
