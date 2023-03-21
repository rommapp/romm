<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { useRouter } from 'vue-router'
import { useTheme } from "vuetify";

// Props
const platforms = ref([])
const currentPlatformName = ref(localStorage.getItem('currentPlatformName') || "")
const currentPlatformSlug = ref(localStorage.getItem('currentPlatformSlug') || "")
const scanOverwrite = ref(false)
const scanning = ref(false)
const gettingRomsFlag = ref(false)
const drawer = ref(null)
const settings = ref(null)
const filter = ref('')
const rail = (localStorage.getItem('rail') == 'true') ? ref(true) : ref(false)
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'light') ? ref(false) : ref(true)
const router = useRouter()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('gettingRoms', (flag) => { gettingRomsFlag.value = flag })

// Functions
async function getPlatforms() {
    // Get the list of the platforms for the navigation drawer
    console.log("Getting platforms...")
    await axios.get('/api/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
        localStorage.setItem('platforms', JSON.stringify(response.data.data))
    }).catch((error) => {console.log(error)})
}

async function selectPlatform(platform){    
    // Select the current platform
    await router.push(import.meta.env.BASE_URL)
    localStorage.setItem('currentPlatformSlug', platform.slug)
    localStorage.setItem('currentPlatformName', platform.name)
    emitter.emit('currentPlatform', platform.slug)
    currentPlatformName.value = platform.name
    currentPlatformSlug.value = platform.slug
}

function toggleRail(){
    // Toggle collapsed/expand platform navigation drawer
    rail.value = !rail.value
    localStorage.setItem('rail', rail.value)
}

async function scan() {
    // Scan and then get the platforms again
    console.log("scanning...")
    scanning.value = true
    await axios.get('/api/scan?overwrite='+scanOverwrite.value).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        getPlatforms()
    }).catch((error) => {console.log(error)})
    scanning.value = false
}

function setFilter(filter) {
    // Sets the roms filter
    emitter.emit('romsFilter', filter)
}

function toggleTheme() {
    // Toggle dark/light theme
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}

getPlatforms()
</script>

<template>
    <!-- Platforms navigation drawer -->
    <v-navigation-drawer width="250" rail-width="72" v-model="drawer" :rail="rail">
        <v-list-item class="mt-3" fixed>
            <template v-slot:prepend>
                <v-avatar :rounded="0"><v-img src="/assets/romm.png"></v-img></v-avatar>
            </template>
            <v-list-item-title class="text-subtitle-2">Rom Manager</v-list-item-title>
        </v-list-item>

        <v-divider class="mt-3 mb-1"></v-divider>

        <v-list nav>
            <v-list-item v-for="platform in platforms"
                class="mt-3"
                :title="rail ? '' : platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="selectPlatform(platform)">
                <template v-slot:prepend>
                    <v-avatar :rounded="0"><v-img :src="'/assets/platforms/'+platform.slug+'.png'"></v-img></v-avatar>
                </template>
                <template v-slot:append>
                    <v-progress-circular v-show="gettingRomsFlag && currentPlatformName == platform.name" indeterminate color="primary" :width="2" :size="20" class="ml-2" />
                </template>
            </v-list-item>
        </v-list>

        <template v-slot:append>
            <v-btn block @click="toggleRail()" rounded="0">
                <v-icon v-if="rail">mdi-arrow-collapse-right</v-icon>
                <v-icon v-if="!rail">mdi-arrow-collapse-left</v-icon>
            </v-btn>
        </template>
    </v-navigation-drawer>

    <v-app-bar color="toolbar" class="elevation-0" >
        <v-app-bar-nav-icon @click="drawer = !drawer" class="hidden-lg-and-up" rounded="0"/>
        <v-toolbar-title class="align-center text-h6 ml-4 d-none d-sm-flex">
            <v-avatar class="mr-3" :rounded="0"><v-img :src="'/assets/platforms/'+currentPlatformSlug+'.png'"></v-img></v-avatar>
            {{ currentPlatformName }}
        </v-toolbar-title>
        <v-toolbar-title class="align-center text-h6 ml-4 d-sm-none">
            <v-avatar class="mr-3" :rounded="0"><v-img :src="'/assets/platforms/'+currentPlatformSlug+'.png'"></v-img></v-avatar>
        </v-toolbar-title>
        <v-text-field hide-details label="search" variant="outlined" density="compact" clearable prepend-inner-icon="mdi-magnify" v-model="filter" @keyup="setFilter(filter)" @click:clear="setFilter('')"/>
        <v-app-bar-nav-icon @click="settings = !settings" class="mr-2 ml-2" rounded="0"><v-icon>mdi-cog</v-icon></v-app-bar-nav-icon>
    </v-app-bar>

    <v-navigation-drawer width="190" v-model="settings" location="right" temporary>
        <v-list >
            <v-list-item class="d-flex align-center justify-center mb-2">
                <v-btn :disabled="scanning" color="secondary" prepend-icon="mdi-magnify-scan" @click="scan()" inset rounded="0">
                    <p v-if="!scanning">Scan</p>
                    <p v-if="scanning">Scanning</p>
                    <v-progress-circular v-show="scanning" indeterminate color="primary" :width="2" :size="20" class="ml-2" />
                </v-btn>
            </v-list-item>
            <v-divider ></v-divider>
            <v-list-item class="d-flex align-center justify-center">
                <v-switch prepend-icon="mdi-brightness-6" class="pr-2 pl-2" v-model="darkMode" @change="toggleTheme()" hide-details="true" inset/>
            </v-list-item>
        </v-list>
    </v-navigation-drawer>

</template>

<style scoped>
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .v-list .v-avatar {
  --v-avatar-height: 40px;
}
</style>