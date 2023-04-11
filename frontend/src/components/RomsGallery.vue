<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const roms = ref([])
const gettingRoms = ref(false)
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
    gettingRoms.value = true
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        console.log("Roms loaded!")
        console.log(response.data.data)
        roms.value = response.data.data
        setFilter(currentFilter.value)
    }).catch((error) => {console.log(error)})
    emitter.emit('gettingRoms', false)
    gettingRoms.value = false
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
        return normalizeString(rom.file_name).includes(currentFilter.value)
    })
}

onMounted(() => { if(localStorage.getItem('currentPlatform')){ getRoms(JSON.parse(localStorage.getItem('currentPlatform')).slug) } })
</script>

<template>

    <v-row>
        <v-col v-for="rom in romsFiltered" cols="6" xs="6" sm="3" md="3" lg="2">
            <v-hover v-slot="{isHovering, props}">
                <v-card v-bind="props" :class="{'on-hover': isHovering}" :elevation="isHovering ? 20 : 3">
                    <v-hover v-slot="{ isHovering, props }" open-delay="800">
                        <v-img @click="selectRom(rom)" v-bind="props" :src="'/assets'+rom.path_cover_l+'?reload='+forceImgReload" :lazy-src="'/assets'+rom.path_cover_s+'?reload='+forceImgReload" class="cover" cover>
                            <template v-slot:placeholder>
                                <div class="d-flex align-center justify-center fill-height">
                                    <v-progress-circular indeterminate/>
                                </div>
                            </template>
                            <v-expand-transition>
                                <div v-if="isHovering || !rom.has_cover" class="rom-title d-flex transition-fast-in-fast-out bg-secondary text-caption-1">
                                    <v-list-item>{{ rom.file_name }}</v-list-item>
                                </div>
                            </v-expand-transition>
                            <div>
                                <v-chip v-show="rom.region" class="ml-1 mr-1 bg-primary" size="x-small">{{ rom.region }}</v-chip>
                                <v-chip v-show="rom.revision" class="mr-1 bg-primary" size="x-small">{{ rom.revision }}</v-chip>
                            </div>
                        </v-img>
                        <v-card-text>
                            <v-row>
                                <v-col class="pa-0">
                                    <v-btn @click="downloadRom(rom, emitter)" icon="mdi-download" size="small" variant="text"/>
                                    <v-btn @click="downloadSave(rom, emitter)" icon="mdi-content-save-all" size="small" variant="text" :disabled="!saveFiles"/>
                                </v-col>
                                <v-btn @click="" icon="mdi-dots-vertical" size="small" variant="text" :disabled="!saveFiles"/>
                            </v-row>
                        </v-card-text>
                    </v-hover>
                </v-card>
            </v-hover>
        </v-col>
    </v-row>
    
    <v-row v-if="noRoms" class="d-flex justify-center align-center mt-16">
        <div class="text-h6">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>

    <v-dialog v-model="gettingRoms" scroll-strategy="none" width="auto" :scrim="false" persistent>
        <v-progress-circular :width="3" :size="70" indeterminate/>
    </v-dialog>

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
    opacity: 0.85;
}
.cover{
    cursor: pointer;
}
</style>