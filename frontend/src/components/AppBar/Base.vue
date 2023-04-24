<script setup>
import MainDrawerToggle from '@/components/AppBar/Gallery/MainDrawerToggle.vue'
import { storeScanning } from '@/stores/scanning.js'
import { storeContextBar } from '@/stores/contextBar.js'
import { useRoute } from 'vue-router'

// Props
const scanning = storeScanning()
const contextBar = storeContextBar()
const route = useRoute()
</script>

<template>

    <v-app-bar elevation="1" density="comfortable">

        <v-progress-linear color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute/>

        <main-drawer-toggle class="ml-5 hidden-lg-and-up"/>

        <template v-slot:append>
            <v-app-bar-nav-icon v-if="route.params.platform != undefined"
                @click="contextBar.toggleContextBar()"
                rounded="0">
                <v-icon :icon="contextBar.value ? 'mdi-chevron-up' : 'mdi-chevron-down' "/>
            </v-app-bar-nav-icon>
        </template>
        
    </v-app-bar>

</template>

<style scoped>
.home-btn{
    cursor: pointer;
}
</style>
