<script setup>
import MainDrawerToggle from '@/components/AppBar/Gallery/MainDrawerToggle.vue'
import FilterBar from '@/components/AppBar/Gallery/FilterBar.vue'
import FilterBtn from '@/components/AppBar/Gallery/FilterBtn.vue'
import GalleryViewBtn from '@/components/AppBar/Gallery/GalleryViewBtn.vue'
import { storeScanning } from '@/stores/scanning.js'

// Props
const scanning = storeScanning()
</script>

<template>

    <v-app-bar elevation="1">

        <v-progress-linear color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute/>

        <main-drawer-toggle class="ml-5 hidden-lg-and-up"/>

        <v-spacer class="hidden-lg-and-up"/>
        <v-avatar rounded="0" class="ml-5 hidden-lg-and-up">
            <v-img v-if="$route.params.platform !== undefined" :src="'/assets/platforms/'+$route.params.platform+'.ico'"/>
        </v-avatar>
        <v-spacer class="hidden-lg-and-up"/>

        <filter-bar class="mr-2 ml-2 hidden-md-and-down"/>
        
        <template v-slot:append>
            <filter-btn class="ml-2 hidden-lg-and-up"/>
            <gallery-view-btn/>
        </template>
        
    </v-app-bar>

</template>

<style scoped>
.home-btn{
    cursor: pointer;
}
</style>
