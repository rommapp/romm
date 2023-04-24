import { defineStore } from 'pinia'
import { normalizeString } from '@/utils/utils.js'

export const storeFilter = defineStore('filter', {
  state: () => ({ 
    value: '',
    hiddenBar: false
  }),

  actions: {
    set(filter) {
      this.value = normalizeString(filter)
    },
    toggleFilterBar(){
      this.hiddenBar = !this.hiddenBar
      this.value = ''
    }
  }
})