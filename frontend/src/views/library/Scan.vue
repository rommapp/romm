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
const scannedRoms = ref([])
const completeRescan = ref(false)

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.set(true);
    const socket = io({ path: '/ws/socket.io/', transports: ['websocket', 'polling'] })
    socket.on("scanning_platform", (platform) => { scanningPlatform.value = platform })
    socket.on("scanning_rom", (rom) => { scannedRoms.value.push(rom) })
    socket.on("done", () => {
        scanning.set(false);
        // emitter.emit('refresh')
        emitter.emit('snackbarScan', {'msg': "Scan completed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        socket.close()
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

        <v-row class="mb-4" no-gutters>
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

        <v-row no-gutters class="align-center">
            <v-col cols="12" class="pa-2">
                <v-avatar :rounded="0" size="40"><v-img :src="'/assets/platforms/'+scanningPlatform+'.ico'"></v-img></v-avatar>
                <span class="text-overline ml-5"> {{ scanningPlatform }}</span>
            </v-col>
            <v-col cols="12">
                <v-list-item v-for="rom in scannedRoms" class="text-body-2" disabled> - {{ rom }}</v-list-item>
                <!-- <v-list-item class="text-body-2" disabled>{{ scanningRom }}</v-list-item> -->
            </v-col>
        </v-row>
    </div>

</template>