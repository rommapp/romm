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
            v-if="lgAndUp"
            height="220"
            src="/assets/romm_complete.svg"
            cover/>

          <v-img
            v-if="mdAndDown"
            height="95"
            src="/assets/romm_complete.svg"
            cover/>

        <v-card-text class="d-flex justify-center">
            <span>Total games: {{ totalGames }}</span>
        </v-card-text>
    </v-card>

</template>

<style scoped>
</style>