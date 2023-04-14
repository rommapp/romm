<script setup>
import { ref } from "vue"
import { useTheme } from "vuetify"

// Props
const theme = useTheme()
const darkMode = (localStorage.getItem('theme') == 'rommLight') ? ref(false) : ref(true)

// Functions
function toggleTheme() {
    theme.global.name.value = darkMode.value ? "rommDark" : "rommLight"
    darkMode.value ? localStorage.setItem('theme', 'rommDark') : localStorage.setItem('theme', 'rommLight')
}
</script>

<template>
    <v-list-item class="d-flex align-center justify-center">
        <v-switch
            @change="toggleTheme()"
            v-model="darkMode"
            class="pr-2 pl-2"
            prepend-icon="mdi-theme-light-dark"
            hide-details
            inset/>
    </v-list-item>
</template>