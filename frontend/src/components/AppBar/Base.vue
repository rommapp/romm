<script setup>
import { storeScanning } from '@/stores/scanning.js'
import DrawerToggle from '@/components/AppBar/DrawerToggle.vue'

// Props
const scanning = storeScanning()
</script>

<template>

    <v-app-bar elevation="1" density="comfortable">
        <v-progress-linear color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute/>
        <drawer-toggle class="ml-5"/>
    </v-app-bar>

</template>
