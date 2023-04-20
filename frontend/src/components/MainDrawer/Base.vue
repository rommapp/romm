<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import RailBtn from '@/components/MainDrawer/RailBtn.vue'
import Platform from '@/components/MainDrawer/Platform.vue'

// Props
const platforms = ref([])
const platformsDrawer = ref(null)
const open = ref(['Platforms'])
const rail = (localStorage.getItem('rail') == 'true') ? ref(true) : ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('platforms', (p) => { platforms.value = p })
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
</script>

<template>

    <v-navigation-drawer v-model="platformsDrawer" :rail="rail" width="300" rail-width="145">

        <v-list v-model:opened="open">
            <router-link to="/" class="hidden-md-and-up">
                <v-row class="justify-center">
                    <v-img v-show="!rail" src="/assets/romm_complete.svg" class="home-btn justify-center"/>
                    <v-img v-show="rail" src="/assets/romm.svg" class="home-btn justify-center"/>
                </v-row>
            </router-link>

            <v-divider class="border-opacity-25 hidden-md-and-up"/>
            
            <v-list-group value="Platforms">
                <template v-slot:activator="{ props }">
                    <v-list-item
                        v-bind="props">
                        <p class="text-body-1 text-truncate">{{ rail ? '' : 'Platforms' }}</p>
                        <template v-slot:prepend>
                            <v-avatar :rounded="0" size="40"><v-icon>mdi-controller</v-icon></v-avatar>
                        </template>
                    </v-list-item>
                </template>
                <platform class="drawer-item" v-for="platform in platforms" :platform="platform" :rail="rail" :key="platform.slug"/>
            </v-list-group>

            <v-list-group value="Library">
                <template v-slot:activator="{ props }">
                    <v-list-item
                        v-bind="props">
                        <p class="text-body-1 text-truncate">{{ rail ? '' : 'Library' }}</p>
                        <template v-slot:prepend>
                            <v-avatar :rounded="0" size="40"><v-icon>mdi-animation-outline</v-icon></v-avatar>
                        </template>
                    </v-list-item>
                </template>
                <v-list-item class="drawer-item" disabled>
                    <p class="text-body-2 text-truncate">{{ rail ? '' : 'Upload roms' }}</p>
                    <template v-slot:prepend>
                        <v-avatar :rounded="0" size="40"><v-icon>mdi-upload</v-icon></v-avatar>
                    </template>
                </v-list-item>
                <v-list-item class="drawer-item" disabled>
                    <p class="text-body-2 text-truncate">{{ rail ? '' : 'Upload saves' }}</p>
                    <template v-slot:prepend>
                        <v-avatar :rounded="0" size="40"><v-icon>mdi-content-save-all</v-icon></v-avatar>
                    </template>
                </v-list-item>
            </v-list-group>

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
.drawer-item {
    padding-inline-start: 30px !important;
}
</style>