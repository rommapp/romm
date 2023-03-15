<script setup>
import axios from 'axios'
import { ref, inject } from "vue";

// Props
const currentRom = ref("")

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (rom) => { getRomDetails(rom) })

// Functions
function getRomDetails(rom){
    currentRom.value = rom.name
}

</script>

<template>
    <v-row>
        <h3>{{ currentRom }}</h3>
    </v-row>
</template>