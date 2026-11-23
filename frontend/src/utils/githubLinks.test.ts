import { describe, expect, it } from "vitest";
import { shortenGithubLinks } from "./githubLinks";

const REPO = "rommapp/romm";
const PR = "https://github.com/rommapp/romm/pull/4654";

describe("shortenGithubLinks", () => {
  it("shortens a pull request to its number", () => {
    expect(
      shortenGithubLinks(`* Fix the list by @contributor in ${PR}`, REPO),
    ).toBe(`* Fix the list by @contributor in [#4654](${PR})`);
  });

  it("shortens an issue the same way", () => {
    const issue = "https://github.com/rommapp/romm/issues/942";

    expect(shortenGithubLinks(`Fixes ${issue}`, REPO)).toBe(
      `Fixes [#942](${issue})`,
    );
  });

  it("keeps the repository on another repository's reference", () => {
    const other = "https://github.com/RetroRealm/playmatch/pull/12";

    expect(shortenGithubLinks(other, REPO)).toBe(
      `[RetroRealm/playmatch#12](${other})`,
    );
  });

  it("reads the repository without regard to case", () => {
    const shouting = "https://github.com/RommApp/RomM/pull/7";

    expect(shortenGithubLinks(shouting, REPO)).toBe(`[#7](${shouting})`);
  });

  it("shortens every reference on a line", () => {
    const second = "https://github.com/rommapp/romm/pull/4655";

    expect(shortenGithubLinks(`${PR} and ${second}`, REPO)).toBe(
      `[#4654](${PR}) and [#4655](${second})`,
    );
  });

  // Rewriting these would nest a link inside a link.
  it("leaves a reference that is already a link alone", () => {
    const notes = [
      `[the fix](${PR})`,
      `[${PR}](${PR})`,
      `[see ${PR} for the details](${PR})`,
      `<${PR}>`,
    ].join("\n");

    expect(shortenGithubLinks(notes, REPO)).toBe(notes);
  });

  // Code reads as written, so a rewrite would show the markdown itself.
  it("leaves a reference inside code alone", () => {
    const notes = [
      `Compare it with \`${PR}\`:`,
      "```sh",
      `curl ${PR}`,
      "```",
    ].join("\n");

    expect(shortenGithubLinks(notes, REPO)).toBe(notes);
  });

  it("leaves a deeper page of a pull request alone", () => {
    const notes = [
      `${PR}/files`,
      `${PR}#issuecomment-1`,
      `${PR}?diff=split`,
      "https://github.com/rommapp/romm/compare/5.0.0...5.1.0",
    ].join("\n");

    expect(shortenGithubLinks(notes, REPO)).toBe(notes);
  });

  // Without the caps on the link label and target this takes ~2s, four times
  // that for twice the text: every unclosed bracket scans what follows it.
  it("does not slow to a crawl on a flood of unclosed brackets", () => {
    const notes = "[x".repeat(50_000);

    const started = performance.now();
    shortenGithubLinks(notes, REPO);

    expect(performance.now() - started).toBeLessThan(1_000);
  });
});
