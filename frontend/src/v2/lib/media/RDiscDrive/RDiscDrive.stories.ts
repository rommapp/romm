import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";
import RDiscDrive from "./RDiscDrive.vue";

// Self-contained SVG fixture so the story needs no network. Named colours (no
// hex literals) keep it within the v2 colour policy.
const discArt = `data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">` +
    `<rect width="100%" height="100%" fill="gainsboro"/>` +
    `<circle cx="200" cy="200" r="200" fill="silver"/>` +
    `<circle cx="200" cy="200" r="150" fill="steelblue"/>` +
    `<circle cx="200" cy="200" r="70" fill="silver"/>` +
    `<text x="200" y="120" fill="white" font-family="sans-serif" font-size="34" ` +
    `text-anchor="middle" dominant-baseline="middle">SILENT HILL</text></svg>`,
)}`;

const meta: Meta<typeof RDiscDrive> = {
  title: "Media/RDiscDrive",
  component: RDiscDrive,
  argTypes: {
    disc: { control: "text" },
    alt: { control: "text" },
    ejectLabel: { control: "text" },
    trayLabel: { control: "text" },
    accent: { control: "text" },
    autoSpin: { control: "boolean" },
    muted: { control: "boolean" },
  },
  args: {
    disc: discArt,
    alt: "Silent Hill",
    autoSpin: true,
    // Muted by default so the test runner and a casual browse stay quiet;
    // flip the control (or open "With sound") to hear the drive.
    muted: true,
  },
  render: (args) => ({
    components: { RDiscDrive },
    setup: () => ({ args }),
    template: `
      <div style="width:340px;padding:24px;background:var(--r-color-bg)">
        <RDiscDrive v-bind="args" />
      </div>
    `,
  }),
};

export default meta;

type Story = StoryObj<typeof RDiscDrive>;

// ── Default: eject, drag the disc into the well, push the tray shut ──
export const Default: Story = {};

// ── Sound on: synthesised servo, clunk, seat and spin-up ──
export const WithSound: Story = {
  name: "With sound",
  args: { muted: false },
};

// ── A platform-tinted drive (the accent drives trim and the LED) ──
export const Accented: Story = {
  name: "Platform accent",
  args: { accent: "var(--r-color-romm-green)" },
};

// ── Tray out, waiting for a disc ──
export const TrayOpen: Story = {
  name: "Tray open",
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole("button", { name: "Eject" }));
    const drive = canvasElement.querySelector(".r-disc-drive");
    await waitFor(() => expect(drive).toHaveClass("r-disc-drive--open"));
  },
};

// ── Interaction: the whole sequence on the keyboard alone, which is what a
//    gamepad emits. If this passes, the egg is completable from the couch. ──
export const KeyboardLoad: Story = {
  name: "Keyboard / gamepad load",
  args: { onLoaded: fn() },
  play: async ({ canvasElement, args, step }) => {
    const canvas = within(canvasElement);
    const drive = canvasElement.querySelector(".r-disc-drive");
    expect(drive).not.toBeNull();

    await step("eject pops the tray", async () => {
      await userEvent.click(canvas.getByRole("button", { name: "Eject" }));
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--open"));
    });

    await step("arrows walk the disc down into the well", async () => {
      const disc = canvas.getByRole("button", { name: "Silent Hill" });
      disc.focus();
      for (let i = 0; i < 6; i++) await userEvent.keyboard("{ArrowDown}");
      await userEvent.keyboard("{Enter}");
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--seated"), {
        timeout: 3000,
      });
    });

    await step("confirm on the tray shuts it and the drive reads", async () => {
      canvas.getByRole("button", { name: "Disc tray" }).focus();
      await userEvent.keyboard("{Enter}");
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--ready"), {
        timeout: 6000,
      });
      expect(args.onLoaded).toHaveBeenCalledTimes(1);
    });
  },
};

// ── Closing an empty tray is the joke: the drive rejects and spits it back ──
export const EmptyReject: Story = {
  name: "Closed empty (rejects)",
  args: { onRejected: fn() },
  play: async ({ canvasElement, args, step }) => {
    const canvas = within(canvasElement);
    const drive = canvasElement.querySelector(".r-disc-drive");

    await step("open, then shut it with nothing in it", async () => {
      await userEvent.click(canvas.getByRole("button", { name: "Eject" }));
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--open"));
      await userEvent.click(canvas.getByRole("button", { name: "Eject" }));
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--error"), {
        timeout: 3000,
      });
      expect(args.onRejected).toHaveBeenCalledTimes(1);
    });

    await step("the tray comes back out on its own", async () => {
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--open"), {
        timeout: 4000,
      });
    });
  },
};

// ── Ejecting a loaded drive brings the disc back out on the tray ──
export const EjectLoaded: Story = {
  name: "Eject a loaded drive",
  render: (args) => ({
    components: { RDiscDrive },
    setup: () => ({ args }),
    template: `
      <div style="width:340px;padding:24px;background:var(--r-color-bg)">
        <RDiscDrive ref="drive" v-bind="args" />
        <button data-testid="load" @click="$refs.drive.skip()">Load</button>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const drive = canvasElement.querySelector(".r-disc-drive");

    await step("a loaded drive is holding the disc", async () => {
      await userEvent.click(canvas.getByTestId("load"));
      await waitFor(() => expect(drive).toHaveClass("r-disc-drive--ready"));
    });

    await step(
      "eject returns it to the tray rather than emptying",
      async () => {
        await userEvent.click(canvas.getByRole("button", { name: "Eject" }));
        await waitFor(() => expect(drive).toHaveClass("r-disc-drive--seated"));
        expect(
          canvasElement.querySelector(".r-disc-drive__disc--seated"),
        ).not.toBeNull();
      },
    );
  },
};

// ── The escape hatch: skip() reports the disc read with no performance ──
export const Skipped: Story = {
  name: "Skip straight to loaded",
  args: { onLoaded: fn() },
  render: (args) => ({
    components: { RDiscDrive },
    setup: () => ({ args }),
    template: `
      <div style="width:340px;padding:24px;background:var(--r-color-bg)">
        <RDiscDrive ref="drive" v-bind="args" />
        <button data-testid="skip" @click="$refs.drive.skip()">Skip</button>
      </div>
    `,
  }),
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    const drive = canvasElement.querySelector(".r-disc-drive");
    await userEvent.click(canvas.getByTestId("skip"));
    await waitFor(() => expect(drive).toHaveClass("r-disc-drive--ready"));
    expect(args.onLoaded).toHaveBeenCalledTimes(1);
  },
};
