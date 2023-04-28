import { defineStore } from 'pinia'

export const storePlatforms = defineStore('platforms', {
  state: () => ({ value: [] }),

  actions: {
    set(platforms) { this.value = platforms }
  }
})