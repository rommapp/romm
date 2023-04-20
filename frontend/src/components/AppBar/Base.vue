<script setup>
import { ref, inject } from "vue"
import PlatformsBtn from '@/components/AppBar/PlatformsBtn.vue'
import FilterBar from '@/components/AppBar/FilterBar.vue'
import FilterBtn from '@/components/AppBar/FilterBtn.vue'
import GalleryViewBtn from '@/components/AppBar/GalleryViewBtn.vue'
import SettingsBtn from '@/components/AppBar/SettingsBtn.vue'

// Props
const scanning = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('scanning', (s) => { scanning.value = s })
</script>

<template>

    <v-app-bar>

        <v-progress-linear color="rommAccent1" :active="scanning" :indeterminate="true" absolute/>

        <router-link to="/">
            <v-avatar size="100" class="ml-3 home-btn hidden-sm-and-down"><v-img src="/assets/romm_complete.svg"></v-img></v-avatar>
        </router-link>
            
        <platforms-btn class="ml-2 hidden-lg-and-up"/>
        
        <v-spacer class="hidden-xs-and-down"/>
        
        <filter-bar class="mr-2 ml-2 hidden-xs"/>

        <filter-btn class="ml-2 hidden-sm-and-up"/>
            
        <template v-slot:append>
            <gallery-view-btn/>
            <settings-btn/>
        </template>
        
    </v-app-bar>

</template>

<style scoped>
.home-btn{
    cursor: pointer;
}
</style>
