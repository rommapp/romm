<script setup lang="ts">
// BrandingSection (romm-themeable): choose the server's theme pack. Saving recompiles every
// pack from the mapped themes folder, so edits made on the host apply on save.
import { RAlert, RBtn, REmptyState, RSpinner, RTag } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import themeableApi, {
  type BrandingStatus,
  STOCK_THEME,
  type ThemePack,
} from "@/services/api/themeable";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useFetchState } from "@/v2/composables/useFetchState";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const PAGE_SIZE = 10;
// RomM's stock palette, shown as the swatch of the "RomM default" entry.
const STOCK_SWATCH = ["#07070f", "#8b74e8", "#e1a38d"];
const PERSONAL_CHOICE_KEY = "romm-themeable.theme";

type Option = Omit<ThemePack, "source"> & {
  source: ThemePack["source"] | "stock";
};

const { t } = useI18n();
const snackbar = useSnackbar();

const {
  state: status,
  isLoading: loading,
  error: loadError,
} = useFetchState(
  () => themeableApi.getBranding().then(({ data }) => data),
  null as BrandingStatus | null,
  {
    onError: (err) => {
      console.error("[branding] Could not load theme packs:", err);
      snackbar.error(t("branding.load-failed"));
    },
  },
);

const selected = ref<string>(STOCK_THEME);
const rescanning = ref(false);
const page = ref(1);
const saving = ref(false);
const savedOnce = ref(false);

const options = computed<Option[]>(() => [
  {
    id: STOCK_THEME,
    name: t("branding.stock-name"),
    description: t("branding.stock-description"),
    author: "",
    version: "",
    source: "stock",
    swatch: STOCK_SWATCH,
    valid: true,
    errors: [],
    warnings: [],
  },
  ...(status.value?.packs ?? []),
]);

const pageCount = computed(() =>
  Math.max(1, Math.ceil(options.value.length / PAGE_SIZE)),
);
const pageOptions = computed(() =>
  options.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
);

watch(status, (value) => {
  if (!value) return;
  const known = options.value.some((o) => o.id === value.selected);
  selected.value = known ? value.selected : STOCK_THEME;
  const index = options.value.findIndex((o) => o.id === selected.value);
  page.value = Math.floor(Math.max(index, 0) / PAGE_SIZE) + 1;
});

const folderWarning = computed(() => {
  const folder = status.value?.folder;
  if (!folder) return null;
  if (!folder.mounted)
    return t("branding.folder-not-mapped", { path: folder.path });
  if (!folder.writable)
    return t("branding.folder-not-writable", { path: folder.path });
  return null;
});

const personalChoice = computed(() => {
  try {
    // The theme loader keeps one choice per browser and reads it before sign-in.
    // eslint-disable-next-line romm/no-unscoped-local-storage
    return window.localStorage.getItem(PERSONAL_CHOICE_KEY);
  } catch {
    return null;
  }
});

function sourceLabel(option: Option): string {
  if (option.source === "stock") return t("branding.stock-source");
  if (option.source === "built-in") return t("branding.built-in");
  return t("branding.folder");
}

function previewHref(id: string): string {
  return `/?romm-theme-preview=${encodeURIComponent(id)}`;
}

async function save(): Promise<void> {
  saving.value = true;
  try {
    const { data } = await themeableApi.saveBranding(selected.value);
    status.value = data;
    savedOnce.value = true;
    if (data.ok) snackbar.success(t("branding.saved"));
    else snackbar.error(data.error ?? t("branding.save-failed"));
  } catch (err) {
    console.error("[branding] Could not save the theme:", err);
    snackbar.error(t("branding.save-failed"));
  } finally {
    saving.value = false;
  }
}

async function rescan(): Promise<void> {
  rescanning.value = true;
  try {
    status.value = (await themeableApi.rescanBranding()).data;
  } catch (err) {
    console.error("[branding] Could not rescan the themes folder:", err);
    snackbar.error(t("branding.load-failed"));
  } finally {
    rescanning.value = false;
  }
}

function reloadPage(): void {
  window.location.reload();
}
</script>

