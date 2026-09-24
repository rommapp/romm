<script setup lang="ts">
// SettingsTab — platform-scoped settings rendered as the `Settings`
// tab inside Platform.vue. Details (editable name + read-only platform
// fields) with a danger zone underneath holding the destructive
// "Delete platform" action.
//
// Mutation path:
//   • `custom_name` / `description` → `platformApi.updatePlatform(...)`
//     Optimistic — the form updates the local platform reactively, a
//     snackbar fires on success/failure.
//
// Delete: emitted upward (`@delete`) so the view orchestrator can
// drive the confirm + router navigation. Same vocabulary as the
// pre-tabs admin kebab.
import { RBtn, RForm, RIcon, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import platformApi from "@/services/api/platform";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import DangerZone from "@/v2/components/shared/DangerZone.vue";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { required } from "@/v2/utils/validation";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  platform: Platform;
  deleting?: boolean;
}>();

const emit = defineEmits<{
  (e: "delete"): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();
const canEdit = useCan("platform.edit");
const hasDeleteGrant = useCan("platform.delete");
// `DELETE /platforms/{id}` gates on PLATFORMS_WRITE
const canDelete = computed(() => hasDeleteGrant.value && canEdit.value);

// ── Details edit form ──────────────────────────────────────────
const formRef = ref<InstanceType<typeof RForm> | null>(null);
const customName = ref<string>(props.platform.display_name);
const description = ref<string>(props.platform.description ?? "");
const saving = ref(false);

// Re-seed on platform change (route swap, socket update) so the fields
// reflect the live canonical values. Each field is watched independently,
// and only re-seeded when it still holds the previous canonical value,
// i.e. the user has no pending local edit to it. A background update to
// one field therefore never discards an unsaved edit to the other (or to
// itself).
watch(
  () => props.platform.display_name,
  (next, prev) => {
    if (!saving.value && customName.value === (prev ?? "")) {
      customName.value = next ?? "";
    }
  },
);

watch(
  () => props.platform.description,
  (next, prev) => {
    if (!saving.value && description.value === (prev ?? "")) {
      description.value = next ?? "";
    }
  },
);

const nameRules = computed(() => [required(t("common.required", "Required"))]);
const nameDirty = computed(
  () => customName.value.trim() !== props.platform.display_name,
);
const descriptionDirty = computed(
  () => description.value.trim() !== (props.platform.description ?? ""),
);
const dirty = computed(() => nameDirty.value || descriptionDirty.value);

async function save() {
  if (!dirty.value) return;
  const valid = await formRef.value?.validate();
  if (!valid) return;
  saving.value = true;
  try {
    // Send each field only when it actually changed.
    const { data } = await platformApi.updatePlatform({
      platform: {
        ...props.platform,
        custom_name: nameDirty.value
          ? customName.value.trim()
          : props.platform.custom_name,
      },
      description: descriptionDirty.value
        ? description.value.trim()
        : undefined,
    });
    platformsStore.update(data);
    if (galleryRoms.currentPlatform?.id === data.id) {
      galleryRoms.setCurrentPlatform(data);
    }
    snackbar.success(t("platform.updated", "Platform updated"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to update platform: ${
        e?.response?.data?.msg || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    saving.value = false;
  }
}

function discard() {
  customName.value = props.platform.display_name;
  description.value = props.platform.description ?? "";
}

// ── Details (read-only) ────────────────────────────────────────
type DetailRow = { label: string; value: string };
const details = computed<DetailRow[]>(() => {
  const p = props.platform;
  const rows: DetailRow[] = [
    { label: t("common.slug"), value: p.slug },
    { label: t("settings.folder-name"), value: p.fs_slug },
  ];
  if (p.category)
    rows.push({ label: t("platform.category"), value: p.category });
  if (typeof p.generation === "number" && p.generation > 0) {
    rows.push({ label: t("platform.generation"), value: String(p.generation) });
  }
  if (p.family_name) {
    rows.push({ label: t("platform.family"), value: p.family_name });
  }
  rows.push({
    label: t("common.size-on-disk"),
    value: formatBytes(p.fs_size_bytes ?? 0, 2),
  });
  rows.push({
    label: t("common.in-library", "In library"),
    value: String(p.rom_count ?? 0),
  });
  return rows;
});
</script>

<template>
  <div class="r-settings-column">
    <section class="r-v2-plat-settings__section">
      <header class="r-section-head">
        <RIcon icon="mdi-information-outline" size="14" />
        <span>{{ t("common.details", "Details") }}</span>
      </header>

      <!-- Only `custom_name` and `description` are user-authored; the
           rest is derived upstream and shown read-only below. -->
      <RForm ref="formRef" class="r-v2-plat-settings__form" @submit="save">
        <RTextField
          v-model="customName"
          prefix-label="stacked"
          :placeholder="platform.name"
          :rules="nameRules"
          :disabled="!canEdit"
          hide-details="auto"
        >
          <template #prefix-label>{{ t("common.name", "Name") }}</template>
        </RTextField>
        <RTextField
          v-model="description"
          prefix-label="stacked"
          :disabled="!canEdit"
          multiline
          :rows="3"
          hide-details="auto"
        >
          <template #prefix-label>
            {{ t("platform.description", "Description") }}
          </template>
        </RTextField>
        <div v-if="dirty" class="r-v2-plat-settings__form-actions">
          <RBtn variant="text" :disabled="saving" @click="discard">
            {{ t("common.discard", "Discard") }}
          </RBtn>
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-check"
            :disabled="!customName.trim()"
            :loading="saving"
            @click="save"
          >
            {{ t("common.apply", "Apply") }}
          </RBtn>
        </div>
      </RForm>

      <div class="r-v2-plat-settings__details">
        <div
          v-for="row in details"
          :key="row.label"
          class="r-v2-plat-settings__detail-row"
        >
          <span class="r-v2-plat-settings__detail-label">{{ row.label }}</span>
          <span class="r-v2-plat-settings__detail-value">{{ row.value }}</span>
        </div>
      </div>
    </section>

    <!-- Delete routes through the parent (confirm dialog + navigation
         lives in Platform.vue). -->
    <DangerZone
      v-if="canDelete"
      :title="t('platform.delete-platform', 'Delete platform')"
      :hint="
        t(
          'platform.delete-platform-hint',
          'Removes the platform and its ROM database entries. Files on disk are NOT deleted.',
        )
      "
    >
      <RBtn
        variant="outlined"
        color="danger"
        prepend-icon="mdi-delete-outline"
        :loading="deleting"
        :disabled="deleting"
        @click="emit('delete')"
      >
        {{ t("common.delete", "Delete") }}
      </RBtn>
    </DangerZone>
  </div>
</template>

<style scoped>
/* ── Name form ────────────────────────────────────────────────── */
.r-v2-plat-settings__form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}
.r-v2-plat-settings__form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ── Read-only details table ─────────────────────────────────── */
.r-v2-plat-settings__details {
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
}
.r-v2-plat-settings__detail-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  padding: 10px 14px;
  font-size: 12px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-plat-settings__detail-row:last-child {
  border-bottom: 0;
}
.r-v2-plat-settings__detail-label {
  color: var(--r-color-fg-muted);
}
.r-v2-plat-settings__detail-value {
  color: var(--r-color-fg);
  word-break: break-all;
}
</style>
