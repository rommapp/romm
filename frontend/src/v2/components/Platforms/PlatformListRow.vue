<script setup lang="ts">
// PlatformListRow — single row of the Platforms list-mode index.
//
// Anatomy mirrors GameListRow: thumb (RPlatformIcon) + name stack on the
// left, game count column on the right. Click navigates to /platform/<id>
// with the same shared-element morph as PlatformTile so switching between
// grid and list modes lands on the same destination animation.
import { RPlatformIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { usePlatformPlayable } from "@/v2/composables/usePlatformPlayable";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";
import PlayModeBadge from "./PlayModeBadge.vue";
import {
  platformGenerationLabel,
  prettifyPlatformCategory,
} from "./platformListColumns";

defineOptions({ inheritAttrs: false });

interface Props {
  id: number | string;
  slug: string;
  fsSlug?: string;
  displayName: string;
  romCount?: number | null;
  /** Optional metadata — same axes the toolbar can group by. Each
   *  renders an em-dash when missing so columns line up regardless. */
  familyName?: string | null;
  category?: string | null;
  generation?: number | null;
}

const props = withDefaults(defineProps<Props>(), {
  fsSlug: undefined,
  romCount: null,
  familyName: null,
  category: null,
  generation: null,
});

const router = useRouter();
const { t } = useI18n();
// Phones and tablets have no room for the columns: the row goes two-line,
// the same shape the collections list takes.
const { smAndDown } = useBreakpoint();
const iconEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();

const href = computed(() => `/platform/${props.id}`);

const morphName = computed(() => `platform-icon-${props.id}`);

const morphStyle = computed(() =>
  pendingMorphName.value === morphName.value
    ? { viewTransitionName: morphName.value }
    : undefined,
);

const categoryLabel = computed(() =>
  props.category ? prettifyPlatformCategory(props.category) : null,
);
const generationLabel = computed(() =>
  typeof props.generation === "number" && props.generation > 0
    ? platformGenerationLabel(props.generation)
    : null,
);

const { emulator, mode, streamLabel } = usePlatformPlayable(() => props.slug);

function onRowClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!iconEl.value) return;
  e.preventDefault();
  morphTransition({ el: iconEl.value, name: morphName.value }, async () => {
    await router.push(href.value);
  });
}
</script>

<template>
  <a
    v-if="smAndDown"
    class="plat-list-row plat-list-row--compact r-list-compact"
    :href="href"
    :aria-label="t('common.open-item', { name: displayName })"
    @click="onRowClick"
  >
    <div ref="iconEl" class="plat-list-row__thumb" :style="morphStyle">
      <RPlatformIcon
        :slug="slug"
        :fs-slug="fsSlug"
        :alt="displayName"
        :size="40"
        :show-tooltip="false"
      />
    </div>
    <div class="r-list-compact__stack">
      <div class="plat-list-row__name">{{ displayName }}</div>
      <div class="r-list-compact__facts">
        <span>{{
          t("collection.games-count", romCount ?? 0, {
            named: { n: romCount ?? 0 },
          })
        }}</span>
        <template v-if="categoryLabel">
          <span class="r-list-compact__dot">·</span>
          <span>{{ categoryLabel }}</span>
        </template>
        <template v-if="familyName">
          <span class="r-list-compact__dot">·</span>
          <span>{{ familyName }}</span>
        </template>
      </div>
    </div>
    <PlayModeBadge
      v-if="mode"
      class="plat-list-row__playable"
      :mode="mode"
      :emulator="emulator"
      :stream-label="streamLabel"
      :size="18"
    />
  </a>

  <a
    v-else
    class="plat-list-row"
    :href="href"
    :aria-label="t('common.open-item', { name: displayName })"
    @click="onRowClick"
  >
    <div class="plat-list-row__cell plat-list-row__title">
      <div ref="iconEl" class="plat-list-row__thumb" :style="morphStyle">
        <RPlatformIcon
          :slug="slug"
          :fs-slug="fsSlug"
          :alt="displayName"
          :size="40"
          :show-tooltip="false"
        />
      </div>
      <div class="plat-list-row__meta">
        <div class="plat-list-row__name">{{ displayName }}</div>
        <div class="plat-list-row__slug">{{ slug }}</div>
      </div>
    </div>

    <div class="plat-list-row__cell plat-list-row__cell--meta">
      <span v-if="familyName">{{ familyName }}</span>
      <span v-else class="plat-list-row__placeholder">—</span>
    </div>
    <div class="plat-list-row__cell plat-list-row__cell--meta">
      <span v-if="categoryLabel">{{ categoryLabel }}</span>
      <span v-else class="plat-list-row__placeholder">—</span>
    </div>
    <div class="plat-list-row__cell plat-list-row__cell--meta">
      <span v-if="generationLabel">{{ generationLabel }}</span>
      <span v-else class="plat-list-row__placeholder">—</span>
    </div>
    <div
      class="plat-list-row__cell plat-list-row__cell--meta plat-list-row__cell--center"
    >
      <PlayModeBadge
        v-if="mode"
        class="plat-list-row__playable"
        :mode="mode"
        :emulator="emulator"
        :stream-label="streamLabel"
        :size="18"
      />
      <span
        v-else
        class="plat-list-row__playable plat-list-row__playable--off"
        role="img"
        :aria-label="t('platform.playable-none')"
      >
        <RIcon icon="mdi-cancel" size="18" />
        <RTooltip
          activator="parent"
          :text="t('platform.playable-none')"
          location="top"
        />
      </span>
    </div>

    <div class="plat-list-row__cell plat-list-row__cell--end">
      <span v-if="romCount != null">{{
        t("collection.games-count", romCount, { named: { n: romCount } })
      }}</span>
      <span v-else class="plat-list-row__count-unit">—</span>
    </div>
  </a>
</template>

<style scoped>
/* Grid template kept in lock-step with PLATFORM_LIST_GRID_TEMPLATE in
   platformListColumns.ts (the constant is exported for the index
   view's narrative; the row applies it via CSS so the breakpoint
   switch can override without an inline-style override fight). */
.plat-list-row {
  /* Runs to the screen edges wherever the shell asks for it. */
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px 130px 110px 88px 96px;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.plat-list-row:hover {
  background: var(--r-color-bg-elevated);
}

/* Compact (phones / tablets): icon + name, and the columns collapse into
   one line of facts. */
/* Clear of the screen edge, which the row itself runs to. */
.plat-list-row--compact .plat-list-row__playable {
  margin-inline-end: var(--r-space-2);
}

.plat-list-row:focus-visible {
  outline: none;
  background: var(--r-color-bg-elevated);
  box-shadow: inset 0 0 0 2px var(--r-color-brand-primary);
}

.plat-list-row__cell {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plat-list-row__cell--meta {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.plat-list-row__placeholder {
  color: var(--r-color-fg-faint);
}

.plat-list-row__cell--end {
  display: flex;
  justify-content: flex-end;
}

.plat-list-row__cell--center {
  display: flex;
  justify-content: center;
}

.plat-list-row__title {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  min-width: 0;
}

.plat-list-row__thumb {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  opacity: 0.9;
}

.plat-list-row__playable {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.plat-list-row__playable--off {
  color: var(--r-color-fg-faint);
}

.plat-list-row__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.plat-list-row__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plat-list-row__slug {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plat-list-row__count-unit {
  color: var(--r-color-fg-muted);
}
</style>
