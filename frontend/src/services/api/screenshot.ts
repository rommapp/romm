import type {
  Body_add_screenshot_api_screenshots_post as AddScreenshotInput,
  DetailedRomSchema,
  ScreenshotSchema,
} from "@/__generated__";
import api from "@/services/api";

export const screenshotApi = api;

type ScreenshotUploadInput = AddScreenshotInput & {
  screenshotFile: File;
};

async function uploadScreenshots({
  rom,
  screenshotsToUpload,
  emulator,
}: {
  rom: DetailedRomSchema;
  screenshotsToUpload: ScreenshotUploadInput[];
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
  screenshotFile: ScreenshotUploadInput["screenshotFile"];
}): Promise<{ data: ScreenshotSchema }> {
  const formData = new FormData();
  formData.append("screenshotFile", screenshotFile);

  return api.put(`/screenshots/${screenshot.id}`, formData);
}

export default {
  uploadScreenshots,
  updateScreenshot,
};
