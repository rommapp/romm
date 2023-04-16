<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { useRouter } from 'vue-router'
import RailBtn from '@/components/PlatformsDrawer/RailBtn.vue'
import Platform from '@/components/PlatformsDrawer/Platform.vue'

// Props
const selectedPlatform = ref(JSON.parse(localStorage.getItem('selectedPlatform')) || "")
const platforms = ref([])
const platformsDrawer = ref(null)
const rail = (localStorage.getItem('rail') == 'true') ? ref(true) : ref(false)
const router = useRouter()

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

async function goHome(){
    await router.push(import.meta.env.BASE_URL)
}

getPlatforms()
emitter.emit('selectedPlatform', selectedPlatform.value)
</script>

<template>

    <v-navigation-drawer v-model="platformsDrawer" :rail="rail" width="300" rail-width="75">

        <v-list>
            <v-row @click="goHome()" class="justify-center hidden-md-and-up">
                <v-img v-show="!rail" src="/assets/romm_complete.svg" class="home-btn justify-center"/>
                <v-img v-show="rail" src="/assets/romm.svg" class="home-btn justify-center"/>
            </v-row>
            <v-divider class="border-opacity-25 hidden-md-and-up"/>

            <platform v-for="platform in platforms" :platform="platform" :rail="rail" :key="platform.slug"/>
        </v-list>
        
        <template v-slot:append>
            <v-divider class="border-opacity-25" :thickness="1"/>
            <rail-btn :rail="rail"/>
        </template>

    </v-navigation-drawer>

</template>

<style scoped>
.home-btn{
    width: 100px;
    height: 100px;
    cursor: pointer;
}
</style>