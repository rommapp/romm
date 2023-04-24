import { defineStore } from 'pinia'

export const storeContextBar = defineStore('contextBar', {
  state: () => ({ value: false }),

  actions: {
    toggleContextBar() {
      console.log(this.value)
      this.value = !this.value
    }
  }
})