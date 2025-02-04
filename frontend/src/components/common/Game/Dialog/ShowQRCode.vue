<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import RDialog from "@/components/common/RDialog.vue";
import { get3DSCIAFiles, getDownloadLink, is3DSCIAFile } from "@/utils";
import type { Emitter } from "mitt";
import { inject, nextTick, ref } from "vue";
import { useDisplay } from "vuetify";
import qrcode from "qrcode";

const { lgAndUp } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const rom = ref<SimpleRom>(null);

emitter?.on("showQRCodeDialog", async (romToView: SimpleRom) => {
  show.value = true;
  rom.value = romToView;

  await nextTick();

  const is3DSFile = is3DSCIAFile(romToView);
  const matchingFiles = get3DSCIAFiles(romToView);

  const downloadLink = getDownloadLink({
    rom: romToView,
    fileIDs: is3DSFile ? [] : [matchingFiles[0].id],
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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    :width="lgAndUp ? 400 : 400"
  >
    <template #content>
      <v-row no-gutters>
        <v-col cols="12" class="text-center px-4">
          <h3 class="mt-5">{{ rom.name }}</h3>
          <h4 class="text-primary">{{ rom.fs_name }}</h4>
          <canvas id="qr-code"></canvas>
        </v-col>
      </v-row>
    </template>
  </r-dialog>
</template>

<style scoped>
canvas {
  margin: 2rem;
}
</style>
