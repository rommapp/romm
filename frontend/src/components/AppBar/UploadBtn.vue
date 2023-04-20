<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')

// Functions
function uploadRom() {console.log("uploading rom")}
</script>

<template>
    <v-app-bar-nav-icon
        @click="uploadRom()"
        rounded="0"
        disabled>
        <v-icon>mdi-upload</v-icon>
    </v-app-bar-nav-icon>
</template>