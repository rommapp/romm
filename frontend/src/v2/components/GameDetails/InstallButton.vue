<script setup lang="ts">
// InstallButton — "Installing…" control for Windows ROMs, shown in the
// GameDetails ribbon while an install session is actively running. The
// "start" entry point lives on the Download button instead (see
// GameActions.vue, which opens a Download/Install choice for Windows ROMs),
// and so does "Reinstall" once a session is done/failed - this component's
// parent only mounts it while `install.isActive` is true, so it just
// navigates to the full-page /rom/:id/install (the actual progress/VNC view
// lives there) and offers Abort in its dropdown.
import type { SimpleRom } from "@/stores/roms";
import { ROUTES } from "@/plugins/router";
import type { InstallSession } from "@/v2/composables/useInstallSession";
import { RBtn, RIcon, RMenu, RMenuItem, RSpinner } from "@v2/lib";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  install: InstallSession;
  rom: SimpleRom;
  size?: "default" | "large";
}>();

const { t } = useI18n();
const router = useRouter();

function viewInstall() {
  router.push({ name: ROUTES.INSTALL, params: { rom: props.rom.id } });
}
</script>

<template>
  <div v-if="install.isActive.value" class="install-btn-group">
    <!-- The actual progress/VNC view lives on the full-page
         /rom/:id/install now, so this just navigates there. Not RBtn's own
         `loading` prop - that hides the label entirely, and this needs to
         stay readable as "Installing…" for the whole run, not just show a
         bare spinner. -->
    <RBtn
      class="r-v2-game-btn install-btn-group__main"
      variant="outlined"
      :size="size"
      @click="viewInstall"
    >
      <template #prepend>
        <RSpinner :size="14" color="currentColor" />
      </template>
      {{ t("rom.install-installing") }}
    </RBtn>

    <RMenu location="bottom end">
      <template #activator="{ props: menuProps, isOpen }">
        <RBtn
          v-bind="menuProps"
          class="r-v2-game-btn install-btn-group__arrow"
          variant="outlined"
          :size="size"
          icon
          :aria-expanded="isOpen"
          :aria-label="t('rom.install-abort')"
        >
          <RIcon icon="mdi-chevron-down" size="18" />
        </RBtn>
      </template>
      <RMenuItem
        icon="mdi-close-circle-outline"
        variant="danger"
        :label="t('rom.install-abort')"
        :disabled="install.cancelling.value"
        @click="install.cancelInstall()"
      />
    </RMenu>
  </div>
</template>

<style scoped>
.install-btn-group {
  display: flex;
  align-items: center;
}
.install-btn-group__main {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
.install-btn-group__arrow {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  border-left: 1px solid var(--r-color-border);
}
</style>
