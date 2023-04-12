<script setup>
import axios from "axios"
import { ref, inject, toRaw } from "vue"
import { useTheme } from "vuetify"

const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION
const settingsDrawer = ref(false)
const platforms = ref([])
const platformsToScan = ref([])
const scanning = ref(false)
const fullScan = ref(false)
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'light') ? ref(false) : ref(true)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('settingsDrawer', () => { settingsDrawer.value = !settingsDrawer.value })
emitter.on('platforms', (p) => { platforms.value = p })

// Functions
async function scan() {
    scanning.value = true
    const platforms = []
    toRaw(platformsToScan)._rawValue.forEach(p => {platforms.push(toRaw(p.slug))})

    await axios.get('/api/scan?platforms_to_scan='+JSON.stringify(platforms)+'&full_scan='+fullScan.value).then((response) => {
        emitter.emit('snackbarScan', {'msg': 'Scan completed successfully!', 'icon': 'mdi-check-bold', 'color': 'green'})
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't complete scan. Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    scanning.value = false
    emitter.emit('scanning', false)
    emitter.emit('refresh')
}

function toggleTheme() {
    // Toggle dark/light theme
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}
</script>

<template>

    <!-- Settings drawer -->
    <v-navigation-drawer v-model="settingsDrawer" location="right" width="270" temporary floating>
        <!-- Settings drawer - title -->
        <v-list-item class="text-h5 d-flex align-center justify-center font-weight-bold bg-primary pt-4 pb-4 pl-7">
            Settings
            <v-btn title="close settings" @click="settingsDrawer = !settingsDrawer" class="ml-1" icon="mdi-close-box" rounded="0" variant="plain"/>
        </v-list-item>
        <v-divider class="border-opacity-100" :thickness="2"/>
        <v-list>
            <!-- Settings drawer - scan button -->
            <v-select label="Platforms" item-title="name" v-model="platformsToScan" :items="platforms" class="pl-5 pr-5 mt-2 mb-1" density="comfortable" variant="outlined" multiple return-object clearable hide-details chips/>
            <v-list-item class="pa-0">
                <v-row class="align-center">
                    <v-col class="d-flex justify-center">
                        <v-btn title="scan" @click="scan()" :disabled="scanning" prepend-icon="mdi-magnify-scan" class="ml-7" color="secondary" rounded="0" inset>
                            <p v-if="!scanning">Scan</p>
                            <v-progress-circular v-show="scanning" class="ml-2" :width="2" :size="20" indeterminate/>
                        </v-btn>
                    </v-col>
                    <v-col class="mr-4">
                        <v-checkbox v-model="fullScan" label="Full scan" hide-details="true"/>
                    </v-col>
                </v-row>
            </v-list-item>
        </v-list>
        <!-- Settings drawer - theme toggle -->
        <template v-slot:append>
            <v-divider class="border-opacity-25"/>
            <v-list-item class="d-flex align-center justify-center">
                <v-switch @change="toggleTheme()" v-model="darkMode" class="pr-2 pl-2" hide-details="false" prepend-icon="mdi-theme-light-dark" inset/>
            </v-list-item>
            <v-divider class="border-opacity-25"/>
            <v-list-item class="d-flex justify-center alignt-center text-body-2">
                <p>RomM v{{ ROMM_VERSION }}</p>
            </v-list-item>
        </template>
    </v-navigation-drawer>
</template>
