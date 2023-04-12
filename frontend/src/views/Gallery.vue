<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { normalizeString } from '@/utils/utils.js'
import GameCard from '@/components/GameCard/Base.vue'

// Props
const roms = ref([])
const gettingRoms = ref(false)
const noRoms = ref(false)
const romsFiltered = ref([])
const currentFilter = ref('')

// Event listeners bus
const emitter = inject('emitter')
emitter.on('selectedPlatform', (platform) => { getRoms(platform.slug) })
emitter.on('filter', (filter) => { setFilter(filter) })

// Functions
async function getRoms(platform) {
    noRoms.value = false
    emitter.emit('gettingRoms', true)
    gettingRoms.value = true
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        roms.value = response.data.data
        setFilter(currentFilter.value)
    }).catch((error) => {console.log(error)})
    emitter.emit('gettingRoms', false)
    gettingRoms.value = false
    if(roms.value.length==0){noRoms.value = true}
}

function setFilter(filter) {
    currentFilter.value = normalizeString(filter)
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.file_name).includes(currentFilter.value)
    })
}

onMounted(() => {
    if(localStorage.getItem('selectedPlatform')){
        getRoms(JSON.parse(localStorage.getItem('selectedPlatform')).slug)
    }
})
</script>

<template>

    <v-row>
        <v-col v-for="rom in romsFiltered" cols="6" xs="6" sm="3" md="3" lg="2">
            <game-card :rom="rom"/>
        </v-col>
    </v-row>
    
    <v-row v-if="noRoms" class="d-flex justify-center align-center mt-16">
        <div class="text-h6">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>

    <v-dialog v-model="gettingRoms" scroll-strategy="none" width="auto" :scrim="false" persistent>
        <v-progress-circular :width="3" :size="70" indeterminate/>
    </v-dialog>

</template>
