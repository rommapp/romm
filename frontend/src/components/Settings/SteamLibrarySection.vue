<script setup lang="ts">
// SteamLibrarySection: links a RomM account to a Steam account and imports
// the games it owns. The import runs as a task whose completion arrives as a
// notification, which also refreshes the owned count shown here.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import SettingsSection from "@/components/Settings/SettingsSection.vue";
import { useConfirm } from "@/composables/useConfirm";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RTag, RTextField } from "@/lib";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import useSteamLibrary from "@/stores/steamLibrary";
import { errorMessage } from "@/utils/errorMessage";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const auth = storeAuth();
const steamLibrary = useSteamLibrary();
const snackbar = useSnackbar();
const confirm = useConfirm();

const profile = ref("");
const linking = ref(false);
const syncing = ref(false);
const unlinking = ref(false);

const isLinked = computed(() => Boolean(auth.user?.steam_id));
const personaName = computed(
  () => auth.user?.steam_persona_name || auth.user?.steam_id || "",
);

async function startSync(id: number) {
  await userApi.syncSteamLibrary({ id });
  snackbar.info(t("settings.steam-sync-started"), { icon: "mdi-steam" });
}

async function link() {
  const user = auth.user;
  const value = profile.value.trim();
  if (!user || !value || linking.value) return;
  linking.value = true;
  try {
    const { data } = await userApi.linkSteamAccount({
      id: user.id,
      profile: value,
    });
    auth.setCurrentUser(data);
    profile.value = "";
  } catch (err) {
    snackbar.error(
      t("settings.steam-link-failed", { error: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
    return;
  } finally {
    linking.value = false;
  }

  syncing.value = true;
  try {
    await startSync(user.id);
  } catch (err) {
    snackbar.error(
      t("settings.steam-sync-failed", { error: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    syncing.value = false;
  }
}

async function sync() {
  if (!auth.user) return;
  syncing.value = true;
  try {
    await startSync(auth.user.id);
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
      <div class="r-steam__field">
        <RTextField
          v-model="profile"
          prefix-label="stacked"
          :hint="t('settings.steam-profile-hint')"
          @keyup.enter="link"
        >
          <template #prefix-label>{{ t("settings.steam-profile") }}</template>
        </RTextField>
      </div>
      <div class="r-steam__actions">
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-link-variant"
          :loading="linking || syncing"
          :disabled="!profile.trim()"
          @click="link"
        >
          {{ t("settings.steam-link") }}
        </RBtn>
      </div>
    </template>
  </SettingsSection>
</template>

<style scoped>
.r-steam__field {
  padding: 14px 16px;
}

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
