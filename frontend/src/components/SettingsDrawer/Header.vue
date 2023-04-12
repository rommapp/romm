<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-list-item
        class="text-h5 d-flex align-center justify-center font-weight-bold bg-primary pt-4 pb-4 pl-7">
        Settings
        <v-btn
            title="close settings"
            @click="emitter.emit('toggleSettings')"
            class="ml-1"
            icon="mdi-close-box"
            rounded="0"
            variant="plain"/>
    </v-list-item>
</template>