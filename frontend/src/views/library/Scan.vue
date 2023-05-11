<script setup>
import axios from "axios"
import { ref, inject } from "vue"
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
    scanning.set(true)
    const socket = new WebSocket('ws://localhost:5000/scan?platforms='+JSON.stringify(platformsToScan.value.map(p => p.fs_slug))+'&complete_rescan='+completeRescan.value)
    socket.onmessage = function(e){ wsMsg.value = e.data }
    socket.onclose = function(){ 
        scanning.set(false)
        emitter.emit('snackbarScan', {'msg': "Scan completed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        emitter.emit('refresh')
    }
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