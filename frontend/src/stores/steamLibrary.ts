import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import type { NotificationSchema } from "@/__generated__";
import { useSocketEvent } from "@/composables/useSocketEvent";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { STEAM_LIBRARY_SYNC_TASK } from "@/utils/tasks";

/** The Steam apps the current user's linked account owned at its last sync. */
const useSteamLibrary = defineStore("steamLibrary", () => {
  const auth = storeAuth();
  const ownedAppIds = ref<Set<number>>(new Set());
  // The account `ownedAppIds` describes, so a stale list never answers for a
  // newly linked one.
  const loadedFor = ref<string | null>(null);

  const account = computed(() =>
    auth.user?.steam_id ? `${auth.user.id}:${auth.user.steam_id}` : null,
  );
  const isLoaded = computed(
    () => account.value !== null && loadedFor.value === account.value,
  );
  const count = computed(() => ownedAppIds.value.size);

  function owns(appId: number): boolean {
    return ownedAppIds.value.has(appId);
  }

  async function load() {
    const user = auth.user;
    const requested = account.value;
    if (!user || !requested) return;
    try {
      const { data } = await userApi.fetchSteamLibrary({ id: user.id });
      if (account.value !== requested) return;
      ownedAppIds.value = new Set(data);
      loadedFor.value = requested;
    } catch (error) {
      console.error("Error fetching the Steam library: ", error);
    }
  }

  function reset() {
    ownedAppIds.value = new Set();
    loadedFor.value = null;
  }

  watch(
    account,
    (next) => {
      reset();
      if (next) void load();
    },
    { immediate: true },
  );

  // The notification inbox owns the connection; this only listens on it.
  useSocketEvent<NotificationSchema>(
    "notifications:new",
    (notification) => {
      if (
        notification.kind === "task_completed" &&
        notification.data.task === STEAM_LIBRARY_SYNC_TASK
      ) {
        void load();
      }
    },
    { connect: false },
  );

  return { ownedAppIds, isLoaded, count, owns, load, reset };
});

export default useSteamLibrary;
