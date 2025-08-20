<template>
  <div class="relative min-h-screen overflow-y-auto overflow-x-hidden max-w-[100vw] flex">
    <div
      class="fixed inset-0 bg-cover bg-center blur-[40px] saturate-[1.3] opacity-20 scale-105 pointer-events-none"
      :style="{ backgroundImage: current && (current.path_cover_large||current.path_cover_small||current.url_cover) ? `url(${current.path_cover_large||current.path_cover_small||current.url_cover})` : '' }"
    />
    <div class="fixed inset-0 bg-gradient-to-b from-black/70 via-black/20 to-black/80 pointer-events-none" />

    <div
      class="relative z-10 flex-1 min-w-0 pr-[40px]"
      :style="{ width: 'calc(100vw - 40px)' }"
    >
      <div class="mx-10 md:mx-16 lg:mx-20 xl:mx-28 pt-6">
        <h1 class="text-white/90 text-3xl font-bold drop-shadow">
          {{ current?.platform_name || current?.platform_slug?.toUpperCase() || 'Platform' }}
        </h1>
      </div>

      <div
        v-if="loading"
        class="text-center text-fgDim mt-8"
      >
        Loading games…
      </div>
      <div
        v-else-if="error"
        class="text-center text-red-400 mt-8"
      >
        {{ error }}
      </div>
      <div v-else>
        <div
          v-if="filtered.length===0"
          class="text-center text-fgDim p-4"
        >
          No games found.
        </div>
        <div
          ref="gridRef"
          class="grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-5 px-13 md:px-16 lg:px-20 xl:px-28 py-8 relative z-10 w-full box-border overflow-x-hidden"
        >
          <GameCard
            v-for="(rom,i) in filtered"
            :key="rom.id"
            :rom="rom"
            :index="i"
            :selected="i===selectedIndex"
            :loaded="!!loadedMap[rom.id]"
            @click="selectAndOpen(i, rom)"
            @mouseenter="mouseSelect(i)"
            @focus="mouseSelect(i)"
            @loaded="markLoaded(rom.id)"
          />
        </div>
      </div>
    </div>

    <div
      class="w-[40px] bg-black/30 backdrop-blur border-l border-white/10 fixed top-0 right-0 h-screen overflow-hidden z-10 flex-shrink-0"
      :class="{ 'bg-[rgba(248,180,0,0.1)] border-l-[rgba(248,180,0,0.3)]': inAlphabet }"
    >
      <div class="flex flex-col h-screen p-2 items-center justify-evenly">
        <button
          v-for="(L,i) in letters"
          :key="L"
          class="bg-white/5 border border-white/10 text-fgDim rounded w-7 h-7 text-[0.7rem] font-semibold flex items-center justify-center shrink-0 transition-all hover:text-fg0 hover:border-white/30 hover:bg-white/10"
          :class="{ 'bg-[var(--accent-2)] border-[var(--accent)] text-black shadow-[0_0_0_2px_rgba(248,180,0,0.25)]': inAlphabet && i===alphaIndex }"
          @click="jumpToLetter(L)"
        >
          {{ L }}
        </button>
      </div>
    </div>

    <NavigationHint :hints="['Arrow Keys Navigate', 'Enter Select', 'Esc Back']" />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import romApi from '@/services/api/rom';
import GameCard from '@/console/components/GameCard.vue';
import NavigationHint from '@/console/components/NavigationHint.vue';
import type { SimpleRomSchema } from '@/__generated__/models/SimpleRomSchema';

const route = useRoute();
const router = useRouter();
const platformId = Number(route.params.id);

const roms = ref<SimpleRomSchema[]>([]);
const loading = ref(true);
const error = ref('');
const selectedIndex = ref(0);
const query = ref('');
const loadedMap = ref<Record<number, boolean>>({});
const keyboardMode = ref(false);
let keyboardTimeout: number | undefined;
const inAlphabet = ref(false);
const alphaIndex = ref(0);
const gridRef = ref<HTMLDivElement>();

const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return q ? roms.value.filter(r => (r.name||'').toLowerCase().includes(q)) : roms.value;
});

const current = computed(() => filtered.value[selectedIndex.value] || filtered.value[0]);

