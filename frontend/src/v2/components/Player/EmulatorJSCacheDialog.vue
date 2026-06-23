<script setup lang="ts">
// v2 EmulatorJSCacheDialog — confirmation for clearing the EJS IndexedDB
// caches (saves / roms / core / states). Emitter-driven.
import { RBtn, RDialog, RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Events } from "@/types/emitter";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const show = ref(false);

const emitter = inject<Emitter<Events>>("emitter");
const openHandler = () => {
  show.value = true;
};
emitter?.on("openEmulatorJSCacheDialog", openHandler);
onBeforeUnmount(() => emitter?.off("openEmulatorJSCacheDialog", openHandler));

function clearIndexDB() {
  window.indexedDB.deleteDatabase("/data/saves");
  window.indexedDB.deleteDatabase("EmulatorJS-roms");
  window.indexedDB.deleteDatabase("EmulatorJS-core");
  window.indexedDB.deleteDatabase("EmulatorJS-states");
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-database-remove"
    width="480"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("play.clear-cache") }}</span>
    </template>
    <template #content>
      <div class="r-v2-clear-cache">
        <div class="r-v2-clear-cache__icon">
          <RIcon icon="mdi-alert-octagon-outline" size="36" />
        </div>
        <h2 class="r-v2-clear-cache__title">
          {{ t("play.clear-cache-title") }}
        </h2>
        <p class="r-v2-clear-cache__warn">
          {{ t("play.clear-cache-warning") }}
        </p>
        <p class="r-v2-clear-cache__desc">
          {{ t("play.clear-cache-description") }}
        </p>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="error"
        prepend-icon="mdi-database-remove"
        @click="clearIndexDB"
      >
        {{ t("common.confirm") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-clear-cache {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 8px 4px;
  gap: 10px;
}

.r-v2-clear-cache__icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 14%,
    transparent
  );
  color: var(--r-color-danger-fg);
  display: grid;
  place-items: center;
  margin-bottom: 4px;
}

.r-v2-clear-cache__title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-clear-cache__warn {
  margin: 0;
  color: var(--r-color-danger-fg);
  font-weight: var(--r-font-weight-semibold);
  font-size: 13px;
}

.r-v2-clear-cache__desc {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: 13px;
  line-height: 1.5;
  max-width: 360px;
}
</style>
