<script setup lang="ts">
// EditPlatformDialog — surfaces every read-only platform field along
// with a single editable control for the display name (custom_name).
// Same vocabulary as v1's PlatformInfoDrawer edit mode, just promoted
// to a dialog and aligned with v2 primitives.
//
// Mutation path: `platformApi.updatePlatform({ platform: { …, custom_name } })`.
// On success we sync both the platforms store and the gallery's
// current platform ref so the InfoPanel re-renders instantly without
// waiting for a refetch.
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import platformApi from "@/services/api/platform";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { required } from "@/v2/utils/validation";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();

const formRef = ref<InstanceType<typeof RForm> | null>(null);
const customName = ref<string>(props.platform.display_name);
const saving = ref(false);

// Re-seed the editable field every time the dialog opens (or the
// underlying platform changes mid-session via socket events). Keeps
// the field in sync with the current canonical name when the user
// re-opens after closing without saving.
watch(
  () => [props.modelValue, props.platform.display_name] as const,
  ([open, name]) => {
    if (open) customName.value = name;
  },
);

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

const nameRules = computed(() => [required(t("common.required", "Required"))]);

function closeDialog() {
  emit("update:modelValue", false);
}

async function onSave() {
  const valid = await formRef.value?.validate();
  if (!valid) return;
  if (customName.value === props.platform.display_name) {
    closeDialog();
    return;
  }
  saving.value = true;
  try {
    const { data } = await platformApi.updatePlatform({
      platform: { ...props.platform, custom_name: customName.value },
    });
    platformsStore.update(data);
    if (galleryRoms.currentPlatform?.id === data.id) {
      galleryRoms.setCurrentPlatform(data);
    }
    snackbar.success(t("platform.updated", "Platform updated"), {
      icon: "mdi-check-bold",
    });
    closeDialog();
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
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-pencil"
    :width="520"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("platform.edit-platform", "Edit platform") }}</span>
    </template>

    <template #content>
      <RForm ref="formRef" class="r-v2-edit-plat" @submit="onSave">
        <!-- Editable: display name. Only field the user can change
             today; the rest of the platform record is read-only here
             (slug/fs_slug/category/etc. are derived from the upstream
             metadata sources, not user-editable). -->
        <RTextField
          v-model="customName"
          :label="t('common.name', 'Name')"
          :placeholder="platform.name"
          :rules="nameRules"
          prepend-inner-icon="mdi-rename"
          variant="outlined"
          density="comfortable"
          autofocus
          hide-details="auto"
        />

        <!-- Read-only details — same fields the v1 drawer exposed and
             the v2 Settings tab still surfaces. Kept here so the edit
             flow has the full platform context at a glance without
             jumping back to the Settings tab. -->
        <section class="r-v2-edit-plat__details">
          <div
            v-for="row in details"
            :key="row.label"
            class="r-v2-edit-plat__detail-row"
          >
            <span class="r-v2-edit-plat__detail-label">{{ row.label }}</span>
            <span class="r-v2-edit-plat__detail-value">{{ row.value }}</span>
          </div>
        </section>
      </RForm>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="saving" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <span class="r-v2-edit-plat__footer-spacer" />
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :loading="saving"
        @click="onSave"
      >
        {{ t("common.save", "Save") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-edit-plat {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.r-v2-edit-plat__footer-spacer {
  flex: 1;
}

.r-v2-edit-plat__details {
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
}
.r-v2-edit-plat__detail-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  padding: 10px 14px;
  font-size: 12px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-edit-plat__detail-row:last-child {
  border-bottom: 0;
}
.r-v2-edit-plat__detail-label {
  color: var(--r-color-fg-muted);
}
.r-v2-edit-plat__detail-value {
  color: var(--r-color-fg);
  word-break: break-all;
}
</style>
