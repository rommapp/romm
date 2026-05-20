<script setup lang="ts">
// LibraryToolsShell — page chrome shared by every Library Tools route
// (Scan / Upload / Patcher).
//
// Layout: a single column bounded by `--r-page-max-w`. A page eyebrow
// + title block sits at the top alongside an optional `#actions` slot
// (Scan uses it for the "Manage library" button). A hero card-picker
// row exposes the three tools side-by-side — the active one is
// highlighted, the others are router-links. The view's actual content
// renders inside a `.r-v2-lt__panel` glass card below the picker.
//
// Visual contract: deliberately different shape from SettingsShell so
// the user knows they're in an "operations" surface, not "config":
//   * No sidebar — the picker is horizontal at the top.
//   * Cards (not a list) communicate "pick what to do now."
//   * Content is one panel, not a stack of section cards.
//
// Active tool is decided by the route name (passed via `active`),
// which keeps ToolCard ignorant of routing details and lets stories
// drive the visual state without a router.
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";
import ToolCard from "@/v2/components/LibraryTools/ToolCard.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";

defineOptions({ inheritAttrs: false });

type ToolId = "scan" | "upload" | "patcher";

interface Props {
  active: ToolId;
  /** When `true`, renders the content slot directly without the
   *  default glass panel wrapper. Views that already provide their
   *  own surfaces (Scan's config + log columns, Patcher's panes)
   *  pass this so the embedded cards don't double-nest. Same idea as
   *  SettingsShell's `bare` prop. */
  bare?: boolean;
}
withDefaults(defineProps<Props>(), { bare: false });

const { t } = useI18n();
const { scopes } = storeToRefs(storeAuth());
const canScan = computed(() => scopes.value.includes("platforms.write"));
const canUpload = computed(() => scopes.value.includes("roms.write"));
// Patcher is always reachable (matches v1) — purely client-side worker.

interface Tool {
  id: ToolId;
  route: string;
  icon: string;
  label: string;
  description: string;
  enabled: boolean;
}

const tools = computed<Tool[]>(() => [
  {
    id: "scan",
    route: ROUTES.SCAN,
    icon: "mdi-magnify-scan",
    label: t("scan.scan"),
    description: t(
      "scan.scan-desc",
      "Pull new ROMs and metadata from your filesystem.",
    ),
    enabled: canScan.value,
  },
  {
    id: "upload",
    route: ROUTES.UPLOAD,
    icon: "mdi-cloud-upload-outline",
    label: t("common.upload-roms", "Upload ROMs"),
    description: t(
      "common.upload-roms-desc",
      "Add ROMs from your device to a platform.",
    ),
    enabled: canUpload.value,
  },
  {
    id: "patcher",
    route: ROUTES.PATCHER,
    icon: "mdi-file-cog-outline",
    label: t("common.patcher"),
    description: t(
      "common.patcher-desc",
      "Apply IPS, UPS, BPS and other patches to a ROM.",
    ),
    enabled: true,
  },
]);

// Library Tools pages share the current cover-art background from
// wherever the user came from — same no-op pattern as SettingsShell.
const setBgArt = useBackgroundArt();
setBgArt(null);
</script>

<template>
  <section class="r-v2-lt">
    <header class="r-v2-lt__head">
      <div class="r-v2-lt__head-text">
        <span class="r-v2-lt__eyebrow">{{
          t("library-tools.eyebrow", "Library")
        }}</span>
        <h1 class="r-v2-lt__title">
          {{ t("library-tools.title", "Library Tools") }}
        </h1>
      </div>
      <div v-if="$slots.actions" class="r-v2-lt__actions">
        <slot name="actions" />
      </div>
    </header>

    <!-- Hero card-picker — three tools side-by-side, active one
         highlighted. Disabled tiles render as non-clickable shells so
         the user sees which tools exist even when they lack the scope. -->
    <nav
      class="r-v2-lt__picker"
      :aria-label="t('library-tools.picker-aria', 'Library tools')"
    >
      <ToolCard
        v-for="tool in tools"
        :key="tool.id"
        :to="{ name: tool.route }"
        :icon="tool.icon"
        :label="tool.label"
        :description="tool.description"
        :active="active === tool.id"
        :disabled="!tool.enabled"
      />
    </nav>

    <div v-if="bare" class="r-v2-lt__bare">
      <slot />
    </div>
    <div v-else class="r-v2-lt__panel">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.r-v2-lt {
  width: 100%;
  max-width: var(--r-page-max-w);
  margin: 0 auto;
  padding: 28px 40px 60px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.r-v2-lt__head {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}
.r-v2-lt__head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.r-v2-lt__eyebrow {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-lt__title {
  font-size: 28px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: -0.01em;
  line-height: 1.1;
  margin: 0;
  color: var(--r-color-fg);
}
.r-v2-lt__actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.r-v2-lt__picker {
  display: flex;
  gap: 14px;
}

.r-v2-lt__panel {
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  padding: 22px;
  min-height: 320px;
}
/* Bare variant — the view owns its own surfaces. We still stack the
   content vertically so consumers can drop multiple cards/panels
   without each one needing its own flex wrapper. */
.r-v2-lt__bare {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Mobile — picker wraps so the cards stack instead of squishing into
   unreadable slivers. Content padding contracts to match settings'
   small-screen rhythm. */
html[data-bp~="sm-and-down"] .r-v2-lt {
  padding: 20px var(--r-row-pad) 48px;
  gap: 18px;
}
html[data-bp~="sm-and-down"] .r-v2-lt__picker {
  flex-direction: column;
}
html[data-bp~="sm-and-down"] .r-v2-lt__title {
  font-size: 22px;
}
</style>
