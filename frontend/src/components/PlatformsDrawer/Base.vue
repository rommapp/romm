<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import RailBtn from '@/components/PlatformsDrawer/RailBtn.vue'
import Platform from '@/components/PlatformsDrawer/Platform.vue'

// Props
const selectedPlatform = ref(JSON.parse(localStorage.getItem('selectedPlatform')) || "")
const platforms = ref([])
const platformsDrawer = ref(null)
const rail = (localStorage.getItem('rail') == 'true') ? ref(true) : ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('togglePlatforms', () => { platformsDrawer.value = !platformsDrawer.value })
emitter.on('togglePlatformsRail', () => { rail.value = !rail.value; localStorage.setItem('rail', rail.value)})

// Functions
async function getPlatforms() {
    axios.get('/api/platforms').then((response) => {
        platforms.value = response.data.data
        emitter.emit('platforms', platforms.value)
    }).catch((error) => {console.log(error)})
}

getPlatforms()
emitter.emit('selectedPlatform', selectedPlatform.value)
</script>

<template>

    <v-navigation-drawer v-model="platformsDrawer" :rail="rail" width="300" rail-width="75">

        <v-list>
            <platform v-for="platform in platforms" :platform="platform" :rail="rail"/>
        </v-list>
        
        <template v-slot:append>
            <rail-btn :rail="rail"/>
        </template>

    </v-navigation-drawer>

</template>
