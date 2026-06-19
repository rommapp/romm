import type { AxiosProgressEvent } from "axios";
import type {
  Body_add_screenshot_api_screenshots_post as AddScreenshotInput,
  DetailedRomSchema,
  ScreenshotSchema,
} from "@/__generated__";
import api from "@/services/api";
import storeUpload from "@/stores/upload";
import { buildFormInput } from "@/utils/formData";

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
}) {
  const promises = screenshotsToUpload.map(({ screenshotFile }) => {
    const formData = buildFormInput<ScreenshotUploadInput>([
      ["screenshotFile", screenshotFile],
    ]);

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

// ---------- v2 per-user gallery screenshots ----------
// Mirrors the soundtrack upload flow (upload-store progress + allSettled).
async function uploadGalleryScreenshots({
  romId,
  filesToUpload,
}: {
  romId: number;
  filesToUpload: File[];
}) {
  const uploadStore = storeUpload();

  const promises = filesToUpload.map((file) => {
    const formData = new FormData();
    formData.append("screenshotFile", file);

    uploadStore.start(file.name);
    return new Promise<ScreenshotSchema>((resolve, reject) => {
      api
        .post<ScreenshotSchema>("/screenshots", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          params: { rom_id: romId },
          onUploadProgress: (progressEvent: AxiosProgressEvent) => {
            uploadStore.update(file.name, progressEvent);
          },
        })
        .then(({ data }) => resolve(data))
        .catch((error) => {
          uploadStore.fail(file.name, error.response?.data?.detail);
          reject(error);
        });
    });
  });

  return Promise.allSettled(promises);
}

async function deleteScreenshot({ id }: { id: number }) {
  return api.delete(`/screenshots/${id}`);
}

async function setScreenshotVisibility({
  id,
  isPublic,
}: {
  id: number;
  isPublic: boolean;
}) {
  return api.put<ScreenshotSchema>(`/screenshots/${id}`, {
    is_public: isPublic,
  });
}

export default {
  uploadScreenshots,
  uploadGalleryScreenshots,
  deleteScreenshot,
  setScreenshotVisibility,
};
