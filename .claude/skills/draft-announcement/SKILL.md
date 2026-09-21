---
name: draft-announcement
description: Draft the Discord release announcement for a RomM release, from the release notes plus an interview about community news. Use when asked to "write the Discord announcement for 5.3.0", "draft the announcement post", "announce the beta in Discord", or to refresh an announcement draft. Interviews the user for the things no diff contains (new team members, third-party apps to spotlight, milestones, events, Discord housekeeping), writes in the house voice, and never posts to Discord.
argument-hint: "[version to announce, e.g. 5.3.0 | nothing to infer it]"
---

# Drafting a Discord announcement

The release notes say what shipped. The announcement says why anyone should care,
in RomM's voice, in one Discord message. It is a short, warm, slightly unhinged
post: a hook, the few features worth naming, the community news, a pointer to the
notes, a sign-off.

Half the content is not in the repository. **Interview the user for it.** Never
invent a contributor, an app, a milestone, a link or a handle.

Write the draft to the session scratchpad and print it. **Never** post to Discord,
and never write into the maintainer's announcement archive (see section 1).

---

## 1. Read before you write

`$ARGUMENTS` is the version. If empty, take the newest tag and confirm it.

The release notes are the feature source.

```bash
TAG=5.3.0
gh release view "$TAG" --json body --jq .body   # the notes for this release
# for a release not yet published, use the draft in the scratchpad
```

Past announcements are the voice source, and a Discord post is not in the repo, so
they exist only wherever the maintainer archives them. Ask where that is if you do
not already know, and treat it as **read only**: drafts go to the scratchpad.

Read the **two most recent** before drafting. They set the current voice, and they
tell you which third-party apps were already spotlighted. An app highlighted in
either one does not get spotlighted again.

From the notes, pull:

- the Highlights, as candidate features to name,
- every `> [!WARNING]`, which **must** survive into the announcement (`4.1.0` led
  with the mandatory `config.yml`, `4.0.0` led with the RCE advisory),
- a rough PR count and whether the release is mostly fixes, which decides the hook.

## 2. Interview the user, one step at a time

The community news is names, URLs and handles that only the user has, so it gets
**typed, not picked**. Ask **one question per message** and wait for the answer
before asking the next. Never send the whole questionnaire as a numbered list, and
never collect the content answers as checkbox options.

Number every step and say how many there are ("Step 2 of 6"), so the user can see
where the interview ends. Each step states exactly which fields you need, and how
to skip it. Take "skip", "none" or "n/a" as an answer, move on without arguing, and
drop that item from the draft.

| #   | Step               | Ask for                                                                                                         |
| --- | ------------------ | --------------------------------------------------------------------------------------------------------------- |
| 1   | Features           | print the Highlights you found as a numbered list, ask which get named prose; the rest become bullets           |
| 2   | App spotlight      | name, repo URL, author's handle, one line on what it does. List the apps already spotlighted so nothing repeats |
| 3   | Team or role news  | handle, what they built or do, what changes now (joined the team, project gone official, new Experts)           |
| 4   | Milestone or event | what it is, the number or date, and the link                                                                    |
| 5   | Anything else      | housekeeping, a call to action, a beta bug-report ask; the exact wording they want                              |
| 6   | Pings and shape    | the only genuinely multiple-choice step, so one `AskUserQuestion` call: who gets pinged, and one message or two |

Ask for a handle as it is written in Discord, since `@Covin` and `@Covin90` are not
interchangeable. Never offer a sample answer that could be mistaken for a real one:
no invented app names, no placeholder URLs, no guessed star counts.

If steps 2 through 5 all come back empty, drop the Community news section. Several
releases (`4.3.0`, `4.4.0`) have none, and a padded one reads worse than none.

Skip a step only when the answer is already on the table, and say so rather than
silently dropping it: a user who opened with "announce 5.3.0, spotlight `<app>`" has
answered step 2 already.

## 3. The shape

Always, in this order:

