<template>
  <div class="fixed inset-0 bg-black text-white">
    <div
      id="game"
      class="w-full h-full"
    />
    <div
      v-if="showHint"
      class="absolute top-3 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur px-3 py-1 rounded text-xs text-white/80 border border-white/10"
    >
      Press Start + Select (or F10) to exit
    </div>
  </div>
</template>
<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-explicit-any */
import { onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import romApi from '@/services/api/rom';
import type { DetailedRomSchema } from '@/__generated__/models/DetailedRomSchema';
import { getSupportedEJSCores, getControlSchemeForPlatform, areThreadsRequiredForEJSCore, getDownloadPath } from '@/utils';
import firmwareApi from '@/services/api/firmware';

const route = useRoute();
const router = useRouter();
const romId = Number(route.params.rom);
const showHint = ref(true);
let rafId = 0;
let lastPress: Record<number, number> = { 8: 0, 9: 0 };
const EXIT_WINDOW_MS = 300;
const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

function exitEmulator(){
  try{ (window as any).EJS_emulator?.callEvent?.('exit'); }catch{ /* noop */ }
  router.back();
}

function attachKeyboardExit(){
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'F10') { e.preventDefault(); exitEmulator(); }
  };
  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}

function attachGamepadExit(){
  const loop = () => {
    const pads = navigator.getGamepads?.() || [];
    const now = performance.now();
    for(const pad of pads){
      if(!pad) continue;
      const sel = pad.buttons[8]?.pressed; // Select
      const start = pad.buttons[9]?.pressed; // Start
      if(sel) lastPress[8] = now; if(start) lastPress[9] = now;
      if(sel && start && Math.abs(lastPress[8]-lastPress[9]) <= EXIT_WINDOW_MS){
        exitEmulator(); return; 
      }
    }
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);
  return () => cancelAnimationFrame(rafId);
}

async function boot(){
  // Fetch rom details
  const { data: rom } = await romApi.getRom({ romId });
  const r = rom as DetailedRomSchema;
  document.title = `${r.name} | Play`;

  // Configure EmulatorJS globals
  const supported = getSupportedEJSCores(r.platform_slug);
  const storedCore = localStorage.getItem(`player:${r.platform_slug}:core`);
  const core = (storedCore && supported.includes(storedCore)) ? storedCore : supported[0];
  const w = window as any;
  w.EJS_core = core;
  w.EJS_controlScheme = getControlSchemeForPlatform(r.platform_slug);
  w.EJS_threads = areThreadsRequiredForEJSCore(core);
  w.EJS_gameID = r.id;
  // Disc selection persistence
  const storedDisc = localStorage.getItem(`player:${r.id}:disc`);
  const discId = storedDisc ? parseInt(storedDisc) : null;
  w.EJS_gameUrl = getDownloadPath({ rom: r, fileIDs: discId ? [discId] : [] });
  // BIOS selection persistence
  try {
    const { data: firmware } = await firmwareApi.getFirmware({ platformId: r.platform_id });
    const storedBiosID = localStorage.getItem(`player:${r.platform_slug}:bios_id`);
    const bios = storedBiosID ? firmware.find(f => f.id === parseInt(storedBiosID)) : null;
    w.EJS_biosUrl = bios ? `/api/firmware/${bios.id}/content/${bios.file_name}` : '';
  } catch {
    w.EJS_biosUrl = '';
  }
  w.EJS_player = '#game';
  w.EJS_color = '#A453FF';
  w.EJS_alignStartButton = 'center';
  w.EJS_startOnLoaded = true;
  w.EJS_fullscreenOnLoaded = true;
  w.EJS_backgroundImage = `${window.location.origin}/assets/emulatorjs/powered_by_emulatorjs.png`;
  w.EJS_backgroundColor = '#000000';
  w.EJS_defaultOptions = { 'save-state-location': 'browser', rewindEnabled: 'enabled' };
  // Set a valid game name (affects per-game settings keys)
  w.EJS_gameName = (r.fs_name_no_tags || r.name || '').replace(INVALID_CHARS_REGEX, '').trim();

  // Ensure a controller is auto-assigned to Player 1 when available
  w.EJS_onGameStart = () => {
    const e = (window as any).EJS_emulator;
    if (!e) return;
    const assignFirstPad = () => {
      if (!e.gamepad) return;
      if (!Array.isArray(e.gamepadSelection)) e.gamepadSelection = ['', '', '', ''];
      if (!e.gamepad.gamepads || e.gamepad.gamepads.length === 0) return;
      if (!e.gamepadSelection[0]) {
        const gp = e.gamepad.gamepads[0];
        if (gp) {
          e.gamepadSelection[0] = `${gp.id}_${gp.index}`;
          e.updateGamepadLabels?.();
        }
      }
    };
    // Assign immediately if a pad exists
    assignFirstPad();
    // Also assign on future connections
  try { e.gamepad?.on?.('connected', assignFirstPad); } catch { /* noop */ }
  };

  // Load EmulatorJS loader
  const EMULATORJS_VERSION = '4.2.3';
  const LOCAL_PATH = '/assets/emulatorjs/data/';
  const CDN_PATH = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data/`;
  try{
    const res = await fetch(`${LOCAL_PATH}loader.js`);
    const type = res.headers.get('content-type') || '';
    if (!res.ok || !type.includes('javascript')) throw new Error('Invalid local loader.js');
    w.EJS_pathtodata = LOCAL_PATH;
    const js = await res.text();
    const script = document.createElement('script'); script.textContent = js; document.body.appendChild(script);
  }catch{
    console.warn('Local EmulatorJS failed, falling back to CDN');
    w.EJS_pathtodata = CDN_PATH;
    const script = document.createElement('script'); script.src = `${CDN_PATH}loader.js`; document.body.appendChild(script);
  }

  // Hide the hint after a short delay
  setTimeout(() => { showHint.value = false; }, 3500);
}

let detachKey: (() => void) | null = null;
let detachPad: (() => void) | null = null;
onMounted(async () => {
  await boot();
  detachKey = attachKeyboardExit();
  detachPad = attachGamepadExit();
});
onUnmounted(() => {
  try{ (window as any).EJS_emulator?.callEvent?.('exit'); }catch{ /* noop */ }
  detachKey?.();
  detachPad?.();
});
</script>

<style>
#game { width: 100%; height: 100%; }
/* Hide the EmulatorJS in-UI exit button */
#game .ejs_menu_bar .ejs_menu_button:nth-child(-1) { display: none; }
</style>
