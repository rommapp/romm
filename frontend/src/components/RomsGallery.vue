<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const roms = ref([])
const noRoms = ref(false)
const romsFiltered = ref([])
const currentFilter = ref('')
const router = useRouter()
const forceImgReload = Date.now()
const saveFiles = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentPlatform', (platform) => { getRoms(platform.slug) })
emitter.on('romsFilter', (filter) => { setFilter(filter) })

// Functions
async function getRoms(platform) {
    noRoms.value = false
    console.log("Getting roms...")
    emitter.emit('gettingRoms', true)
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        console.log("Roms loaded!")
        console.log(response.data.data)
        roms.value = response.data.data
        setFilter(currentFilter.value)
    }).catch((error) => {console.log(error)})
    emitter.emit('gettingRoms', false)
    if(roms.value.length==0){noRoms.value = true}
}

async function selectRom(rom) {   
    console.log("Selected rom "+rom.name)
    localStorage.setItem('currentRom', JSON.stringify(rom))
    await router.push(import.meta.env.BASE_URL+'details')
    emitter.emit('currentRom', rom)
}

function normalizeString(s) {
    return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,"")
}

function setFilter(filter) {
    currentFilter.value = normalizeString(filter)
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.name).includes(currentFilter.value)
    })
}

onMounted(() => { if(localStorage.getItem('currentPlatform')){ getRoms(JSON.parse(localStorage.getItem('currentPlatform')).slug) } })
</script>

<template>

    <v-row>
        <v-col v-for="rom in romsFiltered" cols="6" xs="6" sm="3" md="3" lg="2">
            <v-hover v-slot="{isHovering, props}">
                <v-card v-bind="props" :class="{'on-hover': isHovering}" :elevation="isHovering ? 20 : 3">
                    <v-img :src="rom.path_cover_l+'?reload='+forceImgReload" :lazy-src="rom.path_cover_s+'?reload='+forceImgReload" cover>
                        <v-tooltip activator="parent" open-delay="500" location="top">{{ rom.filename }}</v-tooltip>
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height">
                                <v-progress-circular indeterminate/>
                            </div>
                        </template>
                        <div v-if="!rom.has_cover" class="rom-title d-flex align-center text-body-1 pt-2 pr-5 pb-2 pl-5 bg-secondary">{{ rom.filename }}</div>
                        <v-btn @click="selectRom(rom)" class="d-flex align-center justify-center fill-height" color="transparent" block/>
                    </v-img>
                    <v-card-text>
                        <v-row>
                            <v-btn @click="downloadRom(rom)" icon="mdi-download" size="small" variant="text"/>
                            <v-btn @click="downloadSave()" icon="mdi-content-save-all" size="small" variant="text" :disabled="!saveFiles"/>
                        </v-row>
                    </v-card-text>
                </v-card>
            </v-hover>
        </v-col>
    </v-row>
    <v-row v-if="noRoms" class="d-flex align-center justify-center fill-height">
        <div class="text-h6 mt-16 pt-16">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>

</template>

<style scoped>
.v-card .rom-title{
    transition: opacity .4s ease-in-out;
}
.rom-title.on-hover {
    opacity: 1;
}
.rom-title:not(.on-hover) {
    opacity: 0.85;
}
.v-card.on-hover {
    opacity: 1;
}
.v-card:not(.on-hover) {
    opacity: 0.95;
}
</style>