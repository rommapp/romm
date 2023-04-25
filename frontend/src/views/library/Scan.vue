<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { useDisplay } from "vuetify"
import { storePlatforms } from '@/stores/platforms.js'
import { storeScanning } from '@/stores/scanning.js'
import AppBar from '@/components/AppBar/Base.vue'

// Props
const platforms = storePlatforms()
const platformsToScan = ref([])
const scanning = storeScanning()
const fullScan = ref(false)
const { mdAndDown } = useDisplay()

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.set(true)
    const _platforms = []
    platformsToScan.value.forEach(p => { _platforms.push(p.fs_slug) })
    await axios.get('/api/scan?platforms='+JSON.stringify(_platforms)+'&full_scan='+fullScan.value).then((response) => {
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

    <app-bar v-if="mdAndDown"/>

    <v-select
        label="Platforms"
        item-title="name"
        v-model="platformsToScan"
        :items="platforms.value"
        density="comfortable"
        variant="outlined"
        multiple
        return-object
        clearable
        hide-details
        chips/>

    <v-checkbox
        v-model="fullScan"
        label="Complete Rescan"
        prepend-icon="mdi-cached"
        hint="Rescan every rom, including already scanned roms"
        persistent-hint/>

    <v-btn
        title="scan"
        @click="scan()"
        :disabled="scanning.value"
        prepend-icon="mdi-magnify-scan"
        rounded="0"
        class="mt-7"
        inset>
        <p v-if="!scanning.value">Scan</p>
        <v-progress-circular
            v-show="scanning.value"
            color="rommAccent1"
            class="ml-3 mr-2"
            :width="2"
            :size="20"
            indeterminate/>
    </v-btn>

</template>