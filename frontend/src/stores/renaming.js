import { defineStore } from 'pinia'

export const storeRenaming = defineStore('renaming', {
  state: () => ({ value: false }),

  actions: {
    set(renaming) { this.value = renaming }
  }
})
