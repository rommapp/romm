<script setup>
import { ref } from "vue"
import { useTheme } from "vuetify"

// Props
const tab = ref('ui')
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'rommDark') ? ref(true) : ref(false)
const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION

// Functions
function toggleTheme() {
    theme.global.name.value = darkMode.value ? "rommDark" : "rommLight"
    darkMode.value ? localStorage.setItem('theme', 'rommDark') : localStorage.setItem('theme', 'rommLight')
}
</script>
<template>

    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
        <v-tab value="general" rounded="0" disabled>General<span class="text-caption text-truncate ml-1">[comming soon]</span></v-tab>
        <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
    <v-window v-model="tab">
        <v-window-item value="general"/>
        <v-window-item value="ui" class="pa-2">
            <v-row no-gutters>
                <v-switch
                @change="toggleTheme()"
                v-model="darkMode"
                class="ml-2"
                prepend-icon="mdi-theme-light-dark"
                hide-details
                inset/>
            </v-row>
        </v-window-item>
    </v-window>

    <v-bottom-navigation density="compact" :elevation="0" class="text-caption">
        <v-row no-gutters class="justify-center align-center">
            <span class="text-rommAccent1 ml-2">RomM</span><span class="ml-1">v{{ ROMM_VERSION }}</span>
        </v-row>
    </v-bottom-navigation>

</template>

<style scoped>
</style>