<script setup lang="ts">
import type { Emitter } from "mitt";
import qrcode from "qrcode";
import { inject, nextTick, ref } from "vue";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getNintendoDSFiles, getDownloadLink, isNintendoDSFile } from "@/utils";

const { lgAndUp } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const rom = ref<SimpleRom>({} as SimpleRom);

emitter?.on("showQRCodeDialog", async (romToView: SimpleRom) => {
  show.value = true;
  rom.value = romToView;

  await nextTick();

  const isNDSFile = isNintendoDSFile(romToView);
  const matchingFiles = getNintendoDSFiles(romToView);

  const downloadLink = getDownloadLink({
    rom: romToView,
    fileIDs: isNDSFile ? [] : [matchingFiles[0].id],
  });

  const qrCode = document.getElementById("qr-code");
  qrcode.toCanvas(qrCode, downloadLink, {
    margin: 1,
    width: lgAndUp ? 300 : 200,
  });
});

function closeDialog() {
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    :width="lgAndUp ? 400 : 400"
    @close="closeDialog"
  >
    <template #content>
      <v-row no-gutters>
        <v-col cols="12" class="text-center px-4">
          <h3 class="mt-5">
            {{ rom.name }}
          </h3>
          <h4 class="text-primary">
            {{ rom.fs_name }}
          </h4>
          <canvas id="qr-code" />
        </v-col>
      </v-row>
    </template>
  </RDialog>
</template>

<style scoped>
canvas {
  margin: 2rem;
}
</style>
