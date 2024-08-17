import { defineStore } from "pinia";

class UploadingRom {
  filename = "";
  progress = 0;
  file_size = 0;
  uploaded_size = 0;
  upload_speed = 0;
  finished = false;

  constructor(data: Partial<UploadingRom>) {
    Object.assign(this, data);
  }
}

export default defineStore("upload", {
  state: () => ({
    value: [] as UploadingRom[],
  }),
  actions: {
    add(filename: string) {
      this.value = [...this.value, new UploadingRom({ filename })];
    },
    update(
      filename: string,
      {
        file_size,
        uploaded_size,
        upload_speed,
      }: {
        file_size: number;
        uploaded_size: number;
        upload_speed: number;
      },
    ) {
      this.value = this.value.map((rom) =>
        rom.filename === filename
          ? {
              ...rom,
              file_size,
              uploaded_size,
              upload_speed,
              progress: (uploaded_size / file_size) * 100,
              finished: uploaded_size === file_size,
            }
          : rom,
      );
    },
    markComplete(filename: string) {
      this.value = this.value.map((rom) =>
        rom.filename === filename
          ? {
              ...rom,
              progress: 100,
              upload_speed: 0,
              finished: true,
            }
          : rom,
      );
    },
    clear() {
      this.value = [] as UploadingRom[];
    },
  },
});
