<template>
  <div class="relative h-screen overflow-hidden bg-gradient-to-b from-bg1 to-bg2">
    <div
      class="absolute inset-0 bg-cover bg-center blur-3xl saturate-150 opacity-40 scale-110 transition-all duration-700"
      :style="{ backgroundImage: currentBackground ? `url(${currentBackground})` : 'none' }"
    />
    <div class="absolute inset-0 bg-gradient-to-b from-black/35 via-black/55 to-black/75" />

    <div class="relative z-10 h-full flex flex-col">
      <div class="mt-8 ml-8 flex items-center gap-3 select-none pb-3">
        <RIsotipo
          :size="40"
          :avatar="false"
        />
        <div class="text-white/90 font-bold text-[28px] drop-shadow-xl">
          Console
        </div>
      </div>

      <div
        v-if="loading"
        class="text-center text-fgDim mt-16"
      >
        Loading platforms…
      </div>
      <div
        v-else-if="error"
        class="text-center text-red-400 mt-16"
      >
        {{ error }}
      </div>
      <div v-else>
        <section class="px-8 pb-2">
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow">
            Platforms
          </h2>
          <div class="relative h-[220px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="prevSystem"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="nextSystem"
            >
              ▶
            </button>
            <div
              ref="systemsRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent="onWheelSystems"
            >
              <div class="flex items-center gap-6 h-full px-8 min-w-max">
                <SystemCard
                  v-for="(p,i) in platforms"
                  :key="p.id"
                  :system="p"
                  :index="i"
                  :selected="navigationMode==='systems' && i===selectedIndex"
                  @click="goPlatform(p.id)"
                  @mouseenter="focusSystem(i)"
                  @focus="focusSystem(i)"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="recent.length>0"
          class="px-8 pb-8"
        >
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow">
            Recently Played
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="prevRecent"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="nextRecent"
            >
              ▶
            </button>
            <div
              ref="recentRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent="onWheelRecent"
            >
              <div class="flex items-center gap-4 h-full px-8 min-w-max">
                <GameCard
                  v-for="(g,i) in recent"
                  :key="`${g.platform_id}-${g.id}`"
                  :rom="g"
                  :index="i"
                  :is-recent="true"
                  :selected="navigationMode==='recent' && i===recentIndex"
                  :loaded="true"
                  @click="goGame(g)"
                  @mouseenter="focusRecent(i)"
                  @focus="focusRecent(i)"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="fixed bottom-4 right-4 z-20 flex gap-2">
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="[{ 'bg-white/10 border-white/40 -translate-y-0.5 shadow-lg': navigationMode==='controls' && controlIndex===0 }]"
          title="Logout (F1)"
          @click="doLogout"
        >
          ⏻
        </button>
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="[{ 'bg-white/10 border-white/40 -translate-y-0.5 shadow-lg': navigationMode==='controls' && controlIndex===1 }]"
          title="Fullscreen (F11)"
          @click="toggleFullscreen"
        >
          ⛶
        </button>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import platformApi from '@/services/api/platform';
import romApi from '@/services/api/rom';
import SystemCard from '@/console/components/SystemCard.vue';
import GameCard from '@/console/components/GameCard.vue';
import RIsotipo from '@/components/common/RIsotipo.vue';
import type { PlatformSchema } from '@/__generated__/models/PlatformSchema';
import type { SimpleRomSchema } from '@/__generated__/models/SimpleRomSchema';
import { useInputScope } from '@/console/composables/useInputScope';
import type { InputAction } from '@/console/input/actions';

const router = useRouter();
const platforms = ref<PlatformSchema[]>([]);
const recent = ref<SimpleRomSchema[]>([]);
const loading = ref(true);
const error = ref('');
const navigationMode = ref<'systems'|'recent'|'controls'>('systems');
const selectedIndex = ref(0);
const recentIndex = ref(0);
const controlIndex = ref(0);
const systemsRef = ref<HTMLDivElement>();
const recentRef = ref<HTMLDivElement>();
const currentBackground = ref('');

function focusSystem(i: number){ navigationMode.value='systems'; selectedIndex.value=i; }
function focusRecent(i: number){ navigationMode.value='recent'; recentIndex.value=i; }

function onWheelSystems(e: WheelEvent){
  const el = systemsRef.value; if(!el) return;
  el.scrollLeft += (e.deltaY || e.deltaX);
}
function onWheelRecent(e: WheelEvent){
  const el = recentRef.value; if(!el) return;
  el.scrollLeft += (e.deltaY || e.deltaX);
}

function doLogout(){ router.push({ name:'login' }); }
function toggleFullscreen(){ const de = document.documentElement as HTMLElement & { requestFullscreen?: () => Promise<void> }; if(!document.fullscreenElement) de.requestFullscreen?.(); else document.exitFullscreen?.(); }
function goPlatform(id:number){ router.push({ name: 'console-platform', params: { id } }); }
function goGame(g: SimpleRomSchema){ router.push({ name: 'console-rom', params: { rom: g.id }, query: { id: g.platform_id } }); }

