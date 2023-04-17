<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { onBeforeRouteUpdate, useRoute } from 'vue-router'
import { normalizeString, views } from '@/utils/utils.js'
import GameCard from '@/components/GameGallery/Card/Base.vue'
import GameListHeader from '@/components/GameGallery/ListItem/Header.vue'
import GameListItem from '@/components/GameGallery/ListItem/Item.vue'
import NoRoms from '@/components/GameGallery/NoRoms.vue'

// Props
const roms = ref([])
const gettingRoms = ref(false)
const noRoms = ref(false)
const romsFiltered = ref([])
const currentFilter = ref('')
const currentView = ref(JSON.parse(localStorage.getItem('currentView')) || 0)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('filter', (filter) => { setFilter(filter) })
emitter.on('currentView', (view) => { currentView.value = view })

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

const route = useRoute()

onMounted(async () => {
    getRoms(route.params.platform)
})

onBeforeRouteUpdate(async (to, from) => {
    getRoms(to.params.platform)
})
</script>

<template>

    <v-row v-show="currentView != 2">
        <v-col v-for="rom in romsFiltered"
            :key="rom.file_name"
            :cols="views[currentView]['size-cols']"
            :xs="views[currentView]['size-xs']"
            :sm="views[currentView]['size-sm']"
            :md="views[currentView]['size-md']"
            :lg="views[currentView]['size-lg']"
            class="pa-1">
            <game-card :rom="rom"/>
        </v-col>
    </v-row>

    <v-list v-show="currentView == 2" class="bg-secondary">
        <game-list-header/>
        <v-divider class="border-opacity-100 ml-3 mb-4 mr-3" color="rommAccent1" :thickness="1"/>
        <game-list-item v-for="rom in romsFiltered" :key="rom.file_name" :rom="rom"/>
    </v-list>
    
    <no-roms :noRoms="noRoms"/>

    <v-dialog v-model="gettingRoms" scroll-strategy="none" width="auto" :scrim="false" persistent>
        <v-progress-circular color="rommAccent1" :width="3" :size="70" indeterminate/>
    </v-dialog>

</template>

<style scoped>
.rom{
    transition: opacity .4s ease-in-out;
}
.rom.on-hover {
    opacity: 1;
}
.rom:not(.on-hover) {
    opacity: 0.85;
}
.rom{
    cursor: pointer;
}
</style>