<script setup lang="ts">
// SetupStepPlatforms — Step 1 of the setup wizard.
//
// Layout:
//   1. Structure banner — what folder layout is in use or will be created.
//   2. Detected platforms — read-only, always rendered (folders that
//      already exist on disk). Bundled with any unidentified folders so
//      the user knows nothing of theirs got lost.
//   3. Supported platforms — every platform RomM knows about, grouped
//      by manufacturer. Groups are CLOSED by default and their bodies
//      are gated with v-if (not v-show), so first-render is tiny —
//      otherwise the catalogue's ~300 entries blow up DOM cost.
//   4. Search — when non-empty, replaces the grouped browse with a flat,
//      capped result list across every supported platform.
//   5. Summary line — restates how many new folders the wizard will
//      create under which pattern, so the directory creation effect
//      is never a surprise.
import {
  RBtn,
  RCheckbox,
  RChip,
  RCollapsible,
  REmptyState,
  RIcon,
  RPlatformIcon,
  RTag,
  RTextField,
} from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SetupLibraryInfo } from "@/services/api/setup";
import type { Platform } from "@/stores/platforms";

defineOptions({ inheritAttrs: false });

interface Props {
  libraryInfo: SetupLibraryInfo;
  selectedNewPlatforms: string[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "update:selectedNewPlatforms", value: string[]): void;
}>();

const { t } = useI18n();

const search = ref("");
const openGroups = ref<Set<string>>(new Set());
// Groups that have been opened at least once. We keep their body content
// mounted once expanded so re-opening animates smoothly without remounting.
const mountedGroups = ref<Set<string>>(new Set());

const UNIDENTIFIED = "__unidentified__";
const SEARCH_LIMIT = 80;

// ── Detected platforms ─────────────────────────────────────────────
//
// "Detected" = on disk. We split into identified (matches a supported
// platform → we have a nice display name + icon) and unidentified
// (a folder that doesn't match — likely a typo or an unsupported
// platform). Both get shown in the same section so nothing slips
// through the cracks.

const detectedSlugSet = computed(
  () => new Set(props.libraryInfo.existing_platforms.map((p) => p.fs_slug)),
);

const romCountBySlug = computed(() => {
  const map = new Map<string, number>();
  for (const p of props.libraryInfo.existing_platforms)
    map.set(p.fs_slug, p.rom_count);
  return map;
});

const supportedSlugSet = computed(
  () => new Set(props.libraryInfo.supported_platforms.map((p) => p.fs_slug)),
);

const detectedPlatforms = computed<Array<Platform & { unidentified: boolean }>>(
  () => {
    if (!props.libraryInfo.detected_structure) return [];
    const identified = props.libraryInfo.supported_platforms
      .filter((p) => detectedSlugSet.value.has(p.fs_slug))
      .map((p) => ({ ...p, unidentified: false }));
    const unidentified = props.libraryInfo.existing_platforms
      .filter((p) => !supportedSlugSet.value.has(p.fs_slug))
      .map(
        (p) =>
          ({
            fs_slug: p.fs_slug,
            slug: p.fs_slug,
            name: p.fs_slug,
            family_name: UNIDENTIFIED,
            generation: 999,
            unidentified: true,
          }) as Platform & { unidentified: boolean },
      );
    return [...identified, ...unidentified].sort((a, b) =>
      (a.name ?? a.fs_slug).localeCompare(b.name ?? b.fs_slug),
    );
  },
);

const totalDetectedGames = computed(() =>
  props.libraryInfo.existing_platforms.reduce((s, p) => s + p.rom_count, 0),
);

// ── Supported (selectable) platforms ───────────────────────────────
//
// Filter out anything already on disk — those are shown in the detected
// section. We never present the same fs_slug twice.

const supportedAvailable = computed<Platform[]>(() =>
  props.libraryInfo.supported_platforms.filter(
    (p) => !detectedSlugSet.value.has(p.fs_slug),
  ),
);

interface Group {
  key: string;
  label: string;
  items: Platform[];
}

