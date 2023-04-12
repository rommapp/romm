<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-app-bar-nav-icon
        title="settings"
        @click="emitter.emit('toggleSettings')"
        class="ml-2"
        rounded="0">
        <v-icon>mdi-cog</v-icon>
    </v-app-bar-nav-icon>
</template>