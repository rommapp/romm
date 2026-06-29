<script setup lang="ts">
// SetupStepAdmin — Step 2 of the setup wizard. Creates the first admin
// account that owns the library and manages other users.
//
// Two-column layout: left side carries the avatar picker + context (what
// this account can do, plus a heads-up to save the credentials), right
// side is the form. The avatar picker mirrors the v2 profile-settings
// pattern (clickable round image, hover overlay with a pencil, hidden
// file input). The picked File is held on the wizard draft so Setup.vue
// can upload it after createUser succeeds.
//
// The wizard owns the form draft (Setup.vue keeps the state so navigating
// to Step 1 and back preserves what the user typed). This component is
// pure UI: bind props in, emit input/validity out.
import { RBtn, RForm, RIcon, RTextField, RTooltip } from "@v2/lib";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { defaultAvatarPath } from "@/utils";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import {
  asciiOnly,
  email as emailRule,
  passwordLength,
  required,
  usernameChars,
  usernameLength,
} from "@/v2/utils/validation";

export interface AdminUserDraft {
  username: string;
  email: string;
  password: string;
  repeatPassword: string;
  avatar?: File;
}

defineOptions({ inheritAttrs: false });

const draft = defineModel<AdminUserDraft>({ required: true });
const valid = defineModel<boolean>("valid", { default: false });

const emit = defineEmits<{ (e: "submit"): void }>();

const { t } = useI18n();

const usernameRules = [required(), usernameLength, usernameChars, asciiOnly];
const emailRules = computed(() => {
  if (!draft.value.email) return [];
  return [emailRule];
});
const passwordRules = [required(), passwordLength];
const repeatPasswordRules = computed(() => [
  required(t("settings.repeat-password-required")),
  (v: string) =>
    v === draft.value.password || t("settings.passwords-must-match"),
]);

// ── Avatar picker ──────────────────────────────────────────────────
//
// Hold the preview URL alongside the File so the user can see what they
// picked even after they navigate away from this step and back. We use
// an object URL (cheaper than a base64 reader) and revoke it whenever
// the file changes or the component unmounts.
const fileInputRef = ref<HTMLInputElement | null>(null);
const previewUrl = ref<string>("");

watch(
  () => draft.value.avatar,
  (file, prev) => {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value);
      previewUrl.value = "";
    }
    if (file && file !== prev) {
      previewUrl.value = URL.createObjectURL(file);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});

const avatarSrc = computed(() => previewUrl.value || defaultAvatarPath);

function triggerFilePick() {
  fileInputRef.value?.click();
}

function onAvatarPicked(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  draft.value.avatar = file;
  // Clear the input so picking the same file twice still fires `change`.
  input.value = "";
}

function clearAvatar() {
  draft.value.avatar = undefined;
}

const abilities = [
  {
    icon: "mdi-folder-multiple-outline",
    textKey: "setup.admin-can-manage-library",
  },
  {
    icon: "mdi-account-multiple-outline",
    textKey: "setup.admin-can-manage-users",
  },
  { icon: "mdi-tune-vertical", textKey: "setup.admin-can-configure" },
];
</script>