const groupedAvailable = computed<Group[]>(() => {
  const map = new Map<string, Platform[]>();
  for (const p of supportedAvailable.value) {
    const key = p.family_name || "Other";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  const groups: Group[] = [];
  const keys = [...map.keys()].sort((a, b) => {
    if (a === "Other") return 1;
    if (b === "Other") return -1;
    return a.localeCompare(b);
  });
  for (const key of keys) {
    const items = map.get(key)!;
    items.sort((a, b) => {
      const aGen = a.generation ?? -1;
      const bGen = b.generation ?? -1;
      if (aGen !== bGen) return aGen - bGen;
      return (a.name ?? a.fs_slug).localeCompare(b.name ?? b.fs_slug);
    });
    groups.push({ key, label: key, items });
  }
  return groups;
});

// ── Search ─────────────────────────────────────────────────────────
//
// When a query is present, we abandon the grouped browse and show a
// flat list of supported (non-detected) matches, capped so a one-letter
// search doesn't end up rendering the whole catalogue.

const searchResults = computed<Platform[]>(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return [];
  return supportedAvailable.value
    .filter(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.fs_slug.toLowerCase().includes(q) ||
        p.slug?.toLowerCase().includes(q) ||
        p.family_name?.toLowerCase().includes(q),
    )
    .slice(0, SEARCH_LIMIT);
});

// ── Selection helpers ──────────────────────────────────────────────

function isSelected(slug: string): boolean {
  return props.selectedNewPlatforms.includes(slug);
}

function togglePlatform(slug: string, next: boolean) {
  if (detectedSlugSet.value.has(slug)) return;
  const set = new Set(props.selectedNewPlatforms);
  if (next) set.add(slug);
  else set.delete(slug);
  emit("update:selectedNewPlatforms", [...set]);
}

function newSlugsInGroup(items: Platform[]): string[] {
  return items
    .filter((p) => !detectedSlugSet.value.has(p.fs_slug))
    .map((p) => p.fs_slug);
}

function groupSelectedState(items: Platform[]): boolean | null {
  const selectable = newSlugsInGroup(items);
  if (selectable.length === 0) return false;
  const selected = selectable.filter((s) => isSelected(s)).length;
  if (selected === 0) return false;
  if (selected === selectable.length) return true;
  return null;
}

function toggleGroup(items: Platform[], next: boolean) {
  const selectable = newSlugsInGroup(items);
  if (selectable.length === 0) return;
  const set = new Set(props.selectedNewPlatforms);
  if (next) for (const s of selectable) set.add(s);
  else for (const s of selectable) set.delete(s);
  emit("update:selectedNewPlatforms", [...set]);
}

const allAvailableSelected = computed(() => {
  if (supportedAvailable.value.length === 0) return false;
  return supportedAvailable.value.every((p) => isSelected(p.fs_slug));
});

function toggleAllAvailable() {
  const set = new Set(props.selectedNewPlatforms);
  if (allAvailableSelected.value) {
    for (const p of supportedAvailable.value) set.delete(p.fs_slug);
  } else {
    for (const p of supportedAvailable.value) set.add(p.fs_slug);
  }
  emit("update:selectedNewPlatforms", [...set]);
}

function setGroupOpen(key: string, open: boolean) {
  const s = new Set(openGroups.value);
  if (open) {
    s.add(key);
    if (!mountedGroups.value.has(key)) {
      mountedGroups.value = new Set([...mountedGroups.value, key]);
    }
  } else {
    s.delete(key);
  }
  openGroups.value = s;
}

// ── Structure banner copy ──────────────────────────────────────────

const detectedStructure = computed(() => props.libraryInfo.detected_structure);
const structurePattern = computed(() => {
  if (detectedStructure.value === "struct_b") return "{platform}/roms";
  return "roms/{platform}";
});
const detectedPlatformCount = computed(
  () => props.libraryInfo.existing_platforms.length,
);

function platformFolderPath(slug: string): string {
  if (detectedStructure.value === "struct_b") return `${slug}/roms`;
  return `roms/${slug}`;
}
</script>

