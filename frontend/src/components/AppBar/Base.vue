<script setup>
import { ref, inject } from "vue"
import PlatformsBtn from '@/components/AppBar/PlatformsBtn.vue'
import UploadBtn from '@/components/AppBar/UploadBtn.vue'
import SearchBar from '@/components/AppBar/SearchBar.vue'
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
            
        <platforms-btn/>
        
        <v-spacer class="hidden-xs-and-down"/>
        
        <upload-btn/>
        
        <search-bar/>
            
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
