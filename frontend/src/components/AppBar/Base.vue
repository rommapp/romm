<script setup>
import MainDrawerToggle from '@/components/AppBar/Gallery/MainDrawerToggle.vue'
import { storeScanning } from '@/stores/scanning.js'

// Props
const scanning = storeScanning()
</script>

<template>

    <v-app-bar elevation="1">

        <v-progress-linear color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute/>

        <main-drawer-toggle class="ml-5 hidden-lg-and-up"/>
        
    </v-app-bar>

</template>

<style scoped>
.home-btn{
    cursor: pointer;
}
</style>
