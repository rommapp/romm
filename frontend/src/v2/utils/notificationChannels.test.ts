import { describe, expect, it } from "vitest";
import {
  appriseFieldsPayload,
  initialAppriseValues,
  missingAppriseLists,
} from "./notificationChannels";
import { makeAppriseService } from "./notificationChannels.fixtures";

const service = makeAppriseService();

describe("initialAppriseValues", () => {
  it("starts from the service's defaults", () => {
    expect(initialAppriseValues(service)).toEqual({
      schema: "ntfys",
      host: "",
      port: "",
      token: "",
      targets: [],
      image: true,
      priority: "default",
    });
  });

  it("puts in what the channel already has, numbers as text", () => {
    const values = initialAppriseValues(service, { port: 8080, image: false });

    expect(values).toMatchObject({ port: "8080", image: false });
  });
});

describe("appriseFieldsPayload", () => {
  it("sends what was filled in, numbers as numbers, defaults left out", () => {
    const values = {
      ...initialAppriseValues(service),
      host: "ntfy.example.com",
      port: "8080",
      targets: ["romm"],
      priority: "high",
    };

    expect(appriseFieldsPayload(service, values)).toEqual({
      host: "ntfy.example.com",
      port: 8080,
      targets: ["romm"],
      priority: "high",
    });
  });

  it("sends a secret the form removes as empty", () => {
    const values = initialAppriseValues(service);

    expect(appriseFieldsPayload(service, values, ["token"])).toEqual({
      token: "",
    });
  });

  it("keeps a switch turned away from its default", () => {
    const values = { ...initialAppriseValues(service), image: false };

    expect(appriseFieldsPayload(service, values)).toEqual({ image: false });
  });
});

describe("missingAppriseLists", () => {
  it("names the required lists left empty", () => {
    const values = initialAppriseValues(service);

    expect(missingAppriseLists(service, values)).toEqual(["targets"]);
    expect(
      missingAppriseLists(service, { ...values, targets: ["romm"] }),
    ).toEqual([]);
  });

  it("lets a secret list the channel already has stay empty", () => {
    const values = initialAppriseValues(service);

    expect(missingAppriseLists(service, values, ["targets"])).toEqual([]);
  });
});
