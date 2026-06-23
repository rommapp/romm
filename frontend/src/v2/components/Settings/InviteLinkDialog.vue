<script setup lang="ts">
// InviteLinkDialog — v2-native rebuild of v1
// `Settings/Administration/Users/Dialog/InviteLink.vue`. Picks a role +
// expiry, generates an invite URL, and shows it in a copyable field.
import { RBtn, RIcon, RSelect } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import type { Events } from "@/types/emitter";
import { getRoleIcon } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const show = ref(false);
const generating = ref(false);
const fullInviteLink = ref("");
const selectedRole = ref<string | null>(null);
const selectedExpiration = ref<number>(86400);

const roles = ["viewer", "editor", "admin"];
const expirationOptions = computed(() => [
  { title: t("settings.expiry-1h"), value: 3600 },
  { title: t("settings.expiry-6h"), value: 21600 },
  { title: t("settings.expiry-12h"), value: 43200 },
  { title: t("settings.expiry-1d"), value: 86400 },
  { title: t("settings.expiry-3d"), value: 259200 },
  { title: t("settings.expiry-7d"), value: 604800 },
  { title: t("settings.expiry-30d"), value: 2592000 },
]);

emitter?.on("showCreateInviteLinkDialog", () => {
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
    fullInviteLink.value = `${window.location.origin}/register?token=${data.token}`;
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
  try {
    await navigator.clipboard.writeText(fullInviteLink.value);
    snackbar.success(t("settings.link-copied"), { icon: "mdi-check-bold" });
  } catch {
    /* clipboard unavailable */
  }
}

function close() {
  show.value = false;
}
</script>

<template>
  <RDialog v-model="show" icon="mdi-share-variant" :width="540" @close="close">
    <template #header>
      <span class="r-v2-invite__title">{{ t("settings.invite-link") }}</span>
    </template>
    <template #content>
      <div class="r-v2-invite__field">
        <span class="r-v2-invite__label">{{ t("settings.role") }}</span>
        <div class="r-v2-invite__role-row">
          <button
            v-for="role in roles"
            :key="role"
            type="button"
            class="r-v2-invite__role-btn"
            :class="{
              'r-v2-invite__role-btn--active': selectedRole === role,
            }"
            :aria-pressed="selectedRole === role"
            @click="selectedRole = role"
          >
            <RIcon :icon="getRoleIcon(role)" size="14" />
            {{ role.charAt(0).toUpperCase() + role.slice(1) }}
          </button>
        </div>
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
      <RBtn variant="text" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
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
.r-v2-invite__role-row {
  display: flex;
  gap: 8px;
}
.r-v2-invite__role-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  border-radius: 8px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-invite__role-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-invite__role-btn--active,
.r-v2-invite__role-btn--active:hover {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 60%,
    transparent
  );
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  color: var(--r-color-brand-primary);
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
