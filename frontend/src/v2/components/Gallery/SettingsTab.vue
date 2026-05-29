<script setup lang="ts">
// SettingsTab — platform-scoped settings rendered as the `Settings`
// tab inside Platform.vue. Two-column layout: details (editable name
// + read-only platform fields) on the left, cover-style picker on
// the right. A danger zone underneath the details column holds the
// destructive "Delete platform" action.
//
// Mutation paths:
//   • `custom_name` → `platformApi.updatePlatform({ platform: { …, custom_name } })`
//   • `aspect_ratio` → `platformApi.updatePlatform({ platform: { …, aspect_ratio } })`
//     Both flows are optimistic — the picker / form updates the local
//     platform reactively, a snackbar fires on success/failure.
//
// Delete: emitted upward (`@delete`) so the view orchestrator can
// drive the confirm + router navigation. Same vocabulary as the
// pre-tabs admin kebab.
import { RBtn, RChip, RForm, RIcon, RTextField } from "@v2/lib";
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

// ── Name edit form ─────────────────────────────────────────────
const formRef = ref<InstanceType<typeof RForm> | null>(null);
const customName = ref<string>(props.platform.display_name);
const savingName = ref(false);

// Re-seed on platform change (route swap, socket update) so the
// field reflects the live canonical name. Discard pending edits in
// that case — the source-of-truth changed under us.
watch(
  () => props.platform.display_name,
  (next) => {
    if (!savingName.value) customName.value = next;
  },
);

const nameRules = computed(() => [required(t("common.required", "Required"))]);
const nameDirty = computed(
  () => customName.value.trim() !== props.platform.display_name,
);

