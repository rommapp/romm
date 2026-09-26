import type { ComputedRef, InjectionKey, Ref } from "vue";

/** Storybook-only injection to avoid live heartbeat/socket installs in stories. */
export interface BackendStatusBannerStoryState {
  isOffline: Ref<boolean> | ComputedRef<boolean>;
  isWebSocketDegraded: Ref<boolean> | ComputedRef<boolean>;
  retryNow: () => void | Promise<void>;
  retryWebSocket: () => void;
}

export const backendStatusBannerStoryKey: InjectionKey<BackendStatusBannerStoryState> =
  Symbol("backendStatusBannerStory");
