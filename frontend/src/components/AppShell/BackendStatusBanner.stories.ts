import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { createPinia, setActivePinia } from "pinia";
import { provide, ref } from "vue";
import BackendStatusBanner from "./BackendStatusBanner.vue";
import {
  backendStatusBannerStoryKey,
  type BackendStatusBannerStoryState,
} from "./backendStatusBannerStoryKey";

function storyDecorator(state: BackendStatusBannerStoryState) {
  return () => ({
    setup() {
      provide(backendStatusBannerStoryKey, state);
      return {};
    },
    template: "<story />",
  });
}

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
  decorators: [
    storyDecorator({
      isOffline: ref(false),
      isWebSocketDegraded: ref(false),
      retryNow: () => {},
      retryWebSocket: () => {},
    }),
  ],
  render: () => ({
    components: { BackendStatusBanner },
    template: "<BackendStatusBanner />",
  }),
};

export const ServerOffline: Story = {
  decorators: [
    storyDecorator({
      isOffline: ref(true),
      isWebSocketDegraded: ref(false),
      retryNow: () => {},
      retryWebSocket: () => {},
    }),
  ],
  render: () => ({
    components: { BackendStatusBanner },
    template: "<BackendStatusBanner />",
  }),
};

export const WebSocketDegraded: Story = {
  decorators: [
    storyDecorator({
      isOffline: ref(false),
      isWebSocketDegraded: ref(true),
      retryNow: () => {},
      retryWebSocket: () => {},
    }),
  ],
  render: () => ({
    components: { BackendStatusBanner },
    template: "<BackendStatusBanner />",
  }),
};