<template>
  <div class="r-setup-admin">
    <!-- LEFT: context + avatar -->
    <aside class="r-setup-admin__intro">
      <div class="r-setup-admin__avatar-row">
        <button
          type="button"
          class="r-setup-admin__avatar"
          :aria-label="t('settings.change-avatar')"
          @click="triggerFilePick"
        >
          <img
            :src="avatarSrc"
            :alt="draft.username || t('settings.change-avatar')"
          />
          <span class="r-setup-admin__avatar-edit">
            <RIcon name="mdi-camera" :size="22" />
          </span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          class="r-setup-admin__file"
          :aria-label="t('settings.change-avatar')"
          @change="onAvatarPicked"
        />
        <RTooltip>
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              variant="text"
              size="small"
              icon="mdi-trash-can-outline"
              color="danger"
              class="r-setup-admin__avatar-trash"
              :disabled="!draft.avatar"
              :aria-label="t('common.remove')"
              @click="clearAvatar"
            />
          </template>
          <span>{{ t("common.remove") }}</span>
        </RTooltip>
      </div>

      <p class="r-setup-admin__lead">
        {{ t("setup.admin-user-intro") }}
      </p>
      <ul class="r-setup-admin__abilities">
        <li
          v-for="ability in abilities"
          :key="ability.icon"
          class="r-setup-admin__ability"
        >
          <RIcon :name="ability.icon" :size="18" color="primary" />
          <span>{{ t(ability.textKey) }}</span>
        </li>
      </ul>
      <div class="r-setup-admin__warning">
        <RIcon name="mdi-key-outline" :size="16" color="warning" />
        <span>{{ t("setup.admin-credentials-warning") }}</span>
      </div>
    </aside>

    <!-- RIGHT: form -->
    <RForm v-model="valid" class="r-setup-admin__form" @submit="emit('submit')">
      <RTextField
        :model-value="draft.username"
        :label="t('settings.username')"
        type="text"
        variant="underlined"
        autocomplete="username"
        prepend-inner-icon="mdi-account"
        :rules="usernameRules"
        @update:model-value="(v: string) => (draft.username = v)"
      />
      <RTextField
        :model-value="draft.email"
        :label="t('settings.email')"
        type="email"
        variant="underlined"
        autocomplete="email"
        prepend-inner-icon="mdi-email"
        :rules="emailRules"
        @update:model-value="(v: string) => (draft.email = v)"
      />
      <PasswordField
        :model-value="draft.password"
        :label="t('settings.password')"
        autocomplete="new-password"
        :rules="passwordRules"
        @update:model-value="(v: string) => (draft.password = v)"
      />
      <PasswordField
        :model-value="draft.repeatPassword"
        :label="t('settings.repeat-password')"
        autocomplete="new-password"
        :rules="repeatPasswordRules"
        @update:model-value="(v: string) => (draft.repeatPassword = v)"
      />
    </RForm>
  </div>
</template>

<style scoped>
.r-setup-admin {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--r-space-8);
  align-items: center;
}

html[data-bp~="sm-and-down"] .r-setup-admin {
  grid-template-columns: 1fr;
  gap: var(--r-space-5);
}

/* ── Left intro panel ────────────────────────────────────────────── */
.r-setup-admin__intro {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
  max-width: 420px;
  justify-self: end;
}

html[data-bp~="sm-and-down"] .r-setup-admin__intro {
  justify-self: stretch;
  max-width: none;
  align-items: center;
  text-align: center;
}

/* Avatar — clickable round button sits next to a small trash icon that
   removes the picked photo. The trash button stays disabled until a
   photo is picked so the affordance is discoverable without inviting a
   no-op click. It bottom-aligns next to the avatar so the danger glyph
   reads as a footer action on the photo, not as a sibling control. */
.r-setup-admin__avatar-row {
  display: flex;
  align-items: flex-end;
  gap: var(--r-space-2);
  align-self: flex-start;
}

html[data-bp~="sm-and-down"] .r-setup-admin__avatar-row {
  align-self: center;
}

.r-setup-admin__avatar-trash {
  margin-bottom: -4px;
}

.r-setup-admin__avatar {
  position: relative;
  appearance: none;
  padding: 0;
  background: var(--r-color-surface);
  cursor: pointer;
  border-radius: 50%;
  overflow: hidden;
  width: 96px;
  height: 96px;
  flex-shrink: 0;
  border: 1px solid
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
  box-shadow: 0 0 24px
    color-mix(in srgb, var(--r-color-brand-primary) 25%, transparent);
  transition:
    border-color 200ms ease,
    box-shadow 200ms ease,
    transform 200ms ease;
}

.r-setup-admin__avatar:hover,
.r-setup-admin__avatar:focus-visible {
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 4px
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  transform: scale(1.03);
}

.r-setup-admin__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.r-setup-admin__avatar-edit {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 55%, transparent);
  color: white;
  opacity: 0;
  transition: opacity 200ms ease;
  pointer-events: none;
}

.r-setup-admin__avatar:hover .r-setup-admin__avatar-edit,
.r-setup-admin__avatar:focus-visible .r-setup-admin__avatar-edit {
  opacity: 1;
}

.r-setup-admin__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.r-setup-admin__lead {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-setup-admin__abilities {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-setup-admin__ability {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: var(--r-space-3);
  align-items: start;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
  line-height: var(--r-line-height-normal);
  text-align: left;
}

.r-setup-admin__ability :deep(.r-icon) {
  margin-top: 2px;
}

.r-setup-admin__warning {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  padding: var(--r-space-2) var(--r-space-3);
  border-radius: var(--r-radius-md);
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-warning) 35%, transparent);
  background: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 8%,
    transparent
  );
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-secondary);
}

/* ── Right form ──────────────────────────────────────────────────── */
.r-setup-admin__form {
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  justify-self: start;
}

html[data-bp~="sm-and-down"] .r-setup-admin__form {
  justify-self: stretch;
  max-width: none;
}
</style>
