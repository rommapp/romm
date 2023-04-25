<script setup>
import { ref } from 'vue'
import { storePlatforms } from '@/stores/platforms.js'
import AppBar from '@/components/AppBar/Base.vue'
import { useDisplay } from "vuetify"


// Props
const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((accumulator, p) => { return accumulator + p.n_roms }, 0))
const { mdAndDown, lgAndUp } = useDisplay()
</script>

<template>

    <app-bar v-if="mdAndDown"/>

    <v-card class="mx-auto mt-10" max-width="1000" variant="text">

        <v-img
            :height="lgAndUp ? 220 : 95"
            src="/assets/romm_complete.svg"
            cover/>

        <v-card-text class="d-flex justify-center">
            <span class="text-overline">Total games: {{ totalGames }}</span>
        </v-card-text>
    </v-card>

</template>

<style scoped>
</style>