import { describe, expect, it } from "vitest";
import { isCustomScheme } from "./pairCallback";

describe("isCustomScheme", () => {
  it.each(["argosy://pair", "myapp:callback?x=1"])("accepts %s", (url) => {
    expect(isCustomScheme(url)).toBe(true);
  });

  it.each([
    "https://evil.example/cb",
    "http://evil.example/cb",
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "blob:https://example.com/uuid",
    "file:///etc/passwd",
    "not a url",
  ])("rejects %s", (url) => {
    expect(isCustomScheme(url)).toBe(false);
  });
});
