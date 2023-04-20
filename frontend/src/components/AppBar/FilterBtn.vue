<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-app-bar-nav-icon
        rounded="0"
        @click="emitter.emit('isFiltering')">
        <v-icon>mdi-magnify</v-icon>
    </v-app-bar-nav-icon>
</template>
