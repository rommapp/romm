<script setup>
import axios from "axios"
import { ref, inject, toRaw } from "vue"
import { useRouter } from 'vue-router'
import { useTheme } from "vuetify";

// Props
const platforms = ref([])
const currentPlatformName = ref(localStorage.getItem('currentPlatformName') || "")
const currentPlatformSlug = ref(localStorage.getItem('currentPlatformSlug') || "")
const platformsToScan = ref([])
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
    axios.get('/api/platforms').then((response) => {
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
    // Complete scan of by platform
    console.log("scanning...")
    scanning.value = true
    emitter.emit('scanning', true)
    const platforms = []
    toRaw(platformsToScan)._rawValue.forEach(p => {
        platforms.push(toRaw(p))
    })
    console.log(platforms)
    if (!platforms.length){
        console.log("scanning all platforms")
        await axios.get('/api/scan?overwrite='+scanOverwrite.value).then((response) => {
            console.log("scan completed")
            console.log(response.data)
        }).catch((error) => {console.log(error)})
        scanning.value = false
        emitter.emit('scanning', false)
        // router.go()
    }
    else{
        platforms.forEach(async p => {
            console.log("scanning: "+p.name)
            await axios.put('/api/scan/platform?overwrite='+scanOverwrite.value, {
                p_slug: p.slug,
                p_igdb_id: p.igdb_id
            }).then((response) => {
                console.log("scan "+p.name+" completed")
                console.log(response.data)
            }).catch((error) => {console.log(error)})
            scanning.value = false
            emitter.emit('scanning', false)
            // router.go()
        });
    }
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
    <!-- Settings drawer -->
    <v-navigation-drawer width="250" v-model="settings" location="right" temporary floating>
        <!-- Settings drawer - title -->
        <v-list-item id="settings-title" class="text-h5 d-flex align-center justify-center pt-4 pb-4 pl-7 font-weight-bold bg-primary">
            Settings<v-btn icon="mdi-close-box" class="ml-1" rounded="0" variant="plain" @click="settings = !settings"/>
        </v-list-item>
        <v-divider class="border-opacity-100" :thickness="2"></v-divider>
        <v-list>
            <!-- Settings drawer - scan button -->
            <v-list-item class="d-flex align-center justify-center mb-2">
                <v-btn :disabled="scanning" color="secondary" prepend-icon="mdi-magnify-scan" @click="scan()" inset rounded="0">
                    <p v-if="!scanning">Scan</p>
                    <p v-if="scanning">Scanning</p>
                    <v-progress-circular v-show="scanning" indeterminate color="primary" :width="2" :size="20" class="ml-2" />
                </v-btn>
            </v-list-item>
            <v-select class="pl-2 pr-2" v-model="platformsToScan" :items="platforms" item-title="name" label="Platforms" multiple return-object clearable density="comfortable" variant="outlined" />
            <v-divider class="border-opacity-25"></v-divider>
            <!-- Settings drawer - theme toggle -->
            <v-list-item class="d-flex align-center justify-center">
                <v-switch prepend-icon="mdi-theme-light-dark" class="pr-2 pl-2" v-model="darkMode" @change="toggleTheme()" hide-details="true" inset/>
            </v-list-item>
            <v-divider class="border-opacity-25"></v-divider>
        </v-list>
    </v-navigation-drawer>

    <!-- App bar -->
    <v-app-bar color="toolbar" class="elevation-3" >
        <!-- App bar - RomM avatar -->
        <v-avatar class="ml-4" :rounded="0"><v-img src="/assets/romm.png"></v-img></v-avatar>
        <!-- App bar - RomM title -->
        <v-list-item-title class="text-h6 ml-5 hidden-md-and-down font-weight-black">ROM MANAGER</v-list-item-title>
        <!-- App bar - Platforms drawer toggle -->
        <v-app-bar-nav-icon @click="drawer = !drawer" rounded="0" class="hidden-lg-and-up ml-1"/>
        <!-- App bar - Platform title - desktop -->
        <v-toolbar-title class="align-center justify-center text-h6 ml-4 d-none d-sm-flex"></v-toolbar-title>
        <!-- App bar - Platform title - mobile -->
        <v-toolbar-title class="align-center text-h6 ml-2 d-sm-none">
            <v-avatar class="mr-3" :rounded="0"><v-img :src="'/assets/platforms/'+currentPlatformSlug+'.png'"></v-img></v-avatar>
        </v-toolbar-title>
        <!-- App bar - Scan progress bar -->
        <v-progress-linear absolute bottom :active="scanning" :indeterminate="true" id="scan-progress"/>
        <!-- App bar - Search bar -->
        <v-text-field hide-details label="search" variant="outlined" density="compact" class="ml-5 mr-3" clearable prepend-inner-icon="mdi-magnify" v-model="filter" @keyup="setFilter(filter)" @click:clear="setFilter('')"/>
        <!-- App bar - Settings -->
        <v-app-bar-nav-icon @click="settings = !settings" rounded="0"><v-icon>mdi-cog</v-icon></v-app-bar-nav-icon>
    </v-app-bar>

    <!-- Platforms drawer -->
    <v-navigation-drawer width="250" rail-width="72" v-model="drawer" :rail="rail">
        <v-list nav>
            <!-- Platforms drawer - Platforms list -->
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
        <!-- Platforms drawer - Platforms list - rail toggle -->
        <template v-slot:append>
            <v-btn block @click="toggleRail()" rounded="0">
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