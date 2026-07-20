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
const canDelete = useCan("platform.delete");

// ── Details edit form ──────────────────────────────────────────
const formRef = ref<InstanceType<typeof RForm> | null>(null);
const customName = ref<string>(props.platform.display_name);
const description = ref<string>(props.platform.description ?? "");
const saving = ref(false);

// Re-seed on platform change (route swap, socket update) so the fields
// reflect the live canonical values. Discard the pending edit in that
// case — the source-of-truth changed under us. Each field is watched
// independently so a change to one doesn't throw away an unsaved edit
// to the other.
watch(
  () => props.platform.display_name,
  (next) => {
    if (!saving.value) customName.value = next ?? "";
  },
);

watch(
  () => props.platform.description,
  (next) => {
    if (!saving.value) description.value = next ?? "";
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
    // Send each field only when it actually changed. Writing the name
    // unconditionally would stamp `custom_name` onto a platform that never
    // had one just because its description was edited, pinning it against
    // later upstream metadata renames.
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
  <div class="r-v2-plat-settings">
    <!-- Left column — details (editable name + read-only fields) plus
         danger zone at the bottom. -->
    <div class="r-v2-plat-settings__col">
      <section class="r-v2-plat-settings__section">
        <header class="r-v2-plat-settings__section-head">
          <RIcon icon="mdi-information-outline" size="14" />
          <span>{{ t("common.details", "Details") }}</span>
        </header>

        <!-- Editable fields — `custom_name` and `description` are the
             only user-authored ones. The rest of the metadata (slug,
             fs_slug, etc.) is derived from the upstream sources and is
             surfaced read-only below. -->
        <RForm ref="formRef" class="r-v2-plat-settings__form" @submit="save">
          <RTextField
            v-model="customName"
            :label="t('common.name', 'Name')"
            :placeholder="platform.name"
            :rules="nameRules"
            :disabled="!canEdit"
            prepend-inner-icon="mdi-rename"
            variant="outlined"
            density="comfortable"
            hide-details="auto"
          />
          <RTextField
            v-model="description"
            :label="t('platform.description', 'Description')"
            :disabled="!canEdit"
            multiline
            :rows="3"
            variant="outlined"
            density="comfortable"
            hide-details="auto"
          />
          <div v-if="dirty" class="r-v2-plat-settings__form-actions">
            <RBtn variant="text" :disabled="saving" @click="discard">
              {{ t("common.discard", "Discard") }}
            </RBtn>
            <RBtn
              variant="flat"
              color="primary"
              prepend-icon="mdi-check"
              :loading="saving"
              @click="save"
            >
              {{ t("common.save", "Save") }}
            </RBtn>
          </div>
        </RForm>

        <!-- Read-only details. Kept as a hairline-divided table for
             scan-ability without competing with the editable field
             above. -->
        <div class="r-v2-plat-settings__details">
          <div
            v-for="row in details"
            :key="row.label"
            class="r-v2-plat-settings__detail-row"
          >
            <span class="r-v2-plat-settings__detail-label">{{
              row.label
            }}</span>
            <span class="r-v2-plat-settings__detail-value">{{
              row.value
            }}</span>
          </div>
        </div>
      </section>

      <!-- Danger zone — destructive actions kept visually separated
           with a brand-warning header band, matching the pattern v1
           used in PlatformInfoDrawer. The delete itself routes through
           the parent (confirm dialog + navigation lives in Platform.vue). -->
      <section
        v-if="canDelete"
        class="r-v2-plat-settings__section r-v2-plat-settings__danger"
      >
        <header
          class="r-v2-plat-settings__section-head r-v2-plat-settings__danger-head"
        >
          <RIcon icon="mdi-alert-outline" size="14" />
          <span>{{ t("platform.danger-zone", "Danger zone") }}</span>
        </header>
        <div class="r-v2-plat-settings__danger-row">
          <div class="r-v2-plat-settings__danger-copy">
            <p class="r-v2-plat-settings__danger-title">
              {{ t("platform.delete-platform", "Delete platform") }}
            </p>
            <p class="r-v2-plat-settings__danger-hint">
              {{
                t(
                  "platform.delete-platform-hint",
                  "Removes the platform and its ROM database entries. Files on disk are NOT deleted.",
                )
              }}
            </p>
          </div>
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
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-plat-settings {
  /* Single column — details + danger zone, constrained to a readable
     width rather than stretching the full tab. */
  display: grid;
  grid-template-columns: minmax(280px, 460px);
  gap: 28px;
  align-items: start;
}

.r-v2-plat-settings__col {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.r-v2-plat-settings__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

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

/* ── Danger zone ───────────────────────────────────────────────
   Subtle danger-tinted card. Header label borrows the section-head
   typography so it nests visually with the rest of the surface. */
.r-v2-plat-settings__danger {
  padding: 14px;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 6%,
    transparent
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 35%, transparent);
  border-radius: var(--r-radius-md);
}
.r-v2-plat-settings__danger-head {
  color: var(--r-color-status-base-danger);
}
.r-v2-plat-settings__danger-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.r-v2-plat-settings__danger-copy {
  flex: 1;
  min-width: 0;
}
.r-v2-plat-settings__danger-title {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-plat-settings__danger-hint {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}
</style>
