<script setup>
import { ref, inject } from "vue"
import { io } from "socket.io-client";
import { storePlatforms } from '@/stores/platforms.js'
import { storeScanning } from '@/stores/scanning.js'

// Props
const platforms = storePlatforms()
const platformsToScan = ref([])
const scanning = storeScanning()
const scanningPlatform = ref("")
const scannedPlatforms = ref([])
const completeRescan = ref(false)


// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.set(true);
    scannedPlatforms.value = []
    const socket = io({ path: '/ws/socket.io/', transports: ['websocket', 'polling'] })
    socket.on("scanning_platform", (platform) => { scannedPlatforms.value.push({'p_name': platform[0], 'p_slug': platform[1], 'r': []}); scanningPlatform.value = platform[1] })
    socket.on("scanning_rom", (r) => { scannedPlatforms.value.forEach(e => { if(e['p_slug'] == scanningPlatform.value){ e['r'].push(r) } }) })
    socket.on("done", () => {
        scanning.set(false)
        emitter.emit('refresPlatforms')
        emitter.emit('snackbarScan', {'msg': "Scan completed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        socket.close()
    })
    socket.on("done_ko", (msg) => {
        scanning.set(false)
        emitter.emit('snackbarScan', {'msg': `Scan couldn't be completed. Something went wrong: ${msg}`, 'icon': 'mdi-close-circle', 'color': 'red'})
        socket.close()
    })
    socket.emit("scan", JSON.stringify(platformsToScan.value.map(p => p.fs_slug)), completeRescan.value)
}
</script>

<template>

        <v-row class="pa-4" no-gutters>
            <v-select
                label="Platforms"
                item-title="name"
                v-model="platformsToScan"
                :items="platforms.value"
                variant="outlined"
                density="comfortable"
                multiple
                return-object
                clearable
                hide-details
                rounded="0"
                chips/>
        </v-row>

        <v-row class="pa-4" no-gutters>
            <v-checkbox
                v-model="completeRescan"
                label="Complete Rescan"
                prepend-icon="mdi-cached"
                hint="Rescan every rom, including already scanned roms"
                persistent-hint/>
        </v-row>

        <v-row class="pa-4" no-gutters>
            <v-btn
                @click="scan()"
                :disabled="scanning.value"
                prepend-icon="mdi-magnify-scan"
                rounded="0">
                <span v-if="!scanning.value">Scan</span>
                <v-progress-circular
                    v-show="scanning.value"
                    color="rommAccent1"
                    class="ml-3 mr-2"
                    :width="2"
                    :size="20"
                    indeterminate/>
            </v-btn>
        </v-row>

        <v-divider class="border-opacity-100 ma-4" color="rommAccent1" :thickness="1"/>

        <v-row no-gutters class="align-center pa-4" v-for="d in scannedPlatforms">
            <v-col>
                <v-avatar :rounded="0" size="40"><v-img :src="`/assets/platforms/${d['p_slug']}.ico`"></v-img></v-avatar>
                <span class="text-body-2 ml-5"> {{ d['p_name'] }}</span>
                <v-list-item v-for="r in d['r']" class="text-body-2" disabled> - {{ r }}</v-list-item>
            </v-col>
        </v-row>

</template>