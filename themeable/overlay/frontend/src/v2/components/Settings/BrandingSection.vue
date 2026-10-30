<script setup lang="ts">
// BrandingSection (romm-themeable): choose the server's theme pack and what Random draws from,
// and upload, rename and delete packs. Every change recompiles the packs from the themes folder.
import {
  RAlert,
  RBtn,
  RDialog,
  REmptyState,
  RMenu,
  RMenuItem,
  RSpinner,
  RTag,
  RTextField,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import themeableApi, {
  type BrandingStatus,
  type RandomGroups,
  type ThemePack,
} from "@/services/api/themeable";
import BrandingArtwork from "@/v2/components/Settings/BrandingArtwork.vue";
import BrandingRandomArtwork from "@/v2/components/Settings/BrandingRandomArtwork.vue";
import BrandingUpload from "@/v2/components/Settings/BrandingUpload.vue";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useBrandingChoices } from "@/v2/composables/useBrandingChoices";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFetchState } from "@/v2/composables/useFetchState";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const PAGE_SIZE = 10;

type Option = Omit<ThemePack, "source" | "format"> & {
  source: ThemePack["source"] | "stock" | "draw";
  format?: ThemePack["format"];
};

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();

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

// Ids, storage key and stock swatch come from the compiled status, so they match the loader's.
const client = computed(() => status.value?.client ?? null);
const stockId = computed(() => client.value?.stock_id ?? "");
// The theme and Random's groups as they will be saved; the count follows the groups before Save changes.
const { selected, groups, adoptNext } = useBrandingChoices(status);
const groupKeys = computed(
  () => Object.keys(groups.value) as (keyof RandomGroups)[],
);
// The ids Random would draw with these groups, from the members the compiler published.
const drawIds = computed(() => {
  const random = status.value?.random;
  if (!random) return [];
  const { stock, ...packGroups } = groups.value;
  return [
    ...(stock ? [stockId.value] : []),
    ...Object.entries(packGroups).flatMap(([key, on]) =>
      on ? (random.members[key as keyof typeof random.members] ?? []) : [],
    ),
    ...(random.members.always ?? []),
  ];
});
const drawPacks = computed(() =>
  (status.value?.packs ?? []).filter((p) => drawIds.value.includes(p.id)),
);
const rescanning = ref(false);
const page = ref(1);
const saving = ref(false);
// The pack an action is running on, so only its buttons show progress.
const busy = ref<string | null>(null);
const renaming = ref<Option | null>(null);
const newName = ref("");
const renameOpen = computed({
  get: () => renaming.value !== null,
  set: (open) => {
    if (!open) renaming.value = null;
  },
});
const restoring = ref(false);
const savedOnce = ref(false);

const options = computed<Option[]>(() => [
  {
    id: client.value?.random_id ?? "",
    name: t("branding.random-name"),
    description: drawIds.value.length
      ? t("branding.random-description", drawIds.value.length)
      : "",
    author: "",
    version: "",
    source: "draw",
    // Each pack's brand color, the middle of its swatch.
    swatch: drawPacks.value.flatMap((p) => p.swatch.slice(1, 2)),
    valid: drawIds.value.length > 0,
    errors: drawIds.value.length ? [] : [t("branding.random-unavailable")],
    warnings: [],
    cover: null,
    tags: [],
  },
  {
    id: stockId.value,
    name: t("branding.stock-name"),
    description: t("branding.stock-description"),
    author: "",
    version: "",
    source: "stock",
    swatch: client.value?.stock_swatch ?? [],
    valid: true,
    errors: [],
    warnings: [],
    cover: null,
    tags: [],
  },
  ...(status.value?.packs ?? []),
]);

const pageCount = computed(() =>
  Math.max(1, Math.ceil(options.value.length / PAGE_SIZE)),
);
const pageOptions = computed(() =>
  options.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
);

