import { defineStore } from 'pinia'

export const storeScanning = defineStore('scanning', {
  state: () => ({ value: false }),

  actions: {
    set(scanning) { this.value = scanning }
  }
})