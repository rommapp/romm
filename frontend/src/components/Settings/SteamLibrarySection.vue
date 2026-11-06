<script setup lang="ts">
// SteamLibrarySection: links a RomM account to a Steam account and imports
// the games it owns. The import runs as a task whose completion arrives as a
// notification, which also refreshes the owned count shown here.
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import SettingsSection from "@/components/Settings/SettingsSection.vue";
import { useConfirm } from "@/composables/useConfirm";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RTag } from "@/lib";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import useSteamLibrary from "@/stores/steamLibrary";
import { errorMessage } from "@/utils/errorMessage";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = storeAuth();
const steamLibrary = useSteamLibrary();
const snackbar = useSnackbar();
const confirm = useConfirm();

const linking = ref(false);
const syncing = ref(false);
const unlinking = ref(false);

const isLinked = computed(() => Boolean(auth.user?.steam_id));
const personaName = computed(
  () => auth.user?.steam_persona_name || auth.user?.steam_id || "",
);

// The sign-in happens on Steam's site, so its outcome comes back in the query
// rather than in a reply this component awaited.
onMounted(() => {
  const failure = route.query.steam_error;
  if (typeof failure === "string" && failure) {
    snackbar.error(t("settings.steam-link-failed", { error: failure }), {
      icon: "mdi-close-circle",
    });
  }
  if ("steam_error" in route.query || "steam" in route.query) {
    const query = { ...route.query };
    delete query.steam_error;
    delete query.steam;
    void router.replace({ query });
  }
});

// Steam signs the user in on its own site, then returns to `next`, so this
// hands the browser over rather than awaiting a reply.
async function link() {
  const user = auth.user;
  if (!user || linking.value) return;
  linking.value = true;
  try {
    const { data } = await userApi.startSteamLogin({
      id: user.id,
      next: route.fullPath,
    });
    window.location.assign(data.url);
  } catch (err) {
    linking.value = false;
    snackbar.error(
      t("settings.steam-link-failed", { error: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  }
}

async function sync() {
  const user = auth.user;
  if (!user || syncing.value) return;
  syncing.value = true;
  try {
    await userApi.syncSteamLibrary({ id: user.id });
    snackbar.info(t("settings.steam-sync-started"), { icon: "mdi-steam" });
  } catch (err) {
    snackbar.error(
      t("settings.steam-sync-failed", { error: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    syncing.value = false;
  }
}

async function unlink() {
  const user = auth.user;
  if (!user) return;
  const ok = await confirm({
    title: t("settings.steam-unlink-title"),
    body: t("settings.steam-unlink-confirm"),
    confirmText: t("settings.steam-unlink"),
    tone: "danger",
  });
  if (!ok) return;
  unlinking.value = true;
  try {
    const { data } = await userApi.unlinkSteamAccount({ id: user.id });
    auth.setCurrentUser(data);
  } catch (err) {
    snackbar.error(
      t("settings.steam-unlink-failed", { error: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    unlinking.value = false;
  }
}
</script>

<template>
  <SettingsSection :title="t('settings.steam')" icon="mdi-steam">
    <template #header-actions>
      <RTag
        :icon="isLinked ? 'mdi-link-variant' : 'mdi-link-variant-off'"
        :tone="isLinked ? 'success' : 'neutral'"
        size="small"
      >
        {{
          isLinked
            ? t("settings.steam-connected", { name: personaName })
            : t("settings.steam-not-linked")
        }}
      </RTag>
    </template>

    <template v-if="isLinked">
      <p class="r-steam__summary">
        {{
          steamLibrary.isLoaded
            ? t("settings.steam-owned-count", steamLibrary.count, {
                named: { n: steamLibrary.count },
              })
            : t("settings.steam-library-hint")
        }}
      </p>
      <div class="r-steam__actions">
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-sync"
          :loading="syncing"
          :disabled="unlinking"
          @click="sync"
        >
          {{ t("common.sync") }}
        </RBtn>
        <RBtn
          variant="text"
          color="danger"
          prepend-icon="mdi-link-variant-off"
          :loading="unlinking"
          :disabled="syncing"
          @click="unlink"
        >
          {{ t("settings.steam-unlink") }}
        </RBtn>
      </div>
    </template>

    <template v-else>
      <p class="r-steam__summary">{{ t("settings.steam-sign-in-hint") }}</p>
      <div class="r-steam__actions">
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-steam"
          :loading="linking"
          @click="link"
        >
          {{ t("settings.steam-sign-in") }}
        </RBtn>
      </div>
    </template>
  </SettingsSection>
</template>

<style scoped>
.r-steam__summary {
  margin: 0;
  padding: 14px 16px;
  color: var(--r-color-fg-muted);
}

.r-steam__actions {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid var(--r-color-border);
}
</style>
