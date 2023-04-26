import { defineStore } from 'pinia'

export const storeGalleryView = defineStore('galleryView', {
  state: () => ({ value: (JSON.parse(localStorage.getItem('currentView')) || 0)}),

  actions: {
    set(view) {
      this.value = view
      localStorage.setItem('currentView', this.value)
    },
    next(){
      if(this.value == 2){this.set(0)}
      else{this.set(this.value+1)}
    }
  }
})