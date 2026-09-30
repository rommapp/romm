import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import { userFixture } from "@/utils/user.fixtures";
import StreamInstallSection from "@/v2/components/Settings/StreamInstallSection.vue";
import type { ProtonBuildExtended } from "@/services/api/install";
import { installCache, protonBuilds } from "@/v2/utils/install.fixtures";
import { mockApi } from "@/v2/utils/mockApi.fixtures";
import type { MockRoute } from "@/v2/utils/mockApi.fixtures";

const ADMIN_SCOPES = ["platforms.write", "roms.install"];

function routes(builds: ProtonBuildExtended[] = protonBuilds): MockRoute[] {
  return [
    {
      url: "/config",
      data: () => ({
        ...storeConfig().config,
        CONFIG_FILE_WRITABLE: true,
        INSTALL_DEFAULT_PROTON_BUILD: "proton-cachyos",
        INSTALL_CACHE_TTL_DAYS: 7,
      }),
    },
    { url: "/roms/install/proton-builds", data: { builds } },
    { url: "/roms/install/cache", data: installCache },
    {
      method: "post",
      url: /^\/roms\/install\/proton\/[^/]+\/download$/,
      data: { job_id: "job-1" },
    },
    {
      url: /^\/roms\/install\/proton\/[^/]+\/progress$/,
      data: { progress: 0.42, extracting: false },
    },
  ];
}

// Scopes live on the signed-in user, so each story seeds one before mounting.
function renderAs(scopes: string[]) {
  return () => ({
    components: { StreamInstallSection },
    setup() {
      storeAuth().user = userFixture({ oauth_scopes: scopes });
    },
    template: `<div style="width: 720px"><StreamInstallSection /></div>`,
  });
}

const meta: Meta<typeof StreamInstallSection> = {
  title: "Settings/StreamInstallSection",
  component: StreamInstallSection,
  parameters: { layout: "padded" },
};

export default meta;
type Story = StoryObj<typeof StreamInstallSection>;

export const Admin: Story = {
  render: renderAs(ADMIN_SCOPES),
  beforeEach: () => mockApi(routes()),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByRole("button", { name: "Download" }),
    ).toBeEnabled();
    await expect(canvas.getByLabelText("Speed limit")).toBeEnabled();
  },
};

export const Viewer: Story = {
  render: renderAs([]),
  beforeEach: () => mockApi(routes()),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      await canvas.findByRole("button", { name: "Download" }),
    ).toBeDisabled();
    await expect(canvas.getByLabelText("Speed limit")).toBeDisabled();
  },
};

export const NoBuilds: Story = {
  render: renderAs(ADMIN_SCOPES),
  beforeEach: () => mockApi(routes([])),
  play: async ({ canvasElement }) => {
    await expect(
      await within(canvasElement).findByText(
        "No Proton builds are installed yet. Download one below to get started.",
      ),
    ).toBeVisible();
  },
};

export const UnsavedChanges: Story = {
  render: renderAs(ADMIN_SCOPES),
  beforeEach: () => mockApi(routes()),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const field = await canvas.findByLabelText("Speed limit");
    // Disabled until the config has loaded.
    await waitFor(() => expect(field).toBeEnabled());
    await userEvent.type(field, "500");
    await expect(
      await canvas.findByText("You have unsaved changes"),
    ).toBeVisible();
    await userEvent.click(canvas.getByRole("button", { name: "Discard" }));
    await expect(field).toHaveValue(null);
  },
};

export const DownloadingBuild: Story = {
  render: renderAs(ADMIN_SCOPES),
  beforeEach: () => mockApi(routes()),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      await canvas.findByRole("button", { name: "Download" }),
    );
    // The first progress poll lands after the 2s poll interval.
    const ring = await canvas.findByRole(
      "progressbar",
      { name: "Downloading… 42%" },
      { timeout: 4000 },
    );
    await expect(ring).toHaveAttribute("aria-valuenow", "42");
  },
};