watch(selected, (id) => {
  const index = options.value.findIndex((o) => o.id === id);
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
  const key = client.value?.storage_key;
  if (!key) return null;
  try {
    // The theme loader keeps one choice per browser and reads it before sign-in.
    // eslint-disable-next-line romm/no-unscoped-local-storage
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
});

function sourceLabel(option: Option): string {
  if (option.source === "draw") return t("branding.random-source");
  if (option.source === "stock") return t("branding.stock-source");
  if (option.source === "built-in") return t("branding.built-in");
  return t("branding.folder");
}

function previewHref(id: string): string {
  const param = client.value?.preview_param ?? "";
  return `/?${param}=${encodeURIComponent(id)}`;
}

async function save(): Promise<void> {
  saving.value = true;
  try {
    const { data } = await themeableApi.saveBranding(selected.value, {
      ...groups.value,
    });
    if (data.ok) adoptNext();
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

// Every pack can be renamed and deleted except RomM default and Random.
function canManage(option: Option): boolean {
  return option.source === "built-in" || option.source === "folder";
}

function isAccessible(option: Option): boolean {
  return option.tags.includes(client.value?.accessibility_tag ?? "");
}

/** Runs one pack action; a refused one changed nothing, so the list stays as it was. */
async function runAction(
  id: string,
  request: () => Promise<{ data: BrandingStatus }>,
  success: string,
  failure: string,
): Promise<boolean> {
  busy.value = id;
  try {
    const { data } = await request();
    if (!data.ok) {
      snackbar.error(data.error ?? failure);
      return false;
    }
    status.value = data;
    snackbar.success(success);
    return true;
  } catch (err) {
    console.error(`[branding] ${failure}:`, err);
    snackbar.error(failure);
    return false;
  } finally {
    busy.value = null;
  }
}

function startRename(option: Option): void {
  renaming.value = option;
  newName.value = option.name;
}

async function rename(): Promise<void> {
  const option = renaming.value;
  const name = newName.value.trim();
  if (!option || !name) return;
  if (name === option.name) {
    renaming.value = null;
    return;
  }
  const done = await runAction(
    option.id,
    () => themeableApi.renamePack(option.id, name),
    t("branding.renamed", { name }),
    t("branding.rename-failed"),
  );
  if (done) renaming.value = null;
}

async function resetName(option: Option): Promise<void> {
  const done = await runAction(
    option.id,
    () => themeableApi.renamePack(option.id, null),
    t("branding.name-reset", { name: option.default_name ?? option.name }),
    t("branding.rename-failed"),
  );
  if (done) renaming.value = null;
}

async function remove(option: Option): Promise<void> {
  const builtIn = option.source === "built-in";
  const confirmed = await confirm({
    title: t(builtIn ? "branding.hide-title" : "branding.delete-title", {
      name: option.name,
    }),
    body: t(builtIn ? "branding.hide-body" : "branding.delete-body", {
      id: option.id,
    }),
    confirmText: t(builtIn ? "branding.hide" : "branding.delete"),
    tone: "danger",
    // Deleting an archive can't be undone, so its id must be typed.
    ...(builtIn ? {} : { requireTyped: option.id }),
  });
  if (!confirmed) return;
  await runAction(
    option.id,
    () => themeableApi.deletePack(option.id),
    t(builtIn ? "branding.hidden" : "branding.deleted", { name: option.name }),
    t("branding.delete-failed"),
  );
}

async function restoreBuiltIns(): Promise<void> {
  restoring.value = true;
  try {
    await runAction(
      "",
      () => themeableApi.restoreBuiltInPacks(),
      t("branding.restored"),
      t("branding.restore-failed"),
    );
  } finally {
    restoring.value = false;
  }
}

function onUploaded(data: BrandingStatus): void {
  status.value = data;
  snackbar.success(data.notes.at(-1) ?? t("branding.uploaded"));
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
      <BrandingUpload
        :max-bytes="status?.max_upload_bytes ?? 0"
        :disabled="saving || !!busy || status?.folder?.writable === false"
        @uploaded="onUploaded"
      />
      <p class="r-v2-branding__intro">
        {{ t("branding.subtitle") }}
        <a
          v-if="client?.guide_url"
          :href="client.guide_url"
          target="_blank"
          rel="noopener"
          >{{ t("branding.guide-link") }}</a
        >
      </p>

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
              <RTag
                v-if="isAccessible(option)"
                size="x-small"
                tone="info"
                :text="t('branding.accessibility')"
              />
            </span>
            <span v-if="option.description" class="r-v2-branding__meta">
              {{ option.description }}
            </span>
            <span
              v-if="option.source === 'draw'"
              class="r-v2-branding__groups"
              role="group"
              :aria-label="t('branding.random-groups')"
            >
              <span class="r-v2-branding__meta">{{
                t("branding.random-groups")
              }}</span>
              <RBtn
                v-for="key in groupKeys"
                :key="key"
                size="x-small"
                :variant="groups[key] ? 'flat' : 'outlined'"
                :prepend-icon="groups[key] ? 'mdi-check' : undefined"
                :aria-pressed="groups[key]"
                :disabled="saving"
                @click.prevent="groups[key] = !groups[key]"
              >
                {{ t(`branding.random-group-${key}`) }}
              </RBtn>
            </span>
            <template v-if="option.valid && client?.preview">
              <BrandingRandomArtwork
                v-if="option.source === 'draw'"
                class="r-v2-branding__artwork"
                :packs="drawPacks"
                :client="client"
              />
              <BrandingArtwork
                v-else
                :id="option.id"
                class="r-v2-branding__artwork"
                :client="client"
                :cover="option.cover"
              />
            </template>
            <ul v-if="option.errors.length" class="r-v2-branding__errors">
              <li v-for="(e, i) in option.errors" :key="i">{{ e }}</li>
            </ul>
          </span>
          <span class="r-v2-branding__side">
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
            <RMenu v-if="canManage(option)" location="bottom end">
              <template #activator="{ props: menuProps }">
                <RBtn
                  v-bind="menuProps"
                  variant="outlined"
                  density="compact"
                  append-icon="mdi-chevron-down"
                  :loading="busy === option.id"
                  :disabled="(!!busy && busy !== option.id) || saving"
                  :aria-label="t('branding.more-for', { name: option.name })"
                  @click.prevent
                >
                  {{ t("branding.more") }}
                </RBtn>
              </template>
              <RMenuItem
                icon="mdi-pencil-outline"
                :label="t('branding.rename-item')"
                @click="startRename(option)"
              />
              <RMenuItem
                v-if="option.default_name"
                icon="mdi-restore"
                :label="t('branding.reset-name')"
                @click="resetName(option)"
              />
              <RMenuItem
                icon="mdi-delete-outline"
                variant="danger"
                :label="t('branding.delete-item')"
                @click="remove(option)"
              />
            </RMenu>
          </span>
        </label>
      </fieldset>

      <RDialog
        v-model="renameOpen"
        icon="mdi-pencil-outline"
        width="440"
        cancelable
        :cancel-disabled="!!busy"
      >
        <template #header>
          <span>{{
            t("branding.rename-title", { name: renaming?.name ?? "" })
          }}</span>
        </template>
        <template #content>
          <div class="r-v2-branding__rename">
            <p class="r-v2-branding__meta">{{ t("branding.rename-body") }}</p>
            <!-- eslint-disable vuejs-accessibility/no-autofocus -- focusing the name field when the rename dialog opens is intentional modal UX -->
            <RTextField
              v-model="newName"
              autofocus
              :label="t('branding.new-name')"
              :maxlength="client?.pack_name_max"
              @keydown.enter.prevent="rename"
            />
            <!-- eslint-enable vuejs-accessibility/no-autofocus -->
          </div>
        </template>
        <template #footer>
          <RBtn
            v-if="renaming?.default_name"
            variant="text"
            prepend-icon="mdi-restore"
            :disabled="!!busy"
            @click="renaming && resetName(renaming)"
          >
            {{ t("branding.reset-name") }}
          </RBtn>
          <RBtn
            prepend-icon="mdi-content-save"
            :loading="!!busy"
            :disabled="!newName.trim()"
            @click="rename"
          >
            {{ t("branding.rename-save") }}
          </RBtn>
        </template>
      </RDialog>

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
          v-if="status?.hidden?.length"
          class="r-v2-branding__restore"
          variant="text"
          prepend-icon="mdi-restore"
          :loading="restoring"
          :disabled="saving || !!busy"
          @click="restoreBuiltIns"
        >
          {{ t("branding.restore", { n: status.hidden.length }) }}
        </RBtn>
        <RBtn
          v-if="savedOnce"
          variant="text"
          prepend-icon="mdi-reload"
          @click="reloadPage"
        >
          {{ t("branding.reload-now") }}
        </RBtn>
        <RBtn
          type="submit"
          prepend-icon="mdi-content-save"
          :loading="saving"
          :disabled="!selected"
        >
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

/* A fixed width, so Random's one chip per pack lines up with the three-chip swatches. */
.r-v2-branding__swatch {
  display: inline-flex;
  width: 42px;
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
}
.r-v2-branding__chip {
  display: block;
  flex: 1;
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

.r-v2-branding__artwork {
  margin-top: var(--r-space-2);
}

.r-v2-branding__restore {
  margin-right: auto;
}

.r-v2-branding__rename {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-v2-branding__groups {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-2);
  margin-top: var(--r-space-1);
}

.r-v2-branding__side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--r-space-2);
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
