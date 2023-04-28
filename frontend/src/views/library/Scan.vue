<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { storePlatforms } from '@/stores/platforms.js'
import { storeScanning } from '@/stores/scanning.js'

// Props
const platforms = storePlatforms()
const platformsToScan = ref([])
const scanning = storeScanning()
const completeRescan = ref(false)

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.set(true)
    await axios.get('/api/scan?platforms='+JSON.stringify(platformsToScan.value.map(p => p.fs_slug))+'&complete_rescan='+completeRescan.value, { timeout: 3600000 }).then((response) => {
        emitter.emit('snackbarScan', {'msg': response.data.msg, 'icon': 'mdi-check-bold', 'color': 'green'})
        emitter.emit('refresh')
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    scanning.set(false)
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
    </div>

</template>