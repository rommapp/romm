import { defineStore } from "pinia";

import type { ConfigResponse } from "@/__generated__";

export default defineStore("config", {
  state: () => {
    return { value: {} as ConfigResponse };
  },

  actions: {
    set(data: ConfigResponse) {
      this.value = data;
    },
    addPlatformBinding(fsSlug: string, slug: string) {
      this.value.PLATFORMS_BINDING[fsSlug] = slug;
    },
    removePlatformBinding(fsSlug: string) {
      delete this.value.PLATFORMS_BINDING[fsSlug];
    },
  },
});