<template>
  <section class="r-setup-platforms">
    <!-- Lead + structure banner -->
    <p class="r-setup-platforms__lead">
      {{ t("setup.supported-platforms-lead") }}
    </p>

    <div
      class="r-setup-platforms__banner"
      :data-tone="detectedStructure ? 'info' : 'warning'"
    >
      <div class="r-setup-platforms__banner-text">
        <strong>
          {{
            detectedStructure === "struct_a"
              ? t("setup.structure-a-detected")
              : detectedStructure === "struct_b"
                ? t("setup.structure-b-detected")
                : t("setup.no-structure-banner-title")
          }}
        </strong>
        <code class="r-setup-platforms__banner-pattern">
          {{ structurePattern }}
        </code>
        <span v-if="!detectedStructure" class="r-setup-platforms__banner-meta">
          — {{ t("setup.no-structure-banner-body") }}
        </span>
      </div>
    </div>

    <!-- Two-column body: detected | supported -->
    <div class="r-setup-platforms__columns">
      <!-- LEFT: Detected platforms -->
      <section class="r-setup-platforms__pane">
        <header class="r-setup-platforms__section-head">
          <h3 class="r-setup-platforms__section-title">
            <RIcon name="mdi-folder-check" color="primary" :size="16" />
            <span>{{ t("setup.detected-platforms") }}</span>
            <RChip size="x-small" variant="translucent" color="primary">
              {{ detectedPlatformCount }}
              {{
                detectedPlatformCount === 1
                  ? t("setup.platform")
                  : t("setup.platforms")
              }}
            </RChip>
            <RChip size="x-small" variant="translucent">
              {{ totalDetectedGames }}
              {{
                totalDetectedGames === 1 ? t("setup.game") : t("setup.games")
              }}
            </RChip>
          </h3>
        </header>

        <div class="r-setup-platforms__pane-scroll">
          <REmptyState
            v-if="detectedPlatforms.length === 0"
            icon="mdi-folder-search-outline"
            :title="t('setup.no-structure-detected')"
          />
          <ul v-else class="r-setup-platforms__items">
            <li
              v-for="platform in detectedPlatforms"
              :key="platform.fs_slug"
              class="r-setup-platforms__item"
              data-state="detected"
            >
              <RPlatformIcon
                :slug="platform.slug"
                :fs-slug="platform.fs_slug"
                :name="platform.name"
                :size="26"
                :show-tooltip="false"
                class="r-setup-platforms__item-icon"
              />
              <div class="r-setup-platforms__item-body">
                <span class="r-setup-platforms__item-name">
                  {{ platform.name || platform.fs_slug }}
                </span>
                <span class="r-setup-platforms__item-slug">
                  {{ platform.fs_slug }}
                </span>
              </div>
              <div class="r-setup-platforms__item-state">
                <RTag
                  v-if="platform.unidentified"
                  size="x-small"
                  tone="warning"
                >
                  {{ t("setup.unidentified") }}
                </RTag>
                <RChip
                  v-else
                  size="x-small"
                  variant="translucent"
                  color="primary"
                >
                  {{
                    t(
                      "setup.platform-detected-with-games",
                      { count: romCountBySlug.get(platform.fs_slug) ?? 0 },
                      romCountBySlug.get(platform.fs_slug) ?? 0,
                    )
                  }}
                </RChip>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <!-- RIGHT: Supported platforms -->
      <section class="r-setup-platforms__pane">
        <header class="r-setup-platforms__section-head">
          <h3 class="r-setup-platforms__section-title">
            <RIcon name="mdi-folder-plus-outline" :size="16" />
            <span>{{ t("setup.supported-platforms") }}</span>
            <RChip size="x-small" variant="translucent">
              {{ supportedAvailable.length }}
            </RChip>
          </h3>
          <div class="r-setup-platforms__toolbar">
            <RTextField
              v-model="search"
              density="comfortable"
              variant="outlined"
              prepend-inner-icon="mdi-magnify"
              :placeholder="t('setup.platforms-search-placeholder')"
              hide-details
              class="r-setup-platforms__search"
            />
            <RBtn
              variant="text"
              :disabled="supportedAvailable.length === 0"
              :prepend-icon="
                allAvailableSelected
                  ? 'mdi-checkbox-blank-outline'
                  : 'mdi-check-all'
              "
              @click="toggleAllAvailable"
            >
              {{
                allAvailableSelected
                  ? t("setup.deselect-all")
                  : t("setup.select-all-available")
              }}
            </RBtn>
          </div>
        </header>

        <div class="r-setup-platforms__pane-scroll">
          <!-- Search results (flat, capped) -->
          <template v-if="search.trim()">
            <REmptyState
              v-if="searchResults.length === 0"
              icon="mdi-magnify-close"
              :title="t('setup.platforms-found-empty')"
            />
            <ul v-else class="r-setup-platforms__items">
              <li
                v-for="platform in searchResults"
                :key="platform.fs_slug"
                class="r-setup-platforms__item"
                :data-state="
                  isSelected(platform.fs_slug) ? 'selected' : 'available'
                "
                role="checkbox"
                :aria-checked="isSelected(platform.fs_slug)"
                :tabindex="0"
                @click="
                  togglePlatform(
                    platform.fs_slug,
                    !isSelected(platform.fs_slug),
                  )
                "
                @keydown.space.prevent="
                  togglePlatform(
                    platform.fs_slug,
                    !isSelected(platform.fs_slug),
                  )
                "
                @keydown.enter.prevent="
                  togglePlatform(
                    platform.fs_slug,
                    !isSelected(platform.fs_slug),
                  )
                "
              >
                <RCheckbox
                  :model-value="isSelected(platform.fs_slug)"
                  size="sm"
                  hide-details
                  bare
                  @click.stop
                  @update:model-value="
                    (v) => togglePlatform(platform.fs_slug, v)
                  "
                />
                <RPlatformIcon
                  :slug="platform.slug"
                  :fs-slug="platform.fs_slug"
                  :name="platform.name"
                  :size="26"
                  :show-tooltip="false"
                  class="r-setup-platforms__item-icon"
                />
                <div class="r-setup-platforms__item-body">
                  <span class="r-setup-platforms__item-name">
                    {{ platform.name || platform.fs_slug }}
                  </span>
                  <span class="r-setup-platforms__item-slug">
                    {{ platform.fs_slug }}
                  </span>
                </div>
                <div class="r-setup-platforms__item-state">
                  <RChip
                    v-if="isSelected(platform.fs_slug)"
                    size="x-small"
                    variant="translucent"
                    color="success"
                  >
                    <RIcon name="mdi-folder-plus" :size="12" />
                    <code>{{ platformFolderPath(platform.fs_slug) }}</code>
                  </RChip>
                </div>
              </li>
            </ul>
          </template>

          <!-- Manufacturer groups (browse mode) -->
          <ul v-else class="r-setup-platforms__groups">
            <li
              v-for="group in groupedAvailable"
              :key="group.key"
              class="r-setup-platforms__group"
            >
              <RCollapsible
                :model-value="openGroups.has(group.key)"
                @update:model-value="(v) => setGroupOpen(group.key, v)"
              >
                <template #header-prepend>
                  <RCheckbox
                    :model-value="groupSelectedState(group.items)"
                    :indeterminate="groupSelectedState(group.items) === null"
                    :disabled="newSlugsInGroup(group.items).length === 0"
                    size="sm"
                    hide-details
                    bare
                    @click.stop
                    @update:model-value="(v) => toggleGroup(group.items, v)"
                  />
                </template>
                <template #title>
                  <span class="r-setup-platforms__group-label">
                    {{ group.label }}
                  </span>
                </template>
                <template #header-append>
                  <span class="r-setup-platforms__group-count">
                    {{ group.items.length }}
                  </span>
                </template>

                <!-- Mount once on first open; keep mounted so re-opens
                     animate smoothly without remounting all icons. -->
                <ul
                  v-if="mountedGroups.has(group.key)"
                  class="r-setup-platforms__items r-setup-platforms__items--nested"
                >
                  <li
                    v-for="platform in group.items"
                    :key="platform.fs_slug"
                    class="r-setup-platforms__item"
                    :data-state="
                      isSelected(platform.fs_slug) ? 'selected' : 'available'
                    "
                    role="checkbox"
                    :aria-checked="isSelected(platform.fs_slug)"
                    :tabindex="0"
                    @click="
                      togglePlatform(
                        platform.fs_slug,
                        !isSelected(platform.fs_slug),
                      )
                    "
                    @keydown.space.prevent="
                      togglePlatform(
                        platform.fs_slug,
                        !isSelected(platform.fs_slug),
                      )
                    "
                    @keydown.enter.prevent="
                      togglePlatform(
                        platform.fs_slug,
                        !isSelected(platform.fs_slug),
                      )
                    "
                  >
                    <RCheckbox
                      :model-value="isSelected(platform.fs_slug)"
                      size="sm"
                      hide-details
                      bare
                      @click.stop
                      @update:model-value="
                        (v) => togglePlatform(platform.fs_slug, v)
                      "
                    />
                    <RPlatformIcon
                      :slug="platform.slug"
                      :fs-slug="platform.fs_slug"
                      :name="platform.name"
                      :size="26"
                      :show-tooltip="false"
                      class="r-setup-platforms__item-icon"
                    />
                    <div class="r-setup-platforms__item-body">
                      <span class="r-setup-platforms__item-name">
                        {{ platform.name || platform.fs_slug }}
                      </span>
                      <span class="r-setup-platforms__item-slug">
                        {{ platform.fs_slug }}
                      </span>
                    </div>
                    <div class="r-setup-platforms__item-state">
                      <RChip
                        v-if="isSelected(platform.fs_slug)"
                        size="x-small"
                        variant="translucent"
                        color="success"
                      >
                        <RIcon name="mdi-folder-plus" :size="12" />
                        <code>{{ platformFolderPath(platform.fs_slug) }}</code>
                      </RChip>
                    </div>
                  </li>
                </ul>
              </RCollapsible>
            </li>
          </ul>
        </div>
      </section>
    </div>

    <!-- Summary bar -->
    <div class="r-setup-platforms__summary" role="status">
      <span class="r-setup-platforms__summary-text">
        <strong>
          {{
            selectedNewPlatforms.length === 0
              ? t("setup.footer-create-summary-none")
              : selectedNewPlatforms.length === 1
                ? t("setup.footer-create-summary-one")
                : t("setup.footer-create-summary-many", {
                    count: selectedNewPlatforms.length,
                  })
          }}
        </strong>
        <span class="r-setup-platforms__summary-pattern">
          {{
            t("setup.footer-create-summary-under", {
              pattern: structurePattern,
            })
          }}
        </span>
      </span>
    </div>
  </section>
