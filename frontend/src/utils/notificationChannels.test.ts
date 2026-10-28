import { describe, expect, it } from "vitest";
import {
  appriseFieldsPayload,
  initialAppriseValues,
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
  it("sends what was filled in, numbers as numbers", () => {
    const values = {
      ...initialAppriseValues(service),
      host: "ntfy.example.com",
      port: "8080",
      targets: ["romm"],
    };

    expect(appriseFieldsPayload(service, values)).toEqual({
      schema: "ntfys",
      host: "ntfy.example.com",
      port: 8080,
      targets: ["romm"],
      image: true,
      priority: "default",
    });
  });

  it("sends a secret the form removes as empty", () => {
    const values = initialAppriseValues(service);

    expect(appriseFieldsPayload(service, values, ["token"])).toMatchObject({
      token: "",
    });
  });
});
