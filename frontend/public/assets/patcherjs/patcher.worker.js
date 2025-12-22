// Web Worker for ROM patching
const PATCHER_BASE_PATH = "/assets/patcherjs";
const CORE_SCRIPTS = [
  `${PATCHER_BASE_PATH}/modules/HashCalculator.js`,
  `${PATCHER_BASE_PATH}/modules/BinFile.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ips.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ups.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.aps_n64.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.aps_gba.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.bps.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.rup.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ppf.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.bdf.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.pmsr.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.vcdiff.js`,
  `${PATCHER_BASE_PATH}/RomPatcher.js`,
];

// Load all patcher scripts
let scriptsLoaded = false;

async function loadScripts() {
  if (scriptsLoaded) return;

  try {
    for (const script of CORE_SCRIPTS) {
      importScripts(script);
    }
    scriptsLoaded = true;
    return true;
  } catch (error) {
    throw new Error(`Failed to load patcher scripts: ${error.message}`);
  }
}

// Handle messages from main thread
self.addEventListener("message", async (e) => {
  const { type, romData, patchData, romFileName, patchFileName } = e.data;

  if (type === "PATCH") {
    try {
      // Load scripts if not already loaded
      self.postMessage({
        type: "STATUS",
        message: "Loading patcher libraries...",
      });
      await loadScripts();

      // Extract patch name without extension for custom suffix
      const patchNameWithoutExt = patchFileName.replace(/\.[^.]+$/, "");

      // Try to create BinFile from Uint8Array
      self.postMessage({ type: "STATUS", message: "Reading ROM file..." });
      const romUint8 = new Uint8Array(romData);

      const romBin = await new Promise((resolve, reject) => {
        try {
          new BinFile(romUint8, (bf) => {
            if (bf) {
              bf.fileName = romFileName;
              resolve(bf);
            } else {
              reject(new Error("Failed to create ROM BinFile"));
            }
          });
        } catch (err) {
          reject(err);
        }
      });

      self.postMessage({ type: "STATUS", message: "Reading patch file..." });
      const patchUint8 = new Uint8Array(patchData);

      const patchBin = await new Promise((resolve, reject) => {
        try {
          new BinFile(patchUint8, (bf) => {
            if (bf) {
              bf.fileName = patchFileName;
              resolve(bf);
            } else {
              reject(new Error("Failed to create patch BinFile"));
            }
          });
        } catch (err) {
          reject(err);
        }
      });

      // Parse patch
      self.postMessage({ type: "STATUS", message: "Parsing patch format..." });
      const patch = RomPatcher.parsePatchFile(patchBin);
      if (!patch) {
        throw new Error("Unsupported or invalid patch format.");
      }

      // Apply patch
      self.postMessage({
        type: "STATUS",
        message: "Applying patch (this may take a moment)...",
      });
      const patched = RomPatcher.applyPatch(romBin, patch, {
        requireValidation: false,
        fixChecksum: false,
        outputSuffix: false, // Don't add default suffix
      });

      // Extract the patched binary data
      const patchedData = patched._u8array || patched.u8array || patched.data;
      if (!patchedData) {
        throw new Error("Failed to extract patched ROM data");
      }

      // Create custom filename with patch name
      const romBaseName = romFileName.replace(/\.[^.]+$/, "");
      const romExtension = romFileName.match(/\.[^.]+$/)?.[0] || "";
      const customFileName = `${romBaseName} (patched-${patchNameWithoutExt})${romExtension}`;

      // Send back the result
      self.postMessage(
        {
          type: "SUCCESS",
          patchedData: patchedData.buffer,
          fileName: customFileName,
        },
        [patchedData.buffer],
      ); // Transfer ownership of ArrayBuffer
    } catch (error) {
      self.postMessage({
        type: "ERROR",
        error: error.message || String(error),
      });
    }
  }
});