</template>

<style scoped>
.r-setup-platforms {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
  min-height: 0;
  flex: 1 1 auto;
}

.r-setup-platforms__lead {
  margin: 0 auto;
  max-width: 900px;
  text-align: center;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

/* ── Structure banner ────────────────────────────────────────────── */
.r-setup-platforms__banner {
  display: flex;
  align-items: center;
  padding: var(--r-space-3) var(--r-space-4);
  border-radius: var(--r-radius-md);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
}

.r-setup-platforms__banner[data-tone="info"] {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 30%,
    transparent
  );
  background: color-mix(in srgb, var(--r-color-brand-primary) 6%, transparent);
}

.r-setup-platforms__banner[data-tone="warning"] {
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 35%,
    transparent
  );
  background: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 8%,
    transparent
  );
}

.r-setup-platforms__banner-text {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
  min-width: 0;
}

.r-setup-platforms__banner-text strong {
  color: var(--r-color-fg);
  font-weight: var(--r-font-weight-semibold);
}

.r-setup-platforms__banner-pattern {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  padding: 2px 6px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
  color: var(--r-color-fg);
}

.r-setup-platforms__banner-meta {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
}

/* ── Two-column body ─────────────────────────────────────────────── */
.r-setup-platforms__columns {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--r-space-5);
}

