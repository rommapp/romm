<script setup>
import { ref, inject } from "vue"
import RomMIcon from '@/components/AppBar/RomMIcon.vue'
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

    <v-app-bar class="elevation-3">

        <v-progress-linear
            :active="scanning"
            :indeterminate="true"
            absolute/>
        
        <rom-m-icon/>

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
