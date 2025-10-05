<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import CopyRomDownloadLinkDialog from "@/components/common/Game/Dialog/CopyDownloadLink.vue";
import PlayBtn from "@/components/common/Game/PlayBtn.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getDownloadLink, isNintendoDSRom } from "@/utils";

const props = defineProps<{ rom: DetailedRom }>();
const downloadStore = storeDownload();
const emitter = inject<Emitter<Events>>("emitter");
const qrCodeIcon = ref("mdi-qrcode");
const auth = storeAuth();
const { t } = useI18n();

const isNDSRom = computed(() => {
  return isNintendoDSRom(props.rom);
});

async function copyDownloadLink(rom: DetailedRom) {
  const downloadLink = getDownloadLink({
    rom,
    fileIDs: downloadStore.fileIDsToDownload,
  });
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(downloadLink);
    emitter?.emit("snackbarShow", {
      msg: "Download link copied to clipboard!",
      icon: "mdi-check-bold",
      color: "green",
      timeout: 2000,
    });
  } else {
    emitter?.emit("showCopyDownloadLinkDialog", downloadLink);
  }
}
</script>

<template>
  <div>
    <v-btn-group divided density="compact" class="d-flex flex-row">
      <v-btn
        :disabled="downloadStore.value.includes(rom.id) || rom.missing_from_fs"
        class="flex-grow-1"
        :aria-label="`Download ${rom.name}`"
        @click="
          romApi.downloadRom({
            rom,
            fileIDs: downloadStore.fileIDsToDownload,
          })
        "
      >
        <v-tooltip
          activator="parent"
          location="top"
          transition="fade-transition"
          open-delay="1000"
        >
          {{ t("rom.download") }} {{ rom.name }}
        </v-tooltip>
        <v-icon icon="mdi-download" size="large" />
      </v-btn>
      <v-btn
        :disabled="rom.missing_from_fs"
        :aria-label="`Copy download link ${rom.name}`"
        class="flex-grow-1"
        @click="copyDownloadLink(rom)"
      >
        <v-tooltip
          activator="parent"
          location="top"
          transition="fade-transition"
          open-delay="1000"
        >
          {{ t("rom.copy-link") }}
        </v-tooltip>
        <v-icon icon="mdi-content-copy" />
      </v-btn>
      <PlayBtn :rom="rom" class="flex-grow-1" />
      <v-btn
        v-if="isNDSRom"
        :disabled="rom.missing_from_fs"
        class="flex-grow-1"
        :aria-label="`Show ${rom.name} QR code`"
        @click="emitter?.emit('showQRCodeDialog', rom)"
      >
        <v-icon :icon="qrCodeIcon" />
      </v-btn>
      <v-menu
        v-if="
          auth.scopes.includes('roms.write') ||
          auth.scopes.includes('roms.user.write') ||
          auth.scopes.includes('collections.write')
        "
        location="bottom"
      >
        <template #activator="{ props: menuProps }">
          <v-btn
            :aria-label="`${rom.name} admin menu`"
            class="flex-grow-1"
            v-bind="menuProps"
          >
            <v-icon icon="mdi-dots-vertical" size="large" />
          </v-btn>
        </template>
        <AdminMenu :rom="rom" />
      </v-menu>
    </v-btn-group>

    <CopyRomDownloadLinkDialog />
  </div>
</template>
