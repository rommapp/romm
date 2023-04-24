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

        <platforms-btn class="ml-5 hidden-lg-and-up"/>

        <v-avatar rounded="0" class="ml-5 hidden-lg-and-up">
            <v-img v-if="$route.params.platform !== undefined" :src="'/assets/platforms/'+$route.params.platform+'.ico'"/>
        </v-avatar>

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
