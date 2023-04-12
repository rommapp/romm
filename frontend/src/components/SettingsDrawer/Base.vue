<script setup>
import { ref, inject } from "vue"
import SettingsHeader from '@/components/SettingsDrawer/Header.vue'
import Scan from '@/components/SettingsDrawer/Scan.vue'
import ThemeToggle from '@/components/SettingsDrawer/ThemeToggle.vue'
import VersionLabel from '@/components/SettingsDrawer/VersionLabel.vue'

// Props
const settingsDrawer = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('toggleSettings', () => { settingsDrawer.value = !settingsDrawer.value })
</script>

<template>

    <v-navigation-drawer
        v-model="settingsDrawer"
        location="right"
        width="270"
        temporary
        floating>
        
        <settings-header/>

        <v-divider class="border-opacity-100" :thickness="2"/>
        
        <scan/>

        <template v-slot:append>
            <v-divider class="border-opacity-25"/>
            <theme-toggle/>
            <v-divider class="border-opacity-25"/>
            <version-label/>
        </template>

    </v-navigation-drawer>
</template>
