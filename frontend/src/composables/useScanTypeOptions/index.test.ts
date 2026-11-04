import { describe, expect, it, vi } from "vitest";
import { useScanTypeOptions } from "./index";

vi.mock("vue-i18n");

describe("useScanTypeOptions", () => {
  it("lists every scan type, discovery first, each with its description", () => {
    const options = useScanTypeOptions().value;

    expect(options.map((o) => o.value)).toEqual([
      "new_platforms",
      "quick",
      "unmatched",
      "update",
      "hashes",
      "complete",
    ]);
    expect(options[1]).toEqual({
      title: "scan.quick-scan",
      subtitle: "scan.quick-scan-desc",
      value: "quick",
    });
  });
});
