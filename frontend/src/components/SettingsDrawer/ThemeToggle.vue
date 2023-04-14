<script setup>
import { ref } from "vue"
import { useTheme } from "vuetify"

// Props
// const theme = useTheme()
// const darkMode = (localStorage.getItem('theme') == 'light') ? ref(false) : ref(true)
const darkMode = ref(true)

// Functions
function toggleTheme() {
    console.log("changed theme")
    // theme.global.name.value = darkMode.value ? "dark" : "light"
    // darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
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