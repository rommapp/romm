import api from "@/services/api";

export interface DeviceAuthPendingSchema {
  client_device_identifier: string;
  name: string;
  client: string;
  platform: string | null;
  client_version: string | null;
  requested_scopes: string[];
  allowed_scopes: string[];
  expires_at: string;
}

export interface DeviceAuthApproveResponse {
  device_id: string;
  device_name: string | null;
}

async function getPending(userCode: string) {
  return api.get<DeviceAuthPendingSchema>(
    `/auth/device/pending/${encodeURIComponent(userCode)}`,
  );
}

async function approve({
  userCode,
  approvedScopes,
  deviceName,
  expiresIn,
}: {
  userCode: string;
  approvedScopes: string[];
  deviceName?: string;
  expiresIn?: string;
}) {
  return api.post<DeviceAuthApproveResponse>("/auth/device/approve", {
    user_code: userCode,
    approved_scopes: approvedScopes,
    device_name: deviceName,
    expires_in: expiresIn,
  });
}

async function deny(userCode: string) {
  return api.post("/auth/device/deny", { user_code: userCode });
}

export default {
  getPending,
  approve,
  deny,
};
