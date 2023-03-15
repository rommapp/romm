<script setup>
import axios from "axios"
import { ref } from "vue"
import { useTheme } from "vuetify";


const emit = defineEmits(['currentPlatformSlug'])
defineExpose({ gettingRoms })
const platforms = ref([])
const currentPlatformName = ref(localStorage.getItem('currentPlatformName') || "")
const scanOverwrite = ref(false)
const scanning = ref(false)
const gettingRomsFlag = ref(false)
const drawer = ref(null)
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'light') ? ref(false) : ref(true)


async function getPlatforms() {
    console.log("Getting platforms...")
    await axios.get('http://'+location.hostname+':5000/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    }).catch((error) => {console.log(error)})
}

function selectPlatform(platform){    
    localStorage.setItem('currentPlatformSlug', platform.slug)
    localStorage.setItem('currentPlatformName', platform.name)
    currentPlatformName.value = platform.name
    emit('currentPlatformSlug', platform.slug)
}

async function scan() {
    console.log("scanning...")
    scanning.value = true
    await axios.get('http://'+location.hostname+':5000/scan?overwrite='+scanOverwrite.value).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        getPlatforms()
    }).catch((error) => {console.log(error)})
    scanning.value = false
}

function toggleTheme() {
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}

function gettingRoms(flag) {
    gettingRomsFlag.value = flag
}

getPlatforms()
</script>

<template>
    <v-app-bar color="toolbar" >
        <v-app-bar-nav-icon icon="mdi-controller" @click="drawer = !drawer" />
        
        <v-toolbar-title>{{ currentPlatformName }}</v-toolbar-title>
        
        <v-btn icon><v-icon>mdi-magnify</v-icon></v-btn>
        
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

    <v-navigation-drawer width="250" v-model="drawer" >
        <v-list nav>
            <v-list-item v-for="platform in platforms" 
                :title="platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="selectPlatform(platform)">
                <template v-slot:append>
                    <v-progress-circular v-show="gettingRomsFlag && currentPlatformName == platform.name" indeterminate color="primary" :width="2" :size="20" class="ml-2" />
                </template>
            </v-list-item>
        </v-list>
    </v-navigation-drawer>

</template>

<style scoped>
/* .dark_switch {
    overflow: visible !important;
} */
</style>