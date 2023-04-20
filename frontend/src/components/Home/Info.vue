<script setup>
import { ref, inject } from "vue"

// Props
const platforms = ref([])
const totalRoms = ref(0)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('platforms', (p) => { platforms.value = p })
</script>

<template>
</template>