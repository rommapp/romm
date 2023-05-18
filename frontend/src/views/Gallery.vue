<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { onBeforeRouteUpdate, useRoute } from 'vue-router'
import { io } from "socket.io-client";
import { views } from '@/utils/utils.js'
import { storeFilter } from '@/stores/filter.js'
import { storeGalleryView } from '@/stores/galleryView.js'
import { normalizeString } from '@/utils/utils.js'
import FilterBar from '@/components/GameGallery/FilterBar.vue'
import GalleryViewBtn from '@/components/GameGallery/GalleryViewBtn.vue'
import GameCard from '@/components/GameGallery/Card/Base.vue'
import GameListHeader from '@/components/GameGallery/ListItem/Header.vue'
import GameListItem from '@/components/GameGallery/ListItem/Item.vue'
import { storeScanning } from '@/stores/scanning.js'


// Props
const roms = ref([])
const gettingRoms = ref(false)
const filter = storeFilter()
const galleryView = storeGalleryView()
const route = useRoute()
const romsFiltered = ref([])
// const sections = ['roms', 'firmwares']
// const firmwares = ["firmware_base", "firmware_bios"]
const currentSection = ref('roms')
const scanning = storeScanning()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('filter', () => { filterRoms() })


async function scan() {
    scanning.set(true);
    emitter.emit('snackbarScan', {'msg': `Scanning ${route.params.platform}...`, 'icon': 'mdi-check-bold', 'color': 'green'})
    const socket = io({ path: '/ws/socket.io/', transports: ['websocket', 'polling'] })    
    socket.on("done", () => {
        scanning.set(false)
        emitter.emit('refreshGallery')
        emitter.emit('snackbarScan', {'msg': "Scan completed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        socket.close()
    })
    socket.on("done_ko", (msg) => {
        scanning.set(false)
        emitter.emit('snackbarScan', {'msg': `Scan couldn't be completed. Something went wrong: ${msg}`, 'icon': 'mdi-close-circle', 'color': 'red'})
        socket.close()
    })
    socket.emit("scan", JSON.stringify([route.params.platform]), false)
}


function filterRoms() {
    romsFiltered.value = roms.value.filter(rom => {
        return normalizeString(rom.file_name).includes(filter.value)
    })
}

async function fetchRoms(platform) {
    gettingRoms.value = true
    await axios.get(`/api/platforms/${platform}/roms`).then((response) => {
        roms.value = response.data.data
        filterRoms()
    }).catch((error) => {console.log(error)})
    gettingRoms.value = false
}

onMounted(async () => { fetchRoms(route.params.platform)})
onBeforeRouteUpdate(async (to, _) => { fetchRoms(to.params.platform) })
</script>

<template>
    
    <v-toolbar class="gallery-app-bar bg-primary" elevation="0" density="compact">
        <filter-bar/>
        <gallery-view-btn/>
        <v-btn @click="scan" rounded="0" variant="text" class="mr-0" icon="mdi-magnify-scan"/>
    </v-toolbar>

    <!-- <v-toolbar class="bg-primary" elevation="0" density="compact">
        <v-select item-title="name" :items="sections" v-model="currentSection" hide-details/>
        <v-btn @click="scan" rounded="0" variant="text" class="mr-0" icon="mdi-magnify-scan"/>
    </v-toolbar> -->

    <v-row v-show="currentSection == 'roms'" no-gutters class="test">

        <template v-if="!gettingRoms">

            <template v-if="roms.length>0">

                <v-row v-show="galleryView.value != 2" class="pa-1" no-gutters>
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

                <v-row v-show="galleryView.value == 2" class="pa-1" no-gutters>
                    <v-col class="pa-1"
                        :cols="views[galleryView.value]['size-cols']"
                        :xs="views[galleryView.value]['size-xs']"
                        :sm="views[galleryView.value]['size-sm']"
                        :md="views[galleryView.value]['size-md']"
                        :lg="views[galleryView.value]['size-lg']">
                        <v-table class="bg-secondary">
                            <game-list-header />
                            <v-divider class="border-opacity-100 mb-4 ml-2 mr-2" color="rommAccent1" :thickness="1"/>
                            <tbody>
                                <game-list-item v-for="rom in romsFiltered" :key="rom.file_name" :rom="rom"/>
                            </tbody>
                        </v-table>
                    </v-col>
                </v-row>

            </template>

            <v-row v-if="roms.length==0" no-gutters>
                <div class="text-h6 mt-16 mx-auto">Feels cold here... <v-icon>mdi-emoticon-sad</v-icon></div>
            </v-row>

        </template>


        <template v-else="gettingRoms">
            <v-row no-gutters>
                <v-progress-circular class="mx-auto" color="rommAccent1" :width="3" :size="70" indeterminate/>
            </v-row>
        </template>

    </v-row>
    
    <!-- <v-row v-show="currentSection == 'firmwares'" no-gutters>
        <v-col v-for="firmware in firmwares" class="pa-1"
            :key="firmware"
            :cols="views[galleryView.value]['size-cols']"
            :xs="views[galleryView.value]['size-xs']"
            :sm="views[galleryView.value]['size-sm']"
            :md="views[galleryView.value]['size-md']"
            :lg="views[galleryView.value]['size-lg']">
            <v-card>
                <v-card-text>
                    <span>{{ firmware }}</span>
                </v-card-text>
            </v-card>
        </v-col>
    </v-row> -->

</template>

<style scoped>
.gallery-app-bar {
    z-index: 999 !important;
}
</style>