1. **Hook.** One or two sentences, opening on something _timely_. Check today's
   date first and use it: the season, a holiday, the month, or a self-aware nod to
   the last release. `3.6.0` served Thanksgiving turkey, `3.10.0` opened on the
   summer heat, `3.7.0` on the new year, `4.9.0` on being the last `4.x`, `5.1.0`
   on arriving sooner than anyone expected. Then `@everyone` (if pinging), the
   version in backticks, and what the release is _about_. Never open cold with
   "version X is out". Keep the reference light and skip a holiday that is not
   widely shared, and do not assert a date you have not checked ("the equinox is
   today") when "the days are getting shorter" carries the same warmth.
2. **Any upgrade warning**, immediately after the hook. Imperative, and what to do,
   not why.
3. **The features**, in one of two shapes:
   - **Bullet list** for a release carried by a long tail (`5.1.0`, `4.3.0`): one
     sentence of setup, then five to nine bullets of three to six words each.
   - **`###` section per feature** for a release with two to five real headliners
     (`3.10.0`, `4.4.0`, `3.5.0`): a heading and two or three sentences, saying what
     it does and the one thing needed to use it. Close with an `Other notable
features:` bullet list when there is a tail.
4. **`## Community news`** (`### Community updates` also appears; match the last
   one). Team additions first, then app spotlights, then milestones and events, then
   housekeeping and calls to action.
5. **The pointer.** "More details on each of these features, and a complete list of
   changes, can be found in the [release notes](url)." Link the tag URL.
6. **Sign-off.** "See you soon!", optionally with `:mario_here_we_go:`.

## 4. Voice

- Second person, present tense, contractions. Talking to friends, not users.
- One idea per sentence, and short paragraphs. Nothing here is a manual.
- Enthusiasm is earned by specifics, not adjectives. Name the feature, don't call
  it revolutionary. No claim the release notes do not support.
- Emphasis is _italics_ on a single word, sparingly. Bold is for the thing that
  will break someone's install.
- Backticks for versions, env vars, config keys, filenames.
- Credit by name every time: the contributor for a feature, the author for an app.
- No em-dashes. No AI throat-clearing, no "we're excited to announce" twice in one
  post, no bullet list of benefits.

## 5. Discord mechanics

- **2000 characters**, hard. Past announcements run 1300 to 2100; treat 1800 as the
  target and count before handing over (`wc -m`).
- Over the limit, pick one: split at a section boundary into message 1 (hook plus
  features) and message 2 (community news plus sign-off), marking the split in the
  draft; or do what `3.7.0` did and post a three-line teaser pointing at the GitHub
  notes. Say which you did and why.
- `##`, `###`, `**bold**`, `*italics*`, `` `code` ``, `> quote`, `-`/`*` bullets and
  `[text](url)` all render. Tables, images and HTML do not.
- `@everyone` goes in the first sentence or not at all.
- Custom emoji only from ones this server is known to have:
  `:mario_here_we_go:` (the usual sign-off), `:linkEz:`, `:linkLove:`, `:peepoAlert:`,
  `:snakeSalute:`, `:excuseme:`, `:okay:`, `:linuxNootNoot:`. Anything else renders as
  literal text, so use plain unicode (🎊 👉 ⚠️ 🔥) instead of guessing a shortcode.
- Role pings (`@Expert`, `@Alpha Tester`, `@Beta Tester`) only when the user asked
  for them, spelled as they gave them.

## 6. Before handing it over

- Every feature named appears in the release notes.
- The hook opens on something timely, and the reference matches today's date.
- Every warning in the notes appears in the announcement.
- Every handle, repo URL and number came from the user or from the notes, never
  from you, and every URL is one you have actually seen.
- No app spotlighted in either of the last two announcements.
- The release notes link ends in the tag being announced.
- Under 2000 characters, or split deliberately.
- No em-dashes, no invented emoji shortcodes.

Write to `<scratchpad>/<tag>-announcement.md`, print it, and say what still needs a
human: a screenshot or GIF to attach, a link the user has not given you, a name you
could not confirm.
