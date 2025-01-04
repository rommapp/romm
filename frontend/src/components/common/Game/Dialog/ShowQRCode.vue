<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import RDialog from "@/components/common/RDialog.vue";
import { getDownloadLink } from "@/utils";
import type { Emitter } from "mitt";
import { inject, nextTick, ref } from "vue";
import { useDisplay } from "vuetify";
import qrcode from "qrcode";

const { lgAndUp } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");

emitter?.on("showQRCodeDialog", async (romToView: SimpleRom) => {
  show.value = true;

  await nextTick();

  const downloadLink =
    romToView.file_extension.toLowerCase() === "cia"
      ? getDownloadLink({
          rom: romToView,
          files: [],
        })
      : getDownloadLink({
          rom: romToView,
          files: [
            romToView.files.filter((f) => f["filename"].endsWith(".cia"))[0]
              .filename,
          ],
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
    :width="lgAndUp ? 400 : 300"
  >
    <template #content>
      <v-row no-gutters>
        <v-col cols="12" class="text-center">
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
