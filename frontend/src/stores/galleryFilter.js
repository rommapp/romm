import { defineStore } from 'pinia'
import { normalizeString } from '@/utils/utils.js'

export const storeGalleryFilter = defineStore('galleryFilter', {
  state: () => ({ value: '' }),

  actions: {
    set(filter) { this.value = normalizeString(filter) }
  }
})