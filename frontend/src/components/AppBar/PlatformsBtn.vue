<script setup>
import { ref, inject } from "vue"

// Props
const selectedPlatform = ref('')

// Event listeners bus
const emitter = inject('emitter')
emitter.on('selectedPlatform', (p) => { selectedPlatform.value = p })
</script>

<template>
    <v-btn
        @click="emitter.emit('togglePlatforms')"
        class="ma-4 hidden-lg-and-up"
        rounded="0"
        icon>
        <v-avatar rounded="0">
            <v-img v-show="selectedPlatform != ''" :src="'/assets/platforms/'+selectedPlatform.slug+'.ico'"/>
            <v-icon v-show="selectedPlatform == ''" icon="mdi-menu"/>
        </v-avatar>
    </v-btn>
</template>