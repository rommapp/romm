// Helpers for managing custom EmulatorJS shaders and directory creation in Emscripten FS.

export interface ShaderFsLike {
  mkdir(path: string): void;
}

declare global {
  interface Window {
    EJS_shaders?: Record<string, string>;
  }
}

/** Ensures Emscripten virtual filesystem directories exist for nested shaders under /shader. */
export function ensureShaderDirectories(
  fs: ShaderFsLike | undefined | null,
  shaderPaths: readonly string[],
): void {
  if (!fs?.mkdir) return;
  try {
    fs.mkdir("/shader");
  } catch {
    // Root shader directory may already exist.
  }
  for (const path of shaderPaths) {
    const segments = path.split("/").slice(0, -1);
    let current = "/shader";
    for (const segment of segments) {
      if (!segment || segment === ".") continue;
      current += `/${segment}`;
      try {
        fs.mkdir(current);
      } catch {
        // Parent or directory may already exist.
      }
    }
  }
}

/** Hooks Module assignment and GameManager.initShaders to ensure /shader subdirectories exist. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function patchEmulatorJSShadersFs(emulator?: any): void {
  if (!emulator) {
    if (typeof window !== "undefined") {
      let current = window.EJS_emulator;
      const desc = Object.getOwnPropertyDescriptor(window, "EJS_emulator");
      Object.defineProperty(window, "EJS_emulator", {
        configurable: true,
        enumerable: true,
        get: () => (desc?.get ? desc.get() : current),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        set: (value: any) => {
          current = value;
          if (desc?.set) desc.set.call(window, value);
          if (value) patchEmulatorJSShadersFs(value);
        },
      });
      if (current) patchEmulatorJSShadersFs(current);
    }
    return;
  }

  let currentModule = emulator.Module;
  const initialShaders =
    emulator.config?.shaders || emulator.shaders || window.EJS_shaders;
  if (currentModule?.FS && initialShaders) {
    ensureShaderDirectories(currentModule.FS, Object.keys(initialShaders));
  }

  Object.defineProperty(emulator, "Module", {
    configurable: true,
    enumerable: true,
    get: () => currentModule,
    set(mod: { FS?: ShaderFsLike } | undefined) {
      currentModule = mod;
      const shaders =
        emulator.config?.shaders || emulator.shaders || window.EJS_shaders;
      if (mod?.FS && shaders) {
        ensureShaderDirectories(mod.FS, Object.keys(shaders));
      }
    },
  });

  const gameManager = emulator.gameManager;
  if (gameManager) {
    const originalInitShaders = gameManager.initShaders;
    gameManager.initShaders = function (this: unknown, ...args: unknown[]) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const gm = this as any;
      const shaders =
        gm?.EJS?.config?.shaders || gm?.EJS?.shaders || window.EJS_shaders;
      if (gm?.FS && shaders) {
        ensureShaderDirectories(gm.FS, Object.keys(shaders));
      }
      return originalInitShaders
        ? originalInitShaders.apply(this, args)
        : undefined;
    };
  }
}

/** Sets EmulatorJS custom shaders on the global window. */
export function setEmulatorJSShaders(
  shaders?: Record<string, string>,
): void {
  window.EJS_shaders = shaders || {};
}

/** Cleans up EmulatorJS custom shaders from the global window. */
export function clearEmulatorJSShaders(): void {
  window.EJS_shaders = {};
}
