<script setup>
import { storeFilter } from '@/stores/filter'
import { inject } from 'vue'

// Props
const filter = storeFilter()

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-app-bar-nav-icon
        rounded="0"
        @click="filter.toggleFilterBar();emitter.emit('filter')">
        <v-icon>mdi-magnify</v-icon>
    </v-app-bar-nav-icon>
</template>
