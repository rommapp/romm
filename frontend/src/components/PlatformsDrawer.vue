<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { useRouter } from 'vue-router'
import { useDisplay } from "vuetify"

// Props
const selectedPlatform = ref(JSON.parse(localStorage.getItem('selectedPlatform')) || "")
const platforms = ref([])
const platformsDrawer = ref(null)
const rail = (localStorage.getItem('rail') == 'true') ? ref(true) : ref(false)
const { mobile } = useDisplay()
const router = useRouter()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('platforms', (p) => { platforms.value = p })
emitter.on('platformsDrawer', () => { platformsDrawer.value = !platformsDrawer.value })

// Functions
async function getPlatforms() {
    // Get the list of the platforms for the navigation drawer
    axios.get('/api/platforms').then((response) => {
        platforms.value = response.data.data
        emitter.emit('platforms', platforms.value)
    }).catch((error) => {console.log(error)})
}

async function selectPlatform(platform){    
    // Select the current platform
    if(mobile.value){platformsDrawer.value = false}
    await router.push(import.meta.env.BASE_URL)
    localStorage.setItem('selectedPlatform', JSON.stringify(platform))
    emitter.emit('selectedPlatform', platform)
    selectedPlatform.value = platform
}

function toggleRail(){
    // Toggle collapsed/expand platform navigation drawer
    rail.value = !rail.value
    localStorage.setItem('rail', rail.value)
}

getPlatforms()
emitter.emit('selectedPlatform', selectedPlatform.value)
</script>

<template>

    <v-navigation-drawer v-model="platformsDrawer" :rail="rail" width="300" rail-width="72">
        <v-list>
            <!-- Platforms drawer - Platforms list -->
            <v-list-item v-for="platform in platforms"
                :value="platform.slug"
                :key="platform"
                @:click="selectPlatform(platform)" class="pt-4 pb-4">
                <v-list class="text-subtitle-2">{{ rail ? '' : platform.name }}</v-list>
                <template v-slot:prepend>
                    <v-avatar :rounded="0"><v-img :src="'/assets/platforms/'+platform.slug+'.ico'"></v-img></v-avatar>
                </template>
                <template v-slot:append>
                    <v-chip class="ml-4" size="small">{{ platform.n_roms }}</v-chip>
                </template>
            </v-list-item>
        </v-list>
        <!-- Platforms drawer - Platforms list - rail toggle -->
        <template v-slot:append>
            <v-btn title="toggle rail platforms drawer" @click="toggleRail()" rounded="0" block>
                <v-icon v-if="rail">mdi-arrow-collapse-right</v-icon>
                <v-icon v-if="!rail">mdi-arrow-collapse-left</v-icon>
            </v-btn>
        </template>
    </v-navigation-drawer>

</template>

<style scoped>
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .v-list .v-avatar {
  --v-avatar-height: 40px;
}
</style>
