import { defineStore } from 'pinia'

export const storePlatforms = defineStore('platforms', {
  state: () => ({ value: [] }),

  actions: {
    add(platforms) {
      this.value = platforms
    }
  }
})