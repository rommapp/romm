<script setup>
import axios from 'axios'
import { ref } from "vue";


const currentRom = ref("")


function getRomDetails(rom){
    currentRom.value = rom.name
}

defineExpose({ getRomDetails })
</script>

<template>
    <v-row>
        <h3>{{ currentRom }}</h3>
    </v-row>
</template>

<style scoped>
</style>