<template>
  <SettingsSection :title="t('branding.title')" icon="mdi-palette-outline">
    <template #header-actions>
      <RBtn
        icon="mdi-refresh"
        variant="text"
        density="compact"
        :tooltip="t('branding.refresh')"
        :aria-label="t('branding.refresh')"
        :disabled="loading || saving"
        :loading="rescanning"
        @click="rescan"
      />
    </template>

    <div v-if="loading && !status" class="r-v2-branding__loading">
      <RSpinner />
    </div>

    <REmptyState
      v-else-if="loadError && !status"
      size="small"
      icon="mdi-alert-circle-outline"
      :title="t('branding.load-failed')"
    />

    <form v-else class="r-v2-branding" @submit.prevent="save">
      <p class="r-v2-branding__intro">{{ t("branding.subtitle") }}</p>

      <RAlert
        v-if="status?.error"
        type="error"
        density="compact"
        :text="status.error"
      />
      <RAlert
        v-if="folderWarning"
        type="warning"
        density="compact"
        :text="folderWarning"
      />
      <RAlert
        v-for="note in status?.notes ?? []"
        :key="note"
        type="info"
        density="compact"
        :text="note"
      />
      <RAlert v-if="personalChoice" type="info" density="compact">
        {{ t("branding.own-choice") }}
        <a href="/themeable/" target="_blank" rel="noopener">{{
          t("branding.theme-picker")
        }}</a>
      </RAlert>

      <fieldset class="r-v2-branding__list">
        <legend class="r-v2-branding__legend">{{ t("branding.title") }}</legend>
        <label
          v-for="option in pageOptions"
          :key="option.id"
          :for="`romm-themeable-theme-${option.id}`"
          class="r-v2-branding__option"
          :class="{
            'r-v2-branding__option--selected': selected === option.id,
            'r-v2-branding__option--invalid': !option.valid,
          }"
        >
          <input
            :id="`romm-themeable-theme-${option.id}`"
            v-model="selected"
            class="r-v2-branding__radio"
            type="radio"
            name="romm-themeable-theme"
            :value="option.id"
            :disabled="!option.valid || saving"
          />
          <span class="r-v2-branding__swatch" aria-hidden="true">
            <span
              v-for="(color, i) in option.swatch"
              :key="i"
              class="r-v2-branding__chip"
              :style="{ background: color }"
            />
          </span>
          <span class="r-v2-branding__info">
            <span class="r-v2-branding__name">
              {{ option.name }}
              <RTag size="x-small" tone="neutral" :text="sourceLabel(option)" />
              <RTag
                v-if="status?.effective === option.id"
                size="x-small"
                tone="brand"
                prepend-icon="mdi-check"
                :text="t('branding.in-use')"
              />
              <RTag
                v-if="!option.valid"
                size="x-small"
                tone="danger"
                :text="t('branding.has-problems')"
              />
            </span>
            <span v-if="option.description" class="r-v2-branding__meta">
              {{ option.description }}
            </span>
            <ul v-if="option.errors.length" class="r-v2-branding__errors">
              <li v-for="(e, i) in option.errors" :key="i">{{ e }}</li>
            </ul>
          </span>
          <RBtn
            v-if="option.valid"
            variant="text"
            density="compact"
            prepend-icon="mdi-open-in-new"
            :href="previewHref(option.id)"
            target="_blank"
            :tooltip="t('branding.preview-hint')"
          >
            {{ t("branding.preview") }}
          </RBtn>
        </label>
      </fieldset>

      <nav
        v-if="pageCount > 1"
        class="r-v2-branding__pager"
        :aria-label="t('branding.title')"
      >
        <RBtn
          icon="mdi-chevron-left"
          variant="text"
          density="compact"
          :aria-label="t('branding.previous-page')"
          :disabled="page <= 1"
          @click="page -= 1"
        />
        <span class="r-v2-branding__page">
          {{ t("branding.page-of", { page, pages: pageCount }) }}
        </span>
        <RBtn
          icon="mdi-chevron-right"
          variant="text"
          density="compact"
          :aria-label="t('branding.next-page')"
          :disabled="page >= pageCount"
          @click="page += 1"
        />
      </nav>

      <div class="r-v2-branding__actions">
        <RBtn
          v-if="savedOnce"
          variant="text"
          prepend-icon="mdi-reload"
          @click="reloadPage"
        >
          {{ t("branding.reload-now") }}
        </RBtn>
        <RBtn type="submit" prepend-icon="mdi-content-save" :loading="saving">
          {{ t("branding.save") }}
        </RBtn>
      </div>
    </form>
  </SettingsSection>
</template>

<style scoped>
.r-v2-branding__loading {
  padding: var(--r-space-4);
  color: var(--r-color-fg-muted);
}

.r-v2-branding {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-4);
}

.r-v2-branding__intro {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-branding__list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.r-v2-branding__legend {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.r-v2-branding__option {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-3) var(--r-space-4);
  border-bottom: 1px solid var(--r-color-border);
  cursor: pointer;
}
.r-v2-branding__option:last-child {
  border-bottom: none;
}
.r-v2-branding__option:hover {
  background: var(--r-color-surface-hover);
}
.r-v2-branding__option--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}
.r-v2-branding__option--invalid {
  cursor: default;
}

.r-v2-branding__radio {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--r-color-brand-primary);
}

.r-v2-branding__swatch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
}
.r-v2-branding__chip {
  display: block;
  width: 14px;
  height: 28px;
}

.r-v2-branding__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.r-v2-branding__name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-branding__meta {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}

.r-v2-branding__errors {
  margin: var(--r-space-1) 0 0;
  padding-left: var(--r-space-4);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-danger-fg);
}

.r-v2-branding__pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--r-space-2);
}
.r-v2-branding__page {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-branding__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--r-space-2);
}

html[data-bp~="xs"] .r-v2-branding__option {
  grid-template-columns: auto auto minmax(0, 1fr);
}
html[data-bp~="xs"] .r-v2-branding__option > :last-child {
  grid-column: 3 / -1;
  justify-self: start;
}
</style>
