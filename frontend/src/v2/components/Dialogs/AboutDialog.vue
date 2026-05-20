<script setup lang="ts">
// v2 AboutDialog — emitter-driven. Replaces the v1 AboutDialog in the v2
// GlobalDialogs stack so the "About" entry in UserMenu renders the v2 glass
// panel instead of the legacy card.
import { RDialog, RIcon, RImg } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeatStore = storeHeartbeat();
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

const links: Link[] = [
  {
    isotipo: true,
    label: "RomM version",
    value: heartbeatStore.value.SYSTEM.VERSION,
    href: `https://github.com/rommapp/romm/releases/tag/${heartbeatStore.value.SYSTEM.VERSION}`,
  },
  {
    icon: "mdi-code-braces",
    label: "Source code",
    value: "GitHub",
    href: "https://github.com/rommapp/romm",
  },
  {
    icon: "mdi-file-document-outline",
    label: "Documentation",
    value: "docs.romm.app",
    href: "https://docs.romm.app",
  },
  {
    icon: "mdi-account-group",
    label: "Community",
    value: "Discord",
    href: "https://discord.com/invite/P5HtHnhUDH",
  },
];

void t;
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-help-circle-outline"
    width="520"
    @close="closeDialog"
  >
    <template #header>
      <span>About RomM</span>
    </template>
    <template #content>
      <div class="r-v2-about">
        <a
          v-for="link in links"
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
        </a>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-about {
  display: grid;
  grid-template-columns: 1fr 1fr;
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
  grid-template-columns: 1fr;
}
</style>
