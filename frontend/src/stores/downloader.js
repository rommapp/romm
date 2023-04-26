import { defineStore } from 'pinia'

export const storeDownloader = defineStore('downloader', {
  state: () => ({ value: [] }),

  actions: {
    add(rom) { this.value.push(rom) },
    remove(rom) { this.value.splice(this.value.indexOf(rom), 1) }
  }
})