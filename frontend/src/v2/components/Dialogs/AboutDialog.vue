<script setup lang="ts">
// v2 AboutDialog — emitter-driven. Replaces the v1 AboutDialog in the v2
// GlobalDialogs stack so the "About" entry in UserMenu renders the v2 glass
// panel instead of the legacy card.
import { RDialog, RIcon, RImg, RTooltip } from "@v2/lib";
import { useResizeObserver } from "@vueuse/core";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { Events } from "@/types/emitter";
import { useVersionDisplay } from "@/v2/composables/useVersionDisplay";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { version, href: versionHref } = useVersionDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const show = ref(false);

const openHandler = () => {
  show.value = true;
};
emitter?.on("showAboutDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showAboutDialog", openHandler));

function closeDialog() {
  show.value = false;
}

type Link = {
  icon?: string;
  isotipo?: boolean;
  label: string;
  value: string;
  href: string;
};

const links = computed<Link[]>(() => [
  {
    isotipo: true,
    label: t("common.about-version"),
    value: version.value,
    href: versionHref.value,
  },
  {
    icon: "mdi-code-braces",
    label: t("common.about-source-code"),
    value: "GitHub",
    href: "https://github.com/rommapp/romm",
  },
  {
    icon: "mdi-file-document-outline",
    label: t("common.about-documentation"),
    value: "docs.romm.app",
    href: "https://docs.romm.app",
  },
  {
    icon: "mdi-account-group",
    label: t("common.about-community"),
    value: "Discord",
    href: "https://discord.com/invite/P5HtHnhUDH",
  },
]);

// Which tiles cut their value off, and then show it in full. Measured whenever
// the grid lays out or a value changes, as RTooltip decides on the pointer's arrival.
const grid = ref<HTMLElement | null>(null);
const truncated = ref<boolean[]>([]);

function measure() {
  truncated.value = Array.from(
    grid.value?.querySelectorAll(".r-v2-about__value") ?? [],
    (value) => value.scrollWidth > value.clientWidth,
  );
}

useResizeObserver(grid, measure);
watch(() => links.value.map((link) => link.value), measure, { flush: "post" });
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-help-circle-outline"
    width="520"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("common.about-romm") }}</span>
    </template>
    <template #content>
      <div ref="grid" class="r-v2-about">
        <a
          v-for="(link, index) in links"
          :key="link.label"
          :href="link.href"
          target="_blank"
          rel="noopener noreferrer"
          class="r-v2-about__tile"
        >
          <div class="r-v2-about__icon">
            <RImg
              v-if="link.isotipo"
              src="/assets/isotipo.svg"
              alt="RomM"
              :width="18"
              :height="18"
              contain
            />
            <RIcon v-else-if="link.icon" :icon="link.icon" size="18" />
          </div>
          <div class="r-v2-about__meta">
            <span class="r-v2-about__label">{{ link.label }}</span>
            <span class="r-v2-about__value">{{ link.value }}</span>
          </div>
          <RIcon icon="mdi-open-in-new" size="14" class="r-v2-about__chev" />
          <RTooltip
            activator="parent"
            :text="link.value"
            :disabled="!truncated[index]"
          />
        </a>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-about {
  display: grid;
  /* A 0 minimum, so a long value (a branch name) truncates instead of
     widening its column past the dialog. */
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.r-v2-about__tile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  text-decoration: none;
  color: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-about__tile:hover {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
  transform: translateY(-1px);
}

.r-v2-about__icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--r-color-surface);
  color: var(--r-color-fg);
  flex-shrink: 0;
}

.r-v2-about__meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.r-v2-about__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--r-color-fg-muted);
}

.r-v2-about__value {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-about__chev {
  color: var(--r-color-fg-muted);
}
.r-v2-about__tile:hover .r-v2-about__chev {
  color: var(--r-color-fg);
}

html[data-bp~="xs"] .r-v2-about {
  grid-template-columns: minmax(0, 1fr);
}
</style>
