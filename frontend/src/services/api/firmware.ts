import type { FirmwareSchema } from "@/__generated__";
import api from "@/services/api/index";

export const firmwareApi = api;

async function getFirmware({
    platformId = null,
}: {
    platformId?: number | null;
}): Promise<{ data: FirmwareSchema[] }> {
    return firmwareApi.get(`/firmware`, {
        params: {
            platform_id: platformId,
        },
    });
}

export default {
    getFirmware,
}
