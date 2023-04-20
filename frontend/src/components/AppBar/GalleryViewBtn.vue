<script setup>
import { ref, inject } from "vue"
import { views } from '@/utils/utils.js'

// Event listeners bus
const emitter = inject('emitter')
const currentView = ref(JSON.parse(localStorage.getItem('currentView')) || 0)

// Functions
function changeView() {
    if(currentView.value == 2){currentView.value = 0}
    else{currentView.value = currentView.value + 1}
    emitter.emit('currentView', currentView.value)
    localStorage.setItem('currentView', currentView.value)
}
</script>

<template>
    <v-app-bar-nav-icon
        @click="changeView()"
        rounded="0">
        <v-icon :icon="views[currentView]['icon']"/>
    </v-app-bar-nav-icon>
</template>