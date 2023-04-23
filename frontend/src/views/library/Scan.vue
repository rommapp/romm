<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { storePlatforms } from '@/stores/platforms'


// Props
const platforms = storePlatforms()
const platformsToScan = ref([])
const scanning = ref(false)
const fullScan = ref(false)

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function scan() {
    scanning.value = true
    emitter.emit('scanning', true)
    const platforms = []
    platformsToScan.value.forEach(p => {platforms.push(p.slug)})
    await axios.get('/api/scan?platforms='+JSON.stringify(platforms)+'&full_scan='+fullScan.value).then((response) => {
        emitter.emit('snackbarScan', {'msg': response.data.msg, 'icon': 'mdi-check-bold', 'color': 'green'})
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    scanning.value = false
    emitter.emit('scanning', false)
    emitter.emit('refresh')
}
</script>

<template>
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
        class="text-white"
        hide-details
        chips/>

    <v-checkbox
        v-model="fullScan"
        label="Complete scan"
        prepend-icon="mdi-cached"
        class="text-white"
        hide-details/>

    <div class="ml-10 text-caption font-weight-light font-italic">
        <span>Re-scan every rom even if it is already scanned</span>
    </div>

    <v-btn
        title="scan"
        @click="scan()"
        :disabled="scanning"
        prepend-icon="mdi-magnify-scan"
        rounded="0"
        class="mt-5"
        inset>
        <p v-if="!scanning">Scan</p>
        <v-progress-circular
            v-show="scanning"
            color="rommAccent1"
            :width="2"
            :size="20"
            indeterminate/>
    </v-btn>
            

</template>