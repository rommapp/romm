<script setup>
import axios from 'axios'
import { ref, inject , onMounted } from "vue"
import { useRouter } from 'vue-router'
import { saveAs } from 'file-saver'

// Props
const roms = ref([])
const romsFiltered = ref([])
const currentFilter = ref('')
const noRoms = ref(false)
var currentPlatformSlug = localStorage.getItem('currentPlatformSlug') || ""
const router = useRouter()
const forceImgReload = Date.now()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentPlatform', (platform) => { getRoms(platform) })
emitter.on('romsFilter', (filter) => { setFilter(filter) })

// Functions
function normalizeString(s) {
    return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,"")
}

function setFilter(filter) {
    currentFilter.value = normalizeString(filter)
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.name).includes(currentFilter.value)
    })
}

async function getRoms(platform) {
    currentPlatformSlug = platform
    console.log("Getting roms...")
    emitter.emit('gettingRoms', true)
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        console.log("Roms loaded!")
        console.log(response.data.data)
        roms.value = response.data.data
        setFilter(currentFilter.value)
        if (roms.value.length == 0){ noRoms.value = true }else{ noRoms.value = false }
    }).catch((error) => {console.log(error)})
    emitter.emit('gettingRoms', false)
}
    
function downloadRom(filename) {
    console.log("Downloading "+filename)
    axios.get('/assets/emulation/'+currentPlatformSlug+'/roms/'+filename, { responseType: 'blob' }).then(response => {
        saveAs(new Blob([response.data], { type: 'application/file' }), filename)
    }).catch(console.error)
}

function downloadSave(name) {
    console.log("Downloading "+name+" save file")
}

async function selectRom(rom) {   
    console.log("Selected rom "+rom.name)
    localStorage.setItem('currentRom', JSON.stringify(rom))
    await router.push(import.meta.env.BASE_URL+'details')
    emitter.emit('currentRom', rom)
}

onMounted(() => { if(currentPlatformSlug){ getRoms(currentPlatformSlug) } })
</script>

<template>

    <v-row>
        <v-col v-for="rom in romsFiltered" cols="6" xs="6" sm="3" md="3" lg="2">
            <v-hover v-slot="{isHovering, props}">
                <v-card :elevation="isHovering ? 20 : 3" :class="{'on-hover': isHovering}" v-bind="props">
                    <v-img :src="rom.path_cover_l+'?reload='+forceImgReload" :lazy-src="rom.path_cover_s+'?reload='+forceImgReload" cover>
                        <v-tooltip activator="parent" location="top" open-delay="500">{{ rom.filename }}</v-tooltip>
                        <template v-slot:placeholder>
                            <div class="d-flex align-center justify-center fill-height">
                                <v-progress-circular color="grey-lighten-4" indeterminate />
                            </div>
                        </template>
                        <div v-if="!rom.has_cover" class="d-flex align-center text-body-1 pt-2 pr-5 pb-2 pl-5 bg-secondary rom-title" >{{ rom.filename }}</div>
                        <v-btn class="d-flex align-center justify-center fill-height" @click="selectRom(rom)" color="transparent" block />
                    </v-img>
                    <v-card-text>
                        <v-row>
                            <v-btn size="small" variant="flat" icon="mdi-download" @click="downloadRom(rom.filename)" />
                            <v-btn size="small" variant="flat" icon="mdi-content-save-all" @click=" downloadSave(rom.filename)"/>
                        </v-row>
                    </v-card-text>
                </v-card>
            </v-hover>
        </v-col>
    </v-row>
    <v-row v-if="noRoms" class="d-flex align-center justify-center fill-height">
        <div class="mt-16 pt-16 text-h6">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
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