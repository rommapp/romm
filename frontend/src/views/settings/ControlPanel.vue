<script setup>
import { ref } from "vue"
import { useTheme } from "vuetify"
import AppBar from '@/components/AppBar/Base.vue'
import { useDisplay } from "vuetify"

// Props
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'rommLight') ? ref(false) : ref(true)
const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION
const tab = ref('ui')
const { mdAndDown } = useDisplay()

// Functions
function toggleTheme() {
    theme.global.name.value = darkMode.value ? "rommDark" : "rommLight"
    darkMode.value ? localStorage.setItem('theme', 'rommDark') : localStorage.setItem('theme', 'rommLight')
}

</script>
<template>

    <app-bar v-if="mdAndDown"/>

    <v-tabs v-model="tab" slider-color="rommAccent1">
        <v-tab value="saves" rounded="0" disabled>General<span class="text-caption text-truncate ml-1">{{ rail ? '' : '[comming soon]' }}</span></v-tab>
        <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
    <v-window v-model="tab" class="mt-2">
        <v-window-item value="general">
        </v-window-item>
        <v-window-item value="ui">
            <v-row class="ml-1">
                <v-col>
                    <v-switch
                        @change="toggleTheme()"
                        v-model="darkMode"
                        prepend-icon="mdi-theme-light-dark"
                        hide-details
                        inset/>
                </v-col>
            </v-row>
        </v-window-item>
    </v-window>

    <v-divider class="border-opacity-25 mt-2"/>

    <div class="mt-4 text-caption">
        <span class="text-rommAccent1">RomM</span><span> v{{ ROMM_VERSION }}</span>
    </div>

</template>

<style scoped>
</style>