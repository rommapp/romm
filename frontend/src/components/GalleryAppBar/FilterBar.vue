<script setup>
import { inject, ref, onMounted } from 'vue'
import { storeGalleryFilter } from '@/stores/galleryFilter.js'

// Props
const galleryFilter = storeGalleryFilter()
const filterValue = ref('')

// Event listeners bus
const emitter = inject('emitter')

onMounted(() => { filterValue.value = galleryFilter.value })
</script>

<template>
    <v-text-field @click:clear="galleryFilter.set(''); emitter.emit('filter')"
        @keyup="galleryFilter.set(filterValue); emitter.emit('filter')" v-model="filterValue"
        prepend-inner-icon="mdi-magnify" label="search" hide-details clearable />
</template>
