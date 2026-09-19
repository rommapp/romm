import { debounce } from "lodash";
import { computed, ref } from "vue";
import socket from "@/services/socket";

const UPGRADE_RECHECK_MS = 2500;

export function transportLooksDegraded(
  transportName: string | undefined,
): boolean {
  return transportName === "polling";
}

const websocketDegraded = ref(false);
let installed = false;

function syncDegradedFromTransport() {
  websocketDegraded.value = transportLooksDegraded(
    socket.io?.engine?.transport?.name,
  );
}

function bindEngineUpgradeListener() {
  const engine = socket.io?.engine;
  if (!engine) return;
  const onUpgrade = () => {
    websocketDegraded.value = false;
  };
  engine.off("upgrade", onUpgrade);
  engine.on("upgrade", onUpgrade);
}

function install() {
  const onConnect = () => {
    bindEngineUpgradeListener();
    syncDegradedFromTransport();
    setTimeout(() => syncDegradedFromTransport(), UPGRADE_RECHECK_MS);
  };

  socket.on("connect", onConnect);
  socket.on(
    "connect_error",
    debounce(() => {
      websocketDegraded.value = true;
    }, 300),
  );

  if (socket.connected) {
    onConnect();
  }
}

export function useSocketTransportHealth() {
  if (!installed) {
    installed = true;
    install();
  }

  const isWebSocketDegraded = computed(() => websocketDegraded.value);

  function retryWebSocket() {
    if (socket.connected) {
      socket.disconnect();
    }
    socket.connect();
  }

  return { isWebSocketDegraded, retryWebSocket };
}
