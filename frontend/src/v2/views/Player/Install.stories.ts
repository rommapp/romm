import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, within } from "storybook/test";
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/routeNames";
import storeAuth from "@/stores/auth";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import {
  makeCandidates,
  makeInstallSession,
  makeManifest,
  protonBuilds,
} from "@/v2/utils/install.fixtures";
import { mockApi } from "@/v2/utils/mockApi.fixtures";
import type { MockRoute } from "@/v2/utils/mockApi.fixtures";
import Install from "@/v2/views/Player/Install.vue";

const rom = makeDetailedRom({
  id: 1,
  name: "Example Game",
  platform_slug: "win",
});

function routes(session: MockRoute): MockRoute[] {
  return [
    { url: "/roms/1", data: rom },
    session,
    { url: "/roms/install/worker-status", data: { available: true } },
    { url: "/roms/1/install/candidates", data: makeCandidates() },
    { url: "/roms/install/proton-builds", data: { builds: protonBuilds } },
    { url: "/roms/1/install/stream/manifest", data: makeManifest() },
    {
      url: /^\/roms\/install\/proton\/[^/]+\/progress$/,
      data: { progress: 0.42, extracting: false },
    },
  ];
}

// The page reads the ROM id from the route, and Storybook's router is a
// catch-all with no params, so register the real route and wait for it.
const render = () => ({
  components: { Install },
  setup() {
    storeAuth().user = userFixture({ oauth_scopes: ["roms.install"] });
    const router = useRouter();
    const ready = ref(false);
    router.addRoute({
      path: "/rom/:rom/install",
      name: ROUTES.INSTALL,
      component: Install,
    });
    router.replace("/rom/1/install").then(() => (ready.value = true));
    return { ready };
  },
  template: `<div style="height: 720px; display: flex"><Install v-if="ready" /></div>`,
});

const meta: Meta<typeof Install> = {
  title: "Player/Install",
  component: Install,
  parameters: { layout: "fullscreen" },
  render,
};

export default meta;
type Story = StoryObj<typeof Install>;

export const ReadyToInstall: Story = {
  beforeEach: () =>
    mockApi(routes({ url: "/roms/1/install", status: 404, data: {} })),
  play: async ({ canvasElement }) => {
    // The stage and the sidebar each offer the same "Install" action.
    const buttons = await within(canvasElement).findAllByRole("button", {
      name: "Install",
    });
    for (const button of buttons) await expect(button).toBeEnabled();
  },
};

export const DownloadingProton: Story = {
  beforeEach: () =>
    mockApi(
      routes({
        url: "/roms/1/install",
        data: makeInstallSession("installing", {
          proton_build: "ge-proton-9",
          vnc_url: null,
        }),
      }),
    ),
  play: async ({ canvasElement }) => {
    const bar = await within(canvasElement).findByRole("progressbar", {
      name: /Downloading Proton/,
    });
    await expect(bar).toHaveAttribute("aria-valuenow", "42");
  },
};

// The page fetches nothing else until the ROM arrives.
export const Loading: Story = {
  beforeEach: () => mockApi([{ url: "/roms/1", pending: true }]),
  play: async ({ canvasElement }) => {
    await expect(
      await within(canvasElement).findByRole("progressbar", {
        name: "Loading",
      }),
    ).toBeInTheDocument();
  },
};
