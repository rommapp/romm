<script setup>
import { inject, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import socket from "@/services/socket";
import storeScanning from "@/stores/scanning";

// Props
const emitter = inject("emitter");
const route = useRoute();
const scanning = storeScanning();

// Functions
socket.on("scan:done", () => {
  scanning.set(false);
  socket.disconnect();
  emitter.emit("refreshDrawer");
  emitter.emit("snackbarShow", {
    msg: "Scan completed successfully! Refresh to see the changes.",
    icon: "mdi-check-bold",
    color: "green",
    timeout: 4000
  });
});

socket.on("scan:done_ko", (msg) => {
  scanning.set(false);
  emitter.emit("snackbarShow", {
    msg: `Scan couldn't be completed. Something went wrong: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

async function scan() {
  scanning.set(true);
  emitter.emit("snackbarShow", {
    msg: `Scanning ${route.params.platform}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [route.params.platform],
    rescan: false,
  });
}

onBeforeUnmount(() => {
  socket.off("scan:done");
  socket.off("scan:done_ko");
});
</script>

<template>
    <v-btn
      @click="scan"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-magnify-scan"
    />
</template>