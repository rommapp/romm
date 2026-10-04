<script setup lang="ts">
// InviteLinkDialog: v2-native rebuild of v1
// `Settings/Administration/Users/Dialog/InviteLink.vue`. Picks a role +
// expiry, generates an invite URL, and shows it in a copyable field.
import { RBtn, RIcon, RSelect, RSliderBtnGroup } from "@v2/lib";
import type { SliderBtnGroupItem } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import { getRoleIcon } from "@/utils";
import { useClipboard } from "@/v2/composables/useClipboard";
import { useEmitterEvent } from "@/v2/composables/useEmitterEvent";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const snackbar = useSnackbar();
const clipboard = useClipboard();

const show = ref(false);
const generating = ref(false);
const fullInviteLink = ref("");
const selectedRole = ref<string | null>(null);
const selectedExpiration = ref<number>(86400);

const roleItems = computed<SliderBtnGroupItem<string>[]>(() =>
  ["admin", "user"].map((role) => ({
    id: role,
    label: t(`settings.role-${role}`),
    icon: getRoleIcon(role),
  })),
);
const expirationOptions = computed(() => [
  { title: t("settings.expiry-1h"), value: 3600 },
  { title: t("settings.expiry-6h"), value: 21600 },
  { title: t("settings.expiry-12h"), value: 43200 },
  { title: t("settings.expiry-1d"), value: 86400 },
  { title: t("settings.expiry-3d"), value: 259200 },
  { title: t("settings.expiry-7d"), value: 604800 },
  { title: t("settings.expiry-30d"), value: 2592000 },
]);

useEmitterEvent("showCreateInviteLinkDialog", () => {
  selectedRole.value = null;
  selectedExpiration.value = 86400;
  fullInviteLink.value = "";
  show.value = true;
});

async function createInviteLink() {
  if (!selectedRole.value) return;
  generating.value = true;
  try {
    const { data } = await userApi.createInviteLink({
      role: selectedRole.value,
      expiration: selectedExpiration.value,
    });
    // The backend builds the link from ROMM_BASE_URL so it stays shareable when
    // generated from localhost. It omits it when ROMM_BASE_URL is unset or non-public.
    fullInviteLink.value =
      data.url ?? `${window.location.origin}/register?token=${data.token}`;
    snackbar.success(t("settings.invite-link-created"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.unable-to-create-invite-link", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    generating.value = false;
  }
}

async function copyLink() {
  await clipboard.copy(fullInviteLink.value, {
    successMessage: t("settings.link-copied"),
  });
}

function close() {
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-share-variant"
    :width="540"
    cancelable
    @close="close"
  >
    <template #header>
      <span class="r-v2-invite__title">{{ t("settings.invite-link") }}</span>
    </template>
    <template #content>
      <div class="r-v2-invite__field">
        <span class="r-v2-invite__label">{{ t("settings.role") }}</span>
        <RSliderBtnGroup
          v-model="selectedRole"
          :items="roleItems"
          variant="tab"
          :aria-label="t('settings.role')"
          class="r-v2-invite__roles"
        />
      </div>

      <div class="r-v2-invite__field">
        <RSelect
          v-model="selectedExpiration"
          :items="expirationOptions"
          :label="t('settings.expires-in')"
          variant="outlined"
          density="comfortable"
          hide-details
        />
      </div>

      <div v-if="fullInviteLink" class="r-v2-invite__link">
        <code>{{ fullInviteLink }}</code>
        <button
          type="button"
          class="r-v2-invite__copy-btn"
          :aria-label="t('settings.copy-link')"
          @click="copyLink"
        >
          <RIcon icon="mdi-content-copy" size="14" />
        </button>
      </div>
    </template>
    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        :loading="generating"
        :disabled="!selectedRole"
        prepend-icon="mdi-link-variant"
        @click="createInviteLink"
      >
        {{ t("common.generate") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-invite__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-invite__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-invite__label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
.r-v2-invite__roles {
  align-self: flex-start;
}
.r-v2-invite__link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  font-family: var(--r-font-family-mono, monospace);
  overflow: hidden;
}
.r-v2-invite__link code {
  flex: 1;
  font-size: 12px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-invite__copy-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--r-color-brand-primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-invite__copy-btn:hover {
  background: var(--r-color-surface-hover);
}
</style>