function getCols(): number {
  if (!gridRef.value) return 4;
  try{
    const style = window.getComputedStyle(gridRef.value);
    return Math.max(1, style.gridTemplateColumns.split(' ').length);
  }catch{
    return 4;
  }
}

function scrollToSelected(){
  if(!keyboardMode.value || filtered.value.length===0) return;
  requestAnimationFrame(() => {
    const w = window as unknown as { gameCardElements?: HTMLElement[] };
    const el = w.gameCardElements?.[selectedIndex.value];
  const fallback = document.querySelectorAll('.block.bg-\\[var\\(--tile\\)\\]');
    const target = el || (fallback[selectedIndex.value] as HTMLElement | undefined);
    if(target?.scrollIntoView) target.scrollIntoView({ behavior:'smooth', block:'center', inline:'nearest' });
  });
}

watch(selectedIndex, () => { if(keyboardMode.value) scrollToSelected(); });

function handleKey(e: KeyboardEvent){
  if(!filtered.value.length) return;
  keyboardMode.value = true; window.clearTimeout(keyboardTimeout); keyboardTimeout = window.setTimeout(()=> keyboardMode.value=false, 3000);
  if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter'].includes(e.key)) e.preventDefault();

  if(inAlphabet.value){
    if(e.key==='ArrowLeft'){ inAlphabet.value=false; return; }
    if(e.key==='ArrowUp'){ alphaIndex.value = Math.max(0, alphaIndex.value-1); return; }
    if(e.key==='ArrowDown'){ alphaIndex.value = Math.min(letters.length-1, alphaIndex.value+1); return; }
    if(e.key==='Enter'){
      const L = letters[alphaIndex.value];
      const idx = filtered.value.findIndex(r => (r.name||'').toUpperCase().startsWith(L));
      if(idx>=0){ selectedIndex.value = idx; inAlphabet.value=false; }
      return;
    }
    return;
  }

  const cols = getCols();
  switch(e.key){
    case 'ArrowRight':{
      const atRight = (selectedIndex.value + 1) % cols === 0;
      const last = selectedIndex.value === filtered.value.length-1;
      if(atRight || last){ inAlphabet.value = true; alphaIndex.value = 0; }
      else selectedIndex.value = Math.min(filtered.value.length-1, selectedIndex.value+1);
      break; }
    case 'ArrowLeft': selectedIndex.value = Math.max(0, selectedIndex.value-1); break;
    case 'ArrowUp': { const ni = selectedIndex.value - cols; if(ni>=0) selectedIndex.value = ni; break; }
    case 'ArrowDown': { const ni = selectedIndex.value + cols; if(ni < filtered.value.length) selectedIndex.value = ni; break; }
    case 'Enter': {
      const rom = filtered.value[selectedIndex.value];
      router.push({ name: 'console-rom', params: { rom: rom.id }, query: { id: platformId } });
      break; }
  }
}

function mouseSelect(i:number){ if(!keyboardMode.value) selectedIndex.value = i; }
function selectAndOpen(i:number, rom: SimpleRomSchema){ selectedIndex.value = i; router.push({ name: 'console-rom', params: { rom: rom.id }, query: { id: platformId } }); }
function jumpToLetter(L:string){ const idx = filtered.value.findIndex(r => (r.name||'').toUpperCase().startsWith(L)); if(idx>=0){ selectedIndex.value = idx; inAlphabet.value=false; keyboardMode.value=true; window.clearTimeout(keyboardTimeout); keyboardTimeout = window.setTimeout(()=> keyboardMode.value=false, 3000); } }

onMounted(async () => {
  try{
    const { data } = await romApi.getRoms({ platformId, limit: 500, orderBy: 'name', orderDir: 'asc' });
    roms.value = data.items ?? [];
    // mark those without cover as loaded immediately (no skeleton needed)
    for (const r of roms.value) {
      if (!r.url_cover && !r.path_cover_large && !r.path_cover_small) {
        loadedMap.value[r.id] = true;
      }
    }
  }catch(err: unknown){ error.value = err instanceof Error ? err.message : 'Failed to load roms'; }
  finally{ loading.value = false; }
  window.addEventListener('keydown', handleKey);
});

function markLoaded(id: number){ loadedMap.value[id] = true; }
</script>
