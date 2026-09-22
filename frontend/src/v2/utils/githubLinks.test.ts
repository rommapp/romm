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
    const notes = [`[the fix](${PR})`, `[${PR}](${PR})`, `<${PR}>`].join("\n");

    expect(shortenGithubLinks(notes, REPO)).toBe(notes);
  });

  it("leaves a deeper page of a pull request alone", () => {
    const notes = [
      `${PR}/files`,
      `${PR}#issuecomment-1`,
      "https://github.com/rommapp/romm/compare/5.0.0...5.1.0",
    ].join("\n");

    expect(shortenGithubLinks(notes, REPO)).toBe(notes);
  });
});
