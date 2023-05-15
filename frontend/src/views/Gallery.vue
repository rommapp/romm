<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { onBeforeRouteUpdate, useRoute } from 'vue-router'
import { views } from '@/utils/utils.js'
import { storeFilter } from '@/stores/filter.js'
import { storeGalleryView } from '@/stores/galleryView.js'
import { normalizeString } from '@/utils/utils.js'
import FilterBar from '@/components/GameGallery/FilterBar.vue'
import GalleryViewBtn from '@/components/GameGallery/GalleryViewBtn.vue'
import GameCard from '@/components/GameGallery/Card/Base.vue'
import GameListHeader from '@/components/GameGallery/ListItem/Header.vue'
import GameListItem from '@/components/GameGallery/ListItem/Item.vue'


// Props
const roms = ref([])
const gettingRoms = ref(false)
const filter = storeFilter()
const romsFiltered = ref([])
const galleryView = storeGalleryView()
const route = useRoute()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('filter', () => { filterRoms() })

// Functions
function filterRoms() {
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.file_name).includes(filter.value)
    })
}

async function fetchRoms(platform) {
    gettingRoms.value = true
    await axios.get('/api/platforms/'+platform+'/roms').then((response) => {
        roms.value = response.data.data
        filterRoms()
    }).catch((error) => {console.log(error)})
    gettingRoms.value = false
}

onMounted(async () => { fetchRoms(route.params.platform)})
onBeforeRouteUpdate(async (to, _) => { fetchRoms(to.params.platform) })
</script>

<template>

    <v-app-bar class="gallery-app-bar" elevation="0" density="compact">
        <filter-bar/>
        <gallery-view-btn/>
    </v-app-bar>

    <v-row v-show="!gettingRoms && galleryView.value != 2 && roms.length>0" class="pa-1" no-gutters>
        <v-col v-for="rom in romsFiltered" class="pa-1"
            :key="rom.file_name"
            :cols="views[galleryView.value]['size-cols']"
            :xs="views[galleryView.value]['size-xs']"
            :sm="views[galleryView.value]['size-sm']"
            :md="views[galleryView.value]['size-md']"
            :lg="views[galleryView.value]['size-lg']">
            <game-card :rom="rom"/>
        </v-col>
    </v-row>

    <v-row v-show="!gettingRoms && galleryView.value == 2 && roms.length>0" no-gutters>
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
    
    <v-row v-if="!gettingRoms && roms.length==0" no-gutters>
        <div class="text-h6 mt-16 mx-auto">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
    </v-row>

    <v-row v-if="gettingRoms" no-gutters>
        <v-progress-circular class="mt-16 mx-auto" color="rommAccent1" :width="3" :size="70" indeterminate/>
    </v-row>

</template>
<style scoped>
.gallery-app-bar {
    z-index: 999 !important;
}
</style>
