import { defineStore } from 'pinia'
import { normalizeString } from '@/utils/utils.js'

export default defineStore('galleryFilter', {
  state: () => ({ value: '' }),

  actions: {
    set(filter) { this.value = normalizeString(filter) }
  }
})
