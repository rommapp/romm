import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { createPinia, setActivePinia } from "pinia";
import storeHeartbeat from "@/stores/heartbeat";
import BackendStatusBanner from "./BackendStatusBanner.vue";

const meta: Meta<typeof BackendStatusBanner> = {
  title: "AppShell/BackendStatusBanner",
  component: BackendStatusBanner,
  decorators: [
    () => {
      setActivePinia(createPinia());
      return { template: "<story />" };
    },
  ],
};

export default meta;
type Story = StoryObj<typeof BackendStatusBanner>;

export const Healthy: Story = {
  render: () => ({
    components: { BackendStatusBanner },
    setup() {
      storeHeartbeat().setConnected(true);
      return {};
    },
    template: "<BackendStatusBanner />",
  }),
};

export const ServerOffline: Story = {
  render: () => ({
    components: { BackendStatusBanner },
    setup() {
      storeHeartbeat().setConnected(false);
      return {};
    },
    template: "<BackendStatusBanner />",
  }),
};