function scrollToSelected(container: HTMLDivElement|undefined, el: HTMLElement|undefined){ if(!container||!el) return; const cr=container.getBoundingClientRect(); const er=el.getBoundingClientRect(); const left= el.offsetLeft - (cr.width/2) + (er.width/2); container.scrollTo({ left, behavior:'smooth' }); }

function prevSystem(){ selectedIndex.value = (selectedIndex.value - 1 + platforms.value.length) % platforms.value.length; tickScroll(); }
function nextSystem(){ selectedIndex.value = (selectedIndex.value + 1) % platforms.value.length; tickScroll(); }
function prevRecent(){ recentIndex.value = (recentIndex.value - 1 + recent.value.length) % recent.value.length; tickRecentScroll(); }
function nextRecent(){ recentIndex.value = (recentIndex.value + 1) % recent.value.length; tickRecentScroll(); }

function tickScroll(){ const w = window as unknown as { systemCardElements?: HTMLElement[] }; const el = w.systemCardElements?.[selectedIndex.value]; scrollToSelected(systemsRef.value!, el); }
function tickRecentScroll(){ const w = window as unknown as { recentGameElements?: HTMLElement[] }; const el = w.recentGameElements?.[recentIndex.value]; scrollToSelected(recentRef.value!, el); }

const { on } = useInputScope();
function handleAction(action: InputAction): boolean {
  switch(action){
    case 'moveLeft':
      if(navigationMode.value==='systems'){ prevSystem(); return true; }
      if(navigationMode.value==='recent'){ prevRecent(); return true; }
      if(navigationMode.value==='controls'){ controlIndex.value=(controlIndex.value-1+2)%2; return true; }
      return false;
    case 'moveRight':
      if(navigationMode.value==='systems'){ nextSystem(); return true; }
      if(navigationMode.value==='recent'){ nextRecent(); return true; }
      if(navigationMode.value==='controls'){ controlIndex.value=(controlIndex.value+1)%2; return true; }
      return false;
    case 'moveUp':
      if(navigationMode.value==='recent') { navigationMode.value='systems'; return true; }
      if(navigationMode.value==='controls') { navigationMode.value= recent.value.length>0 ? 'recent' : 'systems'; return true; }
      return false;
    case 'moveDown':
      if(navigationMode.value==='systems') { navigationMode.value= recent.value.length>0 ? 'recent' : 'controls'; return true; }
      if(navigationMode.value==='recent') { navigationMode.value='controls'; return true; }
      return false;
    case 'confirm':
      {
        // Controls take precedence if active
        if(navigationMode.value==='controls') { if(controlIndex.value===0) doLogout(); else toggleFullscreen(); return true; }

        // If recent is active or focused, open recent
        const active = document.activeElement as HTMLElement | null;
        const recentFocused = !!(active && recentRef.value && recentRef.value.contains(active));
        if(navigationMode.value==='recent' || recentFocused) {
          const r = recent.value[recentIndex.value];
          if(r) { router.push({ name:'console-rom', params:{ rom: r.id }, query:{ id: r.platform_id } }); return true; }
        }

        // Default/fallback: open currently selected system
        const sys = platforms.value[selectedIndex.value];
        if(sys) { router.push({ name:'console-platform', params: { id: sys.id } }); return true; }
      }
      return false;
    case 'back':
      router.back();
      return true;
    default:
      return false;
  }
}

watch([navigationMode, selectedIndex, recentIndex, platforms, recent], () => {
  let imageUrl = '';
  const sysImages: Record<string,string|undefined> = {
  arcade: '/systems/arcade.webp',
    mame: '/systems/arcade.webp',
    nes: '/systems/nes.webp',
    snes: '/systems/snes.webp',
    n64: '/systems/n64.webp',
    gb: '/systems/gbc.webp',
    gba: '/systems/gba.webp',
    gbc: '/systems/gbc.webp',
    genesis: '/systems/genesis.webp',
    megadrive: '/systems/genesis.webp',
    psp: '/systems/psp.webp',
  };
  if(navigationMode.value==='systems' && platforms.value[selectedIndex.value]){
    const p = platforms.value[selectedIndex.value] as PlatformSchema;
    imageUrl = sysImages[p.slug] || sysImages[p.fs_slug] || '';
  } else if(navigationMode.value==='recent' && recent.value[recentIndex.value]){
    const g = recent.value[recentIndex.value];
    imageUrl = g.path_cover_large || g.path_cover_small || g.url_cover || '';
  } else if(navigationMode.value==='controls' && platforms.value[selectedIndex.value]){
    const p = platforms.value[selectedIndex.value] as PlatformSchema;
    imageUrl = sysImages[p.slug] || sysImages[p.fs_slug] || '';
  }
  currentBackground.value = imageUrl || '';
});

onMounted(async () => {
  try{
    const { data: plats } = await platformApi.getPlatforms();
    platforms.value = plats;
    const { data: recents } = await romApi.getRecentPlayedRoms();
    recent.value = recents.items ?? [];
  }catch(err: unknown){ error.value = err instanceof Error ? err.message : 'Failed to load'; }
  finally{ loading.value = false; }
  off = on(handleAction);
});
let off: (() => void) | null = null;
onUnmounted(() => { off?.(); off = null; });
</script>

<style scoped>
</style>
