import { describe, expect, it } from "vitest";
import { parseSceneId } from "./sceneIds";

describe("parseSceneId", () => {
  it("accepts a bare number", () => {
    expect(parseSceneId("108", "demozoo")).toBe(108);
    expect(parseSceneId(63, "pouet")).toBe(63);
    expect(parseSceneId("75330", "csdb")).toBe(75330);
  });

  it("parses Demozoo production URLs", () => {
    expect(
      parseSceneId("https://demozoo.org/productions/108/", "demozoo"),
    ).toBe(108);
    expect(
      parseSceneId("https://www.demozoo.org/productions/108", "demozoo"),
    ).toBe(108);
    expect(
      parseSceneId("https://demozoo.org/api/v1/productions/108/", "demozoo"),
    ).toBe(108);
  });

  it("parses Pouët prod.php URLs", () => {
    expect(
      parseSceneId("https://www.pouet.net/prod.php?which=63", "pouet"),
    ).toBe(63);
    expect(
      parseSceneId("https://pouet.net/prod.php?which=106640&watch=1", "pouet"),
    ).toBe(106640);
  });

  it("parses CSDb release URLs", () => {
    expect(parseSceneId("https://csdb.dk/release/?id=75330", "csdb")).toBe(
      75330,
    );
    expect(parseSceneId("https://www.csdb.dk/release/75330", "csdb")).toBe(
      75330,
    );
  });

  it("does not take another site's id for the wrong field", () => {
    expect(
      parseSceneId("https://demozoo.org/productions/108/", "pouet"),
    ).toBeNull();
    expect(
      parseSceneId("https://www.pouet.net/prod.php?which=63", "demozoo"),
    ).toBeNull();
    expect(parseSceneId("https://csdb.dk/release/?id=1", "demozoo")).toBeNull();
  });

  it("returns null for empty or garbage", () => {
    expect(parseSceneId("", "demozoo")).toBeNull();
    expect(parseSceneId("   ", "pouet")).toBeNull();
    expect(parseSceneId(null, "csdb")).toBeNull();
    expect(parseSceneId("https://example.com/108", "demozoo")).toBeNull();
  });
});
