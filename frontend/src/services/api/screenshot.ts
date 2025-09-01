import type { ScreenshotSchema } from "@/__generated__";
import api from "@/services/api";
import type { DetailedRom } from "@/stores/roms";

export const screenshotApi = api;

async function uploadScreenshots({
  rom,
  screenshotsToUpload,
  emulator,
}: {
  rom: DetailedRom;
  screenshotsToUpload: {
    screenshotFile: File;
  }[];
  emulator?: string;
}): Promise<PromiseSettledResult<ScreenshotSchema>[]> {
  const promises = screenshotsToUpload.map(({ screenshotFile }) => {
    const formData = new FormData();
    formData.append("screenshotFile", screenshotFile);

    return new Promise<ScreenshotSchema>((resolve, reject) => {
      api
        .post("/screenshots", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          params: { rom_id: rom.id, emulator },
        })
        .then(({ data }) => {
          resolve(data);
        })
        .catch(reject);
    });
  });

  return Promise.allSettled(promises);
}

async function updateScreenshot({
  screenshot,
  screenshotFile,
}: {
  screenshot: ScreenshotSchema;
  screenshotFile: File;
}): Promise<{ data: ScreenshotSchema }> {
  const formData = new FormData();
  formData.append("screenshotFile", screenshotFile);

  return api.put(`/screenshots/${screenshot.id}`, formData);
}

export default {
  uploadScreenshots,
  updateScreenshot,
};
