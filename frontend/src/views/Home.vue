<script setup>
import { ref } from 'vue'
import { storePlatforms } from '@/stores/platforms'

// Props
const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((accumulator, p) => { return accumulator + p.n_roms }, 0))
</script>

<template>

<span>Total games: {{ totalGames }}</span>

</template>

<style scoped>
</style>