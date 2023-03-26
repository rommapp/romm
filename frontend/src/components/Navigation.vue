<script setup>
import axios from "axios"
import { ref, inject, toRaw } from "vue"
import { useRouter } from 'vue-router'
import { useTheme } from "vuetify"

// Props
const platforms = ref([])
const currentPlatform = ref(JSON.parse(localStorage.getItem('currentPlatform')) || "")
const platformsToScan = ref([])
const scanning = ref(false)
const scanOverwrite = ref(false)
const gettingRomsFlag = ref(false)
const filter = ref('')
const drawer = ref(null)
const settings = ref(null)
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
    axios.get('/api/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    }).catch((error) => {console.log(error)})
}

function setFilter(filter) {
    // Sets the roms filter
    emitter.emit('romsFilter', filter)
}

async function selectPlatform(platform){    
    // Select the current platform
    await router.push(import.meta.env.BASE_URL)
    localStorage.setItem('currentPlatform', JSON.stringify(platform))
    emitter.emit('currentPlatform', platform)
    currentPlatform.value = platform
}

function toggleRail(){
    // Toggle collapsed/expand platform navigation drawer
    rail.value = !rail.value
    localStorage.setItem('rail', rail.value)
}

async function scan() {
    // Complete scan or by platform
    console.log("scanning...")
    scanning.value = true
    const platforms = []
    toRaw(platformsToScan)._rawValue.forEach(p => {platforms.push(toRaw(p.slug))})
    console.log(platforms)

    await axios.put('/api/scan?overwrite='+scanOverwrite.value,{
        platforms: platforms
    }).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        emitter.emit('snackbarScan', {'msg': 'Scan completed successfully!', 'icon': 'mdi-check-bold', 'color': 'green'})
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't complete scan. Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    scanning.value = false
    if (!platforms.length){emitter.emit('refresh')}else{emitter.emit('refreshRoms')}
}

function toggleTheme() {
    // Toggle dark/light theme
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}

function uploadRom() {
    console.log("uploading rom")
}

getPlatforms()
</script>

<template>
    <!-- Settings drawer -->
    <v-navigation-drawer v-model="settings" location="right" width="270" temporary floating>
        <!-- Settings drawer - title -->
        <v-list-item class="text-h5 d-flex align-center justify-center font-weight-bold bg-primary pt-4 pb-4 pl-7">
            Settings
            <v-btn title="close settings" @click="settings = !settings" class="ml-1" icon="mdi-close-box" rounded="0" variant="plain"/>
        </v-list-item>
        <v-divider class="border-opacity-100" :thickness="2"/>
        <v-list>
            <!-- Settings drawer - scan button -->
            <v-select label="Platforms" item-title="name" v-model="platformsToScan" :items="platforms" class="pl-5 pr-5 mt-2" density="comfortable" variant="outlined" multiple return-object clearable/>
            <v-list-item class="d-flex align-center justify-center mb-2 pt-0">
                <v-btn title="scan" @click="scan()" :disabled="scanning" prepend-icon="mdi-magnify-scan" color="secondary" rounded="0" inset>
                    <p v-if="!scanning">Scan</p>
                    <p v-if="scanning">Scanning</p>
                    <v-progress-circular v-show="scanning" class="ml-2" color="primary" :width="2" :size="20" indeterminate/>
                </v-btn>
            </v-list-item>
        </v-list>
        <!-- Settings drawer - theme toggle -->
        <template v-slot:append>
            <v-divider class="border-opacity-25"/>
            <v-list-item class="d-flex align-center justify-center">
                <v-switch @change="toggleTheme()" v-model="darkMode" class="pr-2 pl-2" hide-details="true" prepend-icon="mdi-theme-light-dark" inset/>
            </v-list-item>
        </template>
    </v-navigation-drawer>

    <!-- App bar -->
    <v-app-bar color="toolbar" class="elevation-3">
        <!-- App bar - RomM avatar -->
        <v-avatar class="hidden-md-and-down ml-4" :rounded="0"><v-img src="/assets/romm.png"></v-img></v-avatar>
        <!-- App bar - RomM title -->
        <v-list-item-title class="text-h6 hidden-md-and-down font-weight-black ml-5">ROM MANAGER</v-list-item-title>
        <!-- App bar - Platforms drawer toggle -->
        <v-app-bar-nav-icon title="toggle platforms drawer" @click="drawer = !drawer" class="hidden-lg-and-up ml-1" rounded="0"/>
        <!-- App bar - Platform title - mobile -->
        <v-avatar class="ml-3 mr-3 d-lg-none" :rounded="0"><v-img :src="'/assets/platforms/'+currentPlatform.slug+'.png'"></v-img></v-avatar>
        <!-- App bar - Platform title - desktop -->
        <v-toolbar-title class="text-h6 hidden-sm-and-down ml-4"/>
        <!-- App bar - Scan progress bar -->
        <v-progress-linear :active="scanning" :indeterminate="true" absolute/>
        <!-- App bar - Upload -->
        <v-app-bar-nav-icon title="settings" @click="uploadRom()" rounded="0"><v-icon>mdi-upload</v-icon></v-app-bar-nav-icon>
        <!-- App bar - Search bar -->
        <v-text-field @click:clear="setFilter('')" @keyup="setFilter(filter)" v-model="filter" label="search" class="ml-5 mr-3" prepend-inner-icon="mdi-magnify" variant="outlined" density="compact" hide-details clearable/>
        <!-- App bar - Settings -->
        <v-app-bar-nav-icon title="settings" @click="settings = !settings" rounded="0"><v-icon>mdi-cog</v-icon></v-app-bar-nav-icon>
    </v-app-bar>

    <!-- Platforms drawer -->
    <v-navigation-drawer v-model="drawer" :rail="rail" width="300" rail-width="72">
        <v-list>
            <!-- Platforms drawer - Platforms list -->
            <v-list-item v-for="platform in platforms"
                :value="platform.slug"
                :key="platform"
                @:click="selectPlatform(platform)" class="pt-4 pb-4">
                <v-list class="text-subtitle-2">{{ rail ? '' : platform.name }}</v-list>
                <template v-slot:prepend>
                    <v-avatar :rounded="0"><v-img :src="'/assets/platforms/'+platform.slug+'.png'"></v-img></v-avatar>
                </template>
                <template v-slot:append>
                    <v-chip class="ml-4" size="small">250</v-chip>
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