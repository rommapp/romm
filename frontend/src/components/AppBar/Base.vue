<script setup>
import { ref, inject } from "vue"
import { useRouter } from 'vue-router'
import PlatformsBtn from '@/components/AppBar/PlatformsBtn.vue'
import UploadBtn from '@/components/AppBar/UploadBtn.vue'
import SearchBar from '@/components/AppBar/SearchBar.vue'
import GalleryViewBtn from '@/components/AppBar/GalleryViewBtn.vue'
import SettingsBtn from '@/components/AppBar/SettingsBtn.vue'

// Props
const scanning = ref(false)
const router = useRouter()

// Event listeners bus
const emitter = inject('emitter')
emitter.on('scanning', (s) => { scanning.value = s })

// Functions
async function goHome(){
    await router.push(import.meta.env.BASE_URL)
}
</script>

<template>

    <v-app-bar class="elevation-3">

        <v-progress-linear :active="scanning" :indeterminate="true" absolute/>

        <v-avatar size="100" class="ml-3 home-btn hidden-sm-and-down" @click="goHome()"><v-img src="/assets/romm.svg"></v-img></v-avatar>
            
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
