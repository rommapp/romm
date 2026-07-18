import api from "@/services/api";

async function ingestPlaySessions({
  deviceId = null,
  sessions,
}: {
  deviceId?: string | null;
  sessions: {
    rom_id: number;
    start_time: string;
    end_time: string;
    duration_ms: number;
  }[];
}) {
  return api.post("/play-sessions", {
    device_id: deviceId,
    sessions,
  });
}

export default { ingestPlaySessions };
