<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { onBeforeRouteUpdate, useRoute } from 'vue-router'
import { useDisplay } from "vuetify"
import { views } from '@/utils/utils.js'
import { storeFilter } from '@/stores/filter.js'
import { storeGalleryView } from '@/stores/galleryView.js'
import { storeContextBar } from '@/stores/contextBar.js'
import { normalizeString } from '@/utils/utils.js'
import AppBar from '@/components/AppBar/Base.vue'
import GalleryViewBtn from '@/components/AppBar/Gallery/GalleryViewBtn.vue'
import FilterBar from '@/components/AppBar/Gallery/FilterBar.vue'
import GameCard from '@/components/GameGallery/Card/Base.vue'
import GameListHeader from '@/components/GameGallery/ListItem/Header.vue'
import GameListItem from '@/components/GameGallery/ListItem/Item.vue'

const route = useRoute()

// Props
const gettingRoms = ref(false)
const roms = ref([])
const filter = storeFilter()
const romsFiltered = ref([])
const galleryView = storeGalleryView()
const contextBar = storeContextBar()
const { mdAndDown, lgAndUp } = useDisplay()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('filter', () => { filterRoms() })

// Functions
function filterRoms() {
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.file_name).includes(filter.value)
    })
}

async function getRoms(platform) {
    gettingRoms.value = true
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        roms.value = response.data.data
        filterRoms()
    }).catch((error) => {console.log(error)})
    gettingRoms.value = false
}

onMounted(async () => { getRoms(route.params.platform)})
onBeforeRouteUpdate(async (to, _) => { getRoms(to.params.platform) })
</script>

<template>

    <app-bar v-if="mdAndDown"/>

    <v-expand-transition>
        <v-row v-if="contextBar.value || lgAndUp" class="d-flex transition-fast-in-fast-out justify-center align-center">
            <filter-bar class="pa-1"/>
            <gallery-view-btn class="bg-secondary mr-1"/>
        </v-row>
    </v-expand-transition>


    <v-row v-if="!gettingRoms && galleryView.value != 2 && roms.length>0">
        <v-col v-for="rom in romsFiltered"
            :key="rom.file_name"
            :cols="views[galleryView.value]['size-cols']"
            :xs="views[galleryView.value]['size-xs']"
            :sm="views[galleryView.value]['size-sm']"
            :md="views[galleryView.value]['size-md']"
            :lg="views[galleryView.value]['size-lg']"
            class="pa-1">
            <game-card :rom="rom"/>
        </v-col>
    </v-row>

    <v-row v-if="!gettingRoms && galleryView.value == 2 && roms.length>0" class="justify-center">
        <v-col class="pa-0">
            <v-table class="bg-secondary">
                <game-list-header />
                <v-divider class="border-opacity-100 mb-4 ml-2 mr-2" color="rommAccent1" :thickness="1"/>
                <tbody>
                    <game-list-item v-for="rom in romsFiltered" :key="rom.file_name" :rom="rom"/>
                </tbody>
            </v-table>
        </v-col>
    </v-row>
    
    <v-row v-if="!gettingRoms && roms.length==0">
        <div class="text-h6 mt-16 mx-auto">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>

    <v-row v-if="gettingRoms">
        <v-progress-circular class="mt-16 mx-auto" color="rommAccent1" :width="3" :size="70" indeterminate/>
    </v-row>

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