<script setup>
import PlatformsBtn from '@/components/AppBar/PlatformsBtn.vue'
import FilterBar from '@/components/AppBar/FilterBar.vue'
import FilterBtn from '@/components/AppBar/FilterBtn.vue'
import GalleryViewBtn from '@/components/AppBar/GalleryViewBtn.vue'
import { storeScanning } from '@/stores/scanning.js'

// Props
const scanning = storeScanning()
</script>

<template>

    <v-app-bar elevation="1">

        <v-progress-linear color="rommAccent1" :active="scanning.value" :indeterminate="true" absolute/>

        <router-link to="/">
            <v-avatar size="100" class="ml-7 home-btn hidden-sm-and-down"><v-img src="/assets/romm_complete.svg"></v-img></v-avatar>
        </router-link>
            
        <platforms-btn class="ml-5 hidden-lg-and-up"/>
        
        <v-spacer class="hidden-xs-and-down"/>
        
        <filter-bar class="mr-2 ml-2 hidden-xs"/>

        <filter-btn class="ml-2 hidden-sm-and-up"/>
            
        <template v-slot:append>
            <gallery-view-btn/>
        </template>
        
    </v-app-bar>

</template>

<style scoped>
.home-btn{
    cursor: pointer;
}
</style>
