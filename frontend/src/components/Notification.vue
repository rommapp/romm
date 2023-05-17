<script setup>
import { ref, inject } from "vue"

// Props
const snackbarShow = ref(false)
const snackbarStatus = ref({})

// Event listeners bus
const emitter = inject('emitter')
emitter.on('snackbarShow', (snackbar) => {
  snackbarShow.value = true
  snackbarStatus.value = snackbar
})
</script>

<template>
    <v-snackbar v-model="snackbarShow" :timeout="4000" location="top" color="notification">
        <v-icon :icon="snackbarStatus.icon" :color="snackbarStatus.color" class="ml-2 mr-2"/>
        {{ snackbarStatus.msg }}
        <template v-slot:actions>
            <v-btn @click="snackbarShow=false" variant="text"><v-icon icon="mdi-close"/></v-btn>
        </template>
    </v-snackbar>    
</template>
