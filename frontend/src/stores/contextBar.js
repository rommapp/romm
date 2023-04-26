import { defineStore } from 'pinia'

export const storeContextBar = defineStore('contextBar', {
  state: () => ({ value: false }),

  actions: {
    toggleContextBar() { this.value = !this.value }
  }
})