async function saveName() {
  if (!nameDirty.value) return;
  const valid = await formRef.value?.validate();
  if (!valid) return;
  savingName.value = true;
  try {
    const { data } = await platformApi.updatePlatform({
      platform: { ...props.platform, custom_name: customName.value.trim() },
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
    savingName.value = false;
  }
}

function discardName() {
  customName.value = props.platform.display_name;
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

// ── Aspect ratio ────────────────────────────────────────────────
// Platform-specific options. DVD / Blu-ray / DS / PSP / Switch
// families each add their natural-fit aspect on top of the universal
// 2:3 / 3:4 / 1:1 / 16:11 baseline.
const DVD_PLATFORMS = new Set([
  "dvd-player",
  "ps2",
  "ngc",
  "wii",
  "wiiu",
  "xbox",
  "xbox360",
  "win",
]);
const BLU_RAY_PLATFORMS = new Set([
  "blu-ray-player",
  "ps3",
  "ps4",
  "ps5",
  "psvita",
  "xboxone",
  "series-x-s",
]);
const DS_3DS_PLATFORMS = new Set([
  "nds",
  "nintendo-dsi",
  "3ds",
  "new-nintendo-3ds",
  "psx",
  "dc",
]);
const PSP_PLATFORMS = new Set(["psp", "psp-minis"]);
const SWITCH_PLATFORMS = new Set(["switch", "switch-2"]);

interface AspectOption {
  name: string;
  size: number;
  source: string;
}

const aspectOptions = computed<AspectOption[]>(() => {
  const slug = props.platform.slug?.toLowerCase() ?? "";
  return [
    { name: "2 / 3", size: 2 / 3, source: "SteamGridDB" },
    { name: "3 / 4", size: 3 / 4, source: "IGDB / MobyGames" },
    {
      name: "1 / 1",
      size: 1 / 1,
      source: t("platform.old-squared-cases"),
    },
    {
      name: "16 / 11",
      size: 16 / 11,
      source: t("platform.old-horizontal-cases"),
    },
    ...(DVD_PLATFORMS.has(slug)
      ? [{ name: "0.71 / 1", size: 0.71 / 1, source: "DVD" }]
      : []),
    ...(BLU_RAY_PLATFORMS.has(slug)
      ? [
          {
            name: "0.79 / 1",
            size: 0.79 / 1,
            source: "Blu-ray (Full artwork)",
          },
          {
            name: "0.87 / 1",
            size: 0.87 / 1,
            source: "Blu-ray (Plastic header)",
          },
        ]
      : []),
    ...(DS_3DS_PLATFORMS.has(slug)
      ? [{ name: "1.08 / 1", size: 1.08 / 1, source: "Nintendo DS / 3DS" }]
      : []),
    ...(PSP_PLATFORMS.has(slug)
      ? [{ name: "0.58 / 1", size: 0.58 / 1, source: "PSP" }]
      : []),
    ...(SWITCH_PLATFORMS.has(slug)
      ? [{ name: "0.62 / 1", size: 0.62 / 1, source: "Switch" }]
      : []),
  ];
});

const selectedAspect = computed(() => props.platform.aspect_ratio ?? "3 / 4");

async function setAspect(option: AspectOption) {
  if (option.name === selectedAspect.value) return;
  try {
    const { data } = await platformApi.updatePlatform({
      platform: { ...props.platform, aspect_ratio: option.name },
    });
    platformsStore.update(data);
    if (galleryRoms.currentPlatform?.id === data.id) {
      galleryRoms.setCurrentPlatform(data);
    }
    snackbar.success(t("platform.updated") || "Platform updated", {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to update aspect ratio: ${
        e?.response?.data?.msg || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  }
}
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

        <!-- Editable name field — only `custom_name` is user-editable
             today. The rest of the metadata (slug, fs_slug, etc.) is
             derived from the upstream sources, surfaced read-only. -->
        <RForm
          ref="formRef"
          class="r-v2-plat-settings__name-form"
          @submit="saveName"
        >
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
          <div v-if="nameDirty" class="r-v2-plat-settings__name-actions">
            <RBtn variant="text" :disabled="savingName" @click="discardName">
              {{ t("common.discard", "Discard") }}
            </RBtn>
            <RBtn
              variant="flat"
              color="primary"
              prepend-icon="mdi-check"
              :loading="savingName"
              @click="saveName"
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

    <!-- Right column — cover-style picker. -->
    <div class="r-v2-plat-settings__col">
      <section class="r-v2-plat-settings__section">
        <header class="r-v2-plat-settings__section-head">
          <RIcon icon="mdi-aspect-ratio" size="14" />
          <span>{{ t("platform.cover-style") }}</span>
        </header>
        <div class="r-v2-plat-settings__aspects">
          <button
            v-for="opt in aspectOptions"
            :key="opt.name"
            type="button"
            class="r-v2-plat-settings__aspect"
            :class="{
              'r-v2-plat-settings__aspect--active': opt.name === selectedAspect,
            }"
            :aria-pressed="opt.name === selectedAspect"
            @click="setAspect(opt)"
          >
            <span
              class="r-v2-plat-settings__aspect-tile"
              :style="{ aspectRatio: String(opt.size) }"
            >
              <span class="r-v2-plat-settings__aspect-name">{{
                opt.name
              }}</span>
            </span>
            <RChip
              size="x-small"
              variant="translucent"
              class="r-v2-plat-settings__aspect-source"
            >
              {{ opt.source }}
            </RChip>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-plat-settings {
  display: grid;
  /* Two-column layout — details + danger zone on the left, cover-style
     picker on the right. Collapses to a single column under 900px so
     the aspect grid keeps reasonable card sizing. */
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: 28px;
  align-items: start;
}

@media (max-width: 900px) {
  .r-v2-plat-settings {
    grid-template-columns: 1fr;
  }
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
.r-v2-plat-settings__name-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}
.r-v2-plat-settings__name-actions {
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

/* ── Aspect ratio grid ─────────────────────────────────────────── */
.r-v2-plat-settings__aspects {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
.r-v2-plat-settings__aspect {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--r-color-fg);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-plat-settings__aspect:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
}
.r-v2-plat-settings__aspect--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-plat-settings__aspect-tile {
  display: grid;
  place-items: center;
  width: 80%;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: 6px;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-plat-settings__aspect--active .r-v2-plat-settings__aspect-tile {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 60%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-plat-settings__aspect-name {
  pointer-events: none;
}
.r-v2-plat-settings__aspect-source {
  font-size: 10px;
  text-align: center;
}
</style>
