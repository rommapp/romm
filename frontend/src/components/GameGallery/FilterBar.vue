<script setup>
import { storeFilter } from '@/stores/filter'
import { inject, ref, onMounted } from 'vue'

// Props
const filter = storeFilter()
const filterValue = ref('')

// Event listeners bus
const emitter = inject('emitter')

onMounted(() => { filterValue.value = filter.value })
</script>

<template>

    <v-text-field
        @click:clear="filter.set('');emitter.emit('filter')" 
        @keyup="filter.set(filterValue);emitter.emit('filter')" 
        v-model="filterValue"
        prepend-inner-icon="mdi-magnify"
        label="search"
        hide-details
        clearable/>

</template>
