import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearEmulatorJSShaders,
  ensureShaderDirectories,
  patchEmulatorJSShadersFs,
  setEmulatorJSShaders,
} from "./playerShaders";

function createStrictFs() {
  const directories = new Set<string>(["/"]);
  const writtenFiles = new Map<string, string | Uint8Array>();

  return {
    directories,
    writtenFiles,
    mkdir(path: string) {
      const normalized = path.replace(/\/+$/, "") || "/";
      const lastSlash = normalized.lastIndexOf("/");
      const parent = lastSlash === 0 ? "/" : normalized.slice(0, lastSlash);
      if (!directories.has(parent)) {
        throw new Error("ENOENT: parent directory does not exist");
      }
      if (directories.has(normalized)) {
        throw new Error("EEXIST: directory already exists");
      }
      directories.add(normalized);
    },
    writeFile(path: string, data: string | Uint8Array) {
      const normalized = path.replace(/\/+$/, "");
      const lastSlash = normalized.lastIndexOf("/");
      const parent = lastSlash === 0 ? "/" : normalized.slice(0, lastSlash);
      if (!directories.has(parent)) {
        throw new Error("ENOENT: parent directory does not exist");
      }
      writtenFiles.set(normalized, data);
    },
  };
}

describe("playerShaders", () => {
  afterEach(() => {
    clearEmulatorJSShaders();
  });

  describe("setEmulatorJSShaders / clearEmulatorJSShaders", () => {
    it("sets window.EJS_shaders to provided shaders dictionary", () => {
      const shaders = {
        "custom-crt.glslp": "#reference shader",
        "shaders/pass1.glsl": "void main() {}",
      };
      setEmulatorJSShaders(shaders);
      expect(window.EJS_shaders).toEqual(shaders);
    });

    it("defaults to empty object when shaders is undefined", () => {
      setEmulatorJSShaders(undefined);
      expect(window.EJS_shaders).toEqual({});
    });

    it("clears window.EJS_shaders back to empty object", () => {
      setEmulatorJSShaders({ "test.glslp": "test content" });
      clearEmulatorJSShaders();
      expect(window.EJS_shaders).toEqual({});
    });
  });

  describe("ensureShaderDirectories", () => {
    it("creates /shader and nested subdirectories in Emscripten FS", () => {
      const createdDirs: string[] = [];
      const mockFs = {
        mkdir: vi.fn((dir: string) => {
          createdDirs.push(dir);
        }),
      };

      ensureShaderDirectories(mockFs, [
        "flat.glslp",
        "presets/crt/crt-geom.glslp",
        "presets/crt/sub/pass1.glsl",
      ]);

      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/presets");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/presets/crt");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/presets/crt/sub");
    });

    it("swallows EEXIST error when directory already exists", () => {
      const mockFs = {
        mkdir: vi.fn((dir: string) => {
          if (dir === "/shader") throw new Error("File exists (EEXIST)");
        }),
      };

      expect(() => {
        ensureShaderDirectories(mockFs, ["flat.glslp"]);
      }).not.toThrow();
    });

    it("handles missing fs safely", () => {
      expect(() => {
        ensureShaderDirectories(undefined, ["flat.glslp"]);
      }).not.toThrow();
    });
  });

  describe("patchEmulatorJSShadersFs", () => {
    it("hooks gameManager.initShaders and calls ensureShaderDirectories", () => {
      const mockFs = { mkdir: vi.fn() };
      const originalInitShaders = vi.fn(function () {
        return "initialized";
      });

      const mockEmulator = {
        gameManager: {
          FS: mockFs,
          EJS: {
            shaders: {
              "sub/nested.glsl": "void main() {}",
            },
          },
          initShaders: originalInitShaders,
        },
      };

      patchEmulatorJSShadersFs(mockEmulator);

      const result = mockEmulator.gameManager.initShaders();
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/sub");
      expect(originalInitShaders).toHaveBeenCalled();
      expect(result).toBe("initialized");
    });

    it("hooks gameManager.initShaders with shaders from EJS.config.shaders", () => {
      const mockFs = { mkdir: vi.fn() };
      const originalInitShaders = vi.fn(function () {
        return "initialized";
      });

      const mockEmulator = {
        gameManager: {
          FS: mockFs,
          EJS: {
            config: {
              shaders: {
                "config_sub/nested.glsl": "void main() {}",
              },
            },
          },
          initShaders: originalInitShaders,
        },
      };

      patchEmulatorJSShadersFs(mockEmulator);

      const result = mockEmulator.gameManager.initShaders();
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/config_sub");
      expect(originalInitShaders).toHaveBeenCalled();
      expect(result).toBe("initialized");
    });

    it("hooks gameManager.initShaders falling back to window.EJS_shaders", () => {
      const mockFs = { mkdir: vi.fn() };
      const originalInitShaders = vi.fn(function () {
        return "initialized";
      });
      window.EJS_shaders = {
        "global_sub/screen.glsl": "void main() {}",
      };

      const mockEmulator = {
        gameManager: {
          FS: mockFs,
          EJS: {},
          initShaders: originalInitShaders,
        },
      };

      patchEmulatorJSShadersFs(mockEmulator);

      mockEmulator.gameManager.initShaders();
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/global_sub");
      window.EJS_shaders = {};
    });

    it("does nothing when emulator is null or undefined", () => {
      expect(() => patchEmulatorJSShadersFs(null)).not.toThrow();
    });

    it("intercepts Module assignment when gameManager is not yet created", () => {
      const mockFs = { mkdir: vi.fn() };
      const mockEmulator: {
        Module?: { FS: typeof mockFs };
        shaders?: Record<string, string>;
        gameManager?: unknown;
      } = {
        shaders: {
          "custom/arcade.glsl": "void main() {}",
        },
      };

      patchEmulatorJSShadersFs(mockEmulator);

      mockEmulator.Module = { FS: mockFs };

      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/custom");
    });

    it("falls back to window.EJS_shaders when emulator.shaders is unset", () => {
      const mockFs = { mkdir: vi.fn() };
      window.EJS_shaders = {
        "fallback/crt.glsl": "void main() {}",
      };
      const mockEmulator: {
        Module?: { FS: typeof mockFs };
        shaders?: Record<string, string>;
      } = {};

      patchEmulatorJSShadersFs(mockEmulator);
      mockEmulator.Module = { FS: mockFs };

      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/fallback");
      window.EJS_shaders = {};
    });

    it("hooks window.EJS_emulator when called without arguments", () => {
      const mockFs = { mkdir: vi.fn() };
      const shaders = { "dynamic/shader.glsl": "void main() {}" };
      window.EJS_shaders = shaders;

      patchEmulatorJSShadersFs();

      const emulatorInstance = {
        shaders,
        Module: undefined as { FS: typeof mockFs } | undefined,
      };

      window.EJS_emulator = emulatorInstance;
      emulatorInstance.Module = { FS: mockFs };

      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader");
      expect(mockFs.mkdir).toHaveBeenCalledWith("/shader/dynamic");
      delete (window as { EJS_emulator?: unknown }).EJS_emulator;
      window.EJS_shaders = {};
    });

    it("strict filesystem throws ENOENT when writing to uncreated directories", () => {
      const strictFs = createStrictFs();
      expect(() => {
        strictFs.writeFile("/shader/presets/crt/custom.glslp", "shader content");
      }).toThrow("ENOENT: parent directory does not exist");
    });

    it("allows initShaders to write nested files on strict filesystem following full runtime sequence", () => {
      const strictFs = createStrictFs();
      const shaders = {
        "presets/crt/custom.glslp": "#reference custom preset",
        "presets/crt/passes/pass1.glsl": "void main() {}",
      };

      const mockEmulator = {
        shaders,
        Module: undefined as { FS: typeof strictFs } | undefined,
        gameManager: {
          FS: strictFs,
          EJS: { shaders },
          initShaders: function () {
            for (const [relPath, content] of Object.entries(shaders)) {
              strictFs.writeFile(`/shader/${relPath}`, content);
            }
          },
        },
      };

      patchEmulatorJSShadersFs(mockEmulator);

      mockEmulator.Module = { FS: strictFs };

      expect(() => {
        mockEmulator.gameManager.initShaders();
      }).not.toThrow();

      expect(strictFs.writtenFiles.get("/shader/presets/crt/custom.glslp")).toBe(
        "#reference custom preset",
      );
      expect(
        strictFs.writtenFiles.get("/shader/presets/crt/passes/pass1.glsl"),
      ).toBe("void main() {}");
    });
  });
});
