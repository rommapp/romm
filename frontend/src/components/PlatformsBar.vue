<script setup>
import axios from "axios"
import { ref, inject } from "vue"
import { useTheme } from "vuetify";

// Props
const platforms = ref([])
const backPort = import.meta.env.VITE_BACK_PORT
const currentPlatformName = ref(localStorage.getItem('currentPlatformName') || "")
const scanOverwrite = ref(false)
const scanning = ref(false)
const gettingRomsFlag = ref(false)
const drawer = ref(null)
const filter = ref('')
const rail = ref(false)
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'light') ? ref(false) : ref(true)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('gettingRoms', (flag) => { gettingRomsFlag.value = flag })

// Functions
async function getPlatforms() {
    // Get the list of the platforms for the navigation drawer
    console.log("Getting platforms...")
    await axios.get('http://'+location.hostname+':'+backPort+'/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    }).catch((error) => {console.log(error)})
}

function selectPlatform(platform){    
    // Select the current platform
    localStorage.setItem('currentPlatformSlug', platform.slug)
    localStorage.setItem('currentPlatformName', platform.name)
    emitter.emit('currentPlatform', platform.slug)
    currentPlatformName.value = platform.name
}

async function scan() {
    // Scan and then get the platforms again
    console.log("scanning...")
    scanning.value = true
    await axios.get('http://'+location.hostname+':'+backPort+'/scan?overwrite='+scanOverwrite.value).then((response) => {
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
    <v-app-bar color="toolbar" density="compact">

        <v-app-bar-nav-icon @click="drawer = !drawer" class="hidden-lg-and-up"/>

        <v-toolbar-title class="d-flex align-center justify-center text-h6">{{ currentPlatformName }}</v-toolbar-title>

        <v-text-field hide-details single-line label="search" prepend-inner-icon="mdi-magnify" v-model="filter" @keyup="setFilter(filter)" />

        <v-menu :close-on-content-click="false" >
            <template v-slot:activator="{ props }">
                <v-btn v-bind="props" icon><v-icon>mdi-dots-vertical</v-icon></v-btn>
            </template>
            <v-list>
                <v-list-item class="d-flex align-center justify-center mb-2">
                    <v-btn :disabled="scanning" color="secondary" prepend-icon="mdi-magnify-scan" @click="scan()" inset >
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
        </v-menu>
    </v-app-bar>

    <v-navigation-drawer width="250" rail-width="72" v-model="drawer" :rail="rail">
        <v-list nav>

            <v-list-item class="mt-1">
                <template v-slot:prepend>
                    <v-avatar :rounded="0"><v-img src="/assets/romm.png"></v-img></v-avatar>
                </template>
                <v-list-item-title class="text-subtitle-2">Rom Manager</v-list-item-title>
            </v-list-item>

            <v-divider class="mt-3 mb-1"></v-divider>

            <v-list-item v-for="platform in platforms" 
                :title="rail ? platform.slug : platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="selectPlatform(platform)">
                <template v-slot:append>
                    <v-progress-circular v-show="gettingRomsFlag && currentPlatformName == platform.name" indeterminate color="primary" :width="2" :size="20" class="ml-2" />
                </template>
            </v-list-item>
        </v-list>

        <template v-slot:append>
            <v-btn block @click="rail = !rail">
                <v-icon v-if="rail">mdi-arrow-collapse-right</v-icon>
                <v-icon v-if="!rail">mdi-arrow-collapse-left</v-icon>
            </v-btn>
        </template>
    </v-navigation-drawer>

</template>