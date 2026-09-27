import { describe, expect, it } from "vitest";
import { providerImageUrl } from "./providerImage";

describe("providerImageUrl", () => {
  it("routes a remote provider image through the image proxy", () => {
    expect(
      providerImageUrl(
        "https://images.igdb.com/igdb/image/upload/t_cover_big/co1.jpg",
      ),
    ).toBe(
      "/api/search/image?url=https%3A%2F%2Fimages.igdb.com%2Figdb%2Fimage%2Fupload%2Ft_cover_big%2Fco1.jpg",
    );
  });

  it("encodes the query string so provider parameters survive", () => {
    const url =
      "https://neoclone.screenscraper.fr/api2/mediaJeu.php?devid=x&media=box-2D(us)";
    const proxied = providerImageUrl(url);

    expect(new URLSearchParams(proxied.split("?")[1]).get("url")).toBe(url);
  });

  it("leaves local and empty URLs untouched", () => {
    expect(providerImageUrl("/assets/default/cover.png")).toBe(
      "/assets/default/cover.png",
    );
    expect(providerImageUrl("data:image/png;base64,AAAA")).toBe(
      "data:image/png;base64,AAAA",
    );
    expect(providerImageUrl("")).toBe("");
  });
});
