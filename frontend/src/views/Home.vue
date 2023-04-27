<script setup>
import { ref } from 'vue'
import { useDisplay } from "vuetify"
import { storePlatforms } from '@/stores/platforms.js'

// Props
const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((count, p) => { return count + p.n_roms }, 0))
const { lgAndUp } = useDisplay()
</script>

<template>

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
