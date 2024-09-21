export default class DiskDevice {
  module: unknown;
  doneFlag: boolean;
  file: File | null;

  constructor(module: unknown) {
    this.module = module;
    this.doneFlag = false;
    this.file = null;
  }

  read(dstPtr: number, offset: number, size: number) {
    if (!this.file) {
      throw new Error("No file set.");
    }
    this.doneFlag = false;
    const subsection = this.file.slice(offset, offset + size);
    subsection.arrayBuffer().then((value: ArrayBuffer) => {
      // @ts-ignore
      this.module.HEAPU8.set(new Uint8Array(value), dstPtr);
      this.doneFlag = true;
    });
  }

  getFileSize() {
    if (!this.file) {
      throw new Error("No file set.");
    }
    return this.file.size;
  }

  isDone() {
    return this.doneFlag;
  }

  setFile(file: File) {
    this.file = file;
  }
}
