<script setup>
import { ref } from "vue"
import { useTheme } from "vuetify"

// Props
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'rommLight') ? ref(false) : ref(true)
const ROMM_VERSION = import.meta.env.VITE_ROMM_VERSION

// Functions
function toggleTheme() {
    theme.global.name.value = darkMode.value ? "rommDark" : "rommLight"
    darkMode.value ? localStorage.setItem('theme', 'rommDark') : localStorage.setItem('theme', 'rommLight')
}

</script>
<template>
    <div>
        <v-switch
            @change="toggleTheme()"
            v-model="darkMode"
            prepend-icon="mdi-theme-light-dark"
            hide-details
            inset/>
    </div>

    <v-divider class="border-opacity-25"/>

    <div class="mt-4">
        <span class="text-rommAccent1">RomM</span><span> v{{ ROMM_VERSION }}</span>
    </div>

</template>

<style scoped>
</style>