@media (max-width: 800px) {
  .r-setup-platforms__columns {
    grid-template-columns: 1fr;
  }
}

.r-setup-platforms__pane {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-setup-platforms__pane-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-right: var(--r-space-1);
}

.r-setup-platforms__section-head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-setup-platforms__section-title {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  margin: 0;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
}

/* ── Toolbar ─────────────────────────────────────────────────────── */
.r-setup-platforms__toolbar {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  flex-wrap: wrap;
}

.r-setup-platforms__search {
  flex: 1 1 240px;
  min-width: 200px;
  max-width: 360px;
}

/* ── Items list (shared) ─────────────────────────────────────────── */
.r-setup-platforms__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-setup-platforms__items--nested {
  padding-left: var(--r-space-6);
  margin-top: var(--r-space-2);
}

.r-setup-platforms__item {
  display: grid;
  grid-template-columns: 18px 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-2) var(--r-space-3);
  min-height: 44px;
  border-radius: var(--r-radius-md);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  cursor: pointer;
  transition:
    background 150ms ease,
    border-color 150ms ease;
}

/* Detected items have no leading checkbox column. */
.r-setup-platforms__item[data-state="detected"] {
  grid-template-columns: 28px minmax(0, 1fr) auto;
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 25%,
    transparent
  );
  cursor: default;
}

.r-setup-platforms__item[data-state="selected"] {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 10%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 30%,
    transparent
  );
}

.r-setup-platforms__item[data-state="available"]:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
}

.r-setup-platforms__item-icon {
  width: 26px;
  height: 26px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  padding: 2px;
  flex-shrink: 0;
}

.r-setup-platforms__item-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.r-setup-platforms__item-name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-setup-platforms__item-slug {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-setup-platforms__item-state {
  display: flex;
  align-items: center;
}

.r-setup-platforms__item-state code {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  margin-left: var(--r-space-1);
}

/* ── Groups (browse mode) ────────────────────────────────────────── */
.r-setup-platforms__groups {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-setup-platforms__group {
  border-radius: var(--r-radius-md);
}

.r-setup-platforms__group-label {
  font-weight: var(--r-font-weight-semibold);
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg);
}

.r-setup-platforms__group-count {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  padding: 2px var(--r-space-2);
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-fg) 6%, transparent);
}

/* ── Summary ─────────────────────────────────────────────────────── */
.r-setup-platforms__summary {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  padding: var(--r-space-3);
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}

.r-setup-platforms__summary :deep(.r-icon) {
  flex-shrink: 0;
}

.r-setup-platforms__summary-text {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

.r-setup-platforms__summary-text strong {
  color: var(--r-color-fg);
  font-weight: var(--r-font-weight-semibold);
}

.r-setup-platforms__summary-pattern {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
</style>
