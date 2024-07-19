<script setup lang="ts">
import HomeBtn from "@/components/common/Navigation/HomeBtn.vue";
import PlatformsBtn from "@/components/common/Navigation/PlatformsBtn.vue";
import CollectionsBtn from "@/components/common/Navigation/CollectionsBtn.vue";
import ScanBtn from "@/components/common/Navigation/ScanBtn.vue";
import SearchBtn from "@/components/common/Navigation/SearchBtn.vue";
import UploadBtn from "@/components/common/Navigation/UploadBtn.vue";
import UserBtn from "@/components/common/Navigation/UserBtn.vue";
</script>
<template>
  <v-app-bar
    :elevation="0"
    class="bg-primary justify-center px-1"
    mode="shift"
    height="45"
  >
    <template #prepend>
      <home-btn />
    </template>

    <search-btn />
    <platforms-btn />
    <collections-btn />
    <v-divider opacity="0" class="mx-3" vertical />
    <upload-btn />
    <scan-btn />
    
    <template #append>
      <user-btn />
    </template>
  </v-app-bar>
</template>
