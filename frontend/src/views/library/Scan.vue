<script setup>
import { ref, inject } from "vue"
import { io } from "socket.io-client";
import { storePlatforms } from '@/stores/platforms.js'
import { storeScanning } from '@/stores/scanning.js'

// Props
const wsMsg = ref("")
const platforms = storePlatforms()
const platformsToScan = ref([])
const scanning = storeScanning()
const completeRescan = ref(false)

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.set(true);
    wsMsg.value = 'Scanning...'
    const socket = io({ path: '/ws/socket.io/', transports: ['websocket', 'polling'] })
    socket.on("connect", () => {console.log("ws connected")})
    socket.on('disconnect', () => {console.log('ws disconnected');});
    socket.on("scanning", (params) => {wsMsg.value = 'Scanning > '+params['platform']+' - '+params['rom']})
    socket.on("done", (msg) => { 
        scanning.set(false);
        emitter.emit('snackbarScan', {'msg': "Scan completed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        wsMsg.value = msg
    })
    socket.emit("scan", JSON.stringify(platformsToScan.value.map(p => p.fs_slug)), completeRescan.value)
}
</script>

<template>

    <div class="ma-5">
        <v-row no-gutters>
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

        <v-row class="mb-4" no-gutters>
            <v-checkbox
                v-model="completeRescan"
                label="Complete Rescan"
                prepend-icon="mdi-cached"
                hint="Rescan every rom, including already scanned roms"
                persistent-hint/>
        </v-row>

        <v-row no-gutters>
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

        <div class="ma-5"><span class="text-body-1">{{ wsMsg }}</span></div>
    </div>

</template>