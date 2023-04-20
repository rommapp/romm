<script setup>
import { ref, inject } from "vue"

// Props
const filter = ref('')

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-text-field 
        @click:clear="emitter.emit('filter', '')" 
        @keyup="emitter.emit('filter', filter)" 
        v-model="filter"
        label="search"
        prepend-inner-icon="mdi-magnify"
        class="shrink"
        variant="outlined"
        density="compact"
        hide-details
        clearable/>
</template>
