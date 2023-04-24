<script setup>
import { ref } from 'vue'
import { storePlatforms } from '@/stores/platforms'
import AppBar from '@/components/AppBar/Base.vue'
import { useDisplay } from "vuetify"


// Props
const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((accumulator, p) => { return accumulator + p.n_roms }, 0))
const { mdAndDown } = useDisplay()
</script>

<template>

    <app-bar v-if="mdAndDown"/>

    <span>Total games: {{ totalGames }}</span>

</template>

<style scoped>
</style>