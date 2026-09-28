<script setup lang="ts">
// AlphaJumpMenu: the gallery's jump-to-letter on phones and tablets, where
// the AlphaStrip column would eat into the grid: a toolbar button that opens
// the same letters as a grid.
import { RBtn, RMenu } from "@v2/lib";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import AlphaStrip from "@/v2/components/Gallery/AlphaStrip.vue";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";

interface Props {
  available: Set<string>;
  current: string;
  direction: "asc" | "desc";
}

defineProps<Props>();

const emit = defineEmits<{
  (e: "pick", letter: string): void;
}>();

const { t } = useI18n();

const LETTER_SELECTOR = ".alpha-strip__btn:not(:disabled)";
// Opened from a keyboard or pad, start on the current letter so the arrows
// have somewhere to move from.
const INITIAL_FOCUS = [
  ".alpha-strip__btn--current:not(:disabled)",
  LETTER_SELECTOR,
];

const open = ref(false);
const gridEl = ref<HTMLElement | null>(null);
useWrapGridNav(gridEl, { cellSelector: LETTER_SELECTOR });
</script>

<template>
  <RMenu
    v-model="open"
    location="bottom end"
    sheet-on-mobile
    :initial-focus="INITIAL_FOCUS"
  >
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-bind="activatorProps"
        variant="outlined"
        surface
        :icon="true"
        rounded="circle"
        class="alpha-jump__btn"
        :aria-label="t('gallery.jump-to-letter')"
      >
        A–Z
      </RBtn>
    </template>
    <div ref="gridEl">
      <AlphaStrip
        grid
        :available="available"
        :current="current"
        :direction="direction"
        @pick="emit('pick', $event)"
      />
    </div>
  </RMenu>
</template>

<style scoped>
.alpha-jump__btn {
  flex: none;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.02em;
}
</style>
