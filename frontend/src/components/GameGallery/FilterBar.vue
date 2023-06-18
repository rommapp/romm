<script setup>
import { storeFilter } from '@/stores/filter'
import { inject, ref, onMounted } from 'vue'
import { debounce } from 'lodash';

// Props
const filter = storeFilter()
const filterValue = ref('')

// Event listeners bus
const emitter = inject('emitter')

onMounted(() => { filterValue.value = filter.value })

const filterRoms = debounce(() => {
    filter.set(filterValue.value);
    emitter.emit('filter');
}, 500);
</script>

<template>
    <v-text-field @click:clear="filter.set(''); emitter.emit('filter')" @keyup="filterRoms" v-model="filterValue"
        prepend-inner-icon="mdi-magnify" label="search" hide-details clearable />
</template>
