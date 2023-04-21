<script setup>
import { ref } from 'vue'
import { storePlatforms } from '@/stores/platforms'

// Props
const platforms = storePlatforms()
console.log(platforms.value)
const totalGames = ref(platforms.value.reduce((accumulator, p) => {
    return accumulator + p.n_roms;
}, 0))
</script>

<template>

    <v-row>
        <v-col>
            <span>Total games: {{ totalGames }}</span>
        </v-col>
    </v-row>

</template>