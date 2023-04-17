<script setup>
import axios from "axios"
import { ref, inject, toRaw } from "vue"

// Props
const platforms = ref([])
const platformsToScan = ref([])
const scanning = ref(false)
const fullScan = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('platforms', (p) => { platforms.value = p })

// Functions
async function scan() {
    scanning.value = true
    emitter.emit('scanning', true)
    const platforms = []
    toRaw(platformsToScan)._rawValue.forEach(p => {platforms.push(toRaw(p.slug))})
    await axios.get('/api/scan?platforms='+JSON.stringify(platforms)+'&full_scan='+fullScan.value).then((response) => {
        emitter.emit('snackbarScan', {'msg': 'Scan completed successfully!', 'icon': 'mdi-check-bold', 'color': 'green'})
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't complete scan. Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    scanning.value = false
    emitter.emit('scanning', false)
    emitter.emit('refresh')
}
</script>

<template>
    <v-list>
        <v-select
            label="Platforms"
            item-title="name"
            v-model="platformsToScan"
            :items="platforms"
            class="pl-5 pr-5 mt-2 mb-1"
            density="comfortable"
            variant="outlined"
            multiple
            return-object
            clearable
            hide-details
            chips/>

        <v-list-item class="pa-0">
            <v-row class="align-center">
                <v-col class="d-flex justify-center">
                    <v-btn
                        title="scan"
                        @click="scan()"
                        :disabled="scanning"
                        prepend-icon="mdi-magnify-scan"
                        class="ml-7"
                        rounded="0" 
                        inset>
                        <p v-if="!scanning">Scan</p>
                        <v-progress-circular
                            v-show="scanning"
                            class="ml-2"
                            color="rommAccent1"
                            :width="2"
                            :size="20"
                            indeterminate/>
                    </v-btn>
                </v-col>
                <v-col class="mr-4">
                    <v-checkbox
                        v-model="fullScan"
                        label="Full scan"
                        hide-details/>
                </v-col>
            </v-row>
        </v-list-item>

    </v-list>
</template>