import Cookies from "js-cookie";
import api from "@/services/api";

interface PlaySessionEntry {
  rom_id: number;
  start_time: string;
  end_time: string;
  duration_ms: number;
}

async function ingestPlaySessions({
  deviceId = null,
  sessions,
}: {
  deviceId?: string | null;
  sessions: PlaySessionEntry[];
}) {
  return api.post("/play-sessions", {
    device_id: deviceId,
    sessions,
  });
}

function ingestPlaySessionsKeepalive({
  deviceId = null,
  sessions,
}: {
  deviceId?: string | null;
  sessions: PlaySessionEntry[];
}): void {
  void fetch("/api/play-sessions", {
    method: "POST",
    keepalive: true,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "x-csrftoken": Cookies.get("romm_csrftoken") ?? "",
    },
    body: JSON.stringify({ device_id: deviceId, sessions }),
  }).catch((err) => console.error("Failed to submit play session:", err));
}

export default { ingestPlaySessions, ingestPlaySessionsKeepalive };
