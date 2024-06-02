import type {
  ScreenshotSchema,
  UploadedScreenshotsResponse,
} from "@/__generated__";
import api from "@/services/api/index";
import type { DetailedRom } from "@/stores/roms";

export const screenshotApi = api;

async function uploadScreenshots({
  rom,
  screenshots,
}: {
  rom: DetailedRom;
  screenshots: File[];
}): Promise<{ data: UploadedScreenshotsResponse }> {
  const formData = new FormData();
  screenshots.forEach((screenshot) =>
    formData.append("screenshots", screenshot),
  );

  return api.post("/screenshots", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function updateScreenshot({
  screenshot,
  file,
}: {
  screenshot: ScreenshotSchema;
  file: File;
}): Promise<{ data: ScreenshotSchema }> {
  const formData = new FormData();
  formData.append("file", file);

  return api.put(`/screenshots/${screenshot.id}`, formData);
}

export default {
  uploadScreenshots,
  updateScreenshot,
};
