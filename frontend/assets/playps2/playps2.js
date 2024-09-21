window.PlayPS2 = (() => {
  var _scriptDir =
    typeof document !== "undefined" && document.currentScript
      ? document.currentScript.src
      : undefined;

  return function (moduleArg = {}) {
    function GROWABLE_HEAP_I8() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAP8;
    }
    function GROWABLE_HEAP_U8() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAPU8;
    }
    function GROWABLE_HEAP_I16() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAP16;
    }
    function GROWABLE_HEAP_U16() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAPU16;
    }
    function GROWABLE_HEAP_I32() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAP32;
    }
    function GROWABLE_HEAP_U32() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAPU32;
    }
    function GROWABLE_HEAP_F32() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAPF32;
    }
    function GROWABLE_HEAP_F64() {
      if (wasmMemory.buffer != HEAP8.buffer) {
        updateMemoryViews();
      }
      return HEAPF64;
    }
    var Module = moduleArg;
    var readyPromiseResolve, readyPromiseReject;
    Module["ready"] = new Promise((resolve, reject) => {
      readyPromiseResolve = resolve;
      readyPromiseReject = reject;
    });
    var moduleOverrides = Object.assign({}, Module);
    var arguments_ = [];
    var thisProgram = "./this.program";
    var quit_ = (status, toThrow) => {
      throw toThrow;
    };
    var ENVIRONMENT_IS_WEB = typeof window == "object";
    var ENVIRONMENT_IS_WORKER = typeof importScripts == "function";
    var ENVIRONMENT_IS_NODE =
      typeof process == "object" &&
      typeof process.versions == "object" &&
      typeof process.versions.node == "string";
    var ENVIRONMENT_IS_PTHREAD = Module["ENVIRONMENT_IS_PTHREAD"] || false;
    var scriptDirectory = "";
    function locateFile(path) {
      if (Module["locateFile"]) {
        return Module["locateFile"](path, scriptDirectory);
      }
      return scriptDirectory + path;
    }
    var read_, readAsync, readBinary;
    if (ENVIRONMENT_IS_WEB || ENVIRONMENT_IS_WORKER) {
      if (ENVIRONMENT_IS_WORKER) {
        scriptDirectory = self.location.href;
      } else if (typeof document != "undefined" && document.currentScript) {
        scriptDirectory = document.currentScript.src;
      }
      if (_scriptDir) {
        scriptDirectory = _scriptDir;
      }
      if (scriptDirectory.indexOf("blob:") !== 0) {
        scriptDirectory = scriptDirectory.substr(
          0,
          scriptDirectory.replace(/[?#].*/, "").lastIndexOf("/") + 1,
        );
      } else {
        scriptDirectory = "";
      }
      {
        read_ = (url) => {
          var xhr = new XMLHttpRequest();
          xhr.open("GET", url, false);
          xhr.send(null);
          return xhr.responseText;
        };
        if (ENVIRONMENT_IS_WORKER) {
          readBinary = (url) => {
            var xhr = new XMLHttpRequest();
            xhr.open("GET", url, false);
            xhr.responseType = "arraybuffer";
            xhr.send(null);
            return new Uint8Array(xhr.response);
          };
        }
        readAsync = (url, onload, onerror) => {
          var xhr = new XMLHttpRequest();
          xhr.open("GET", url, true);
          xhr.responseType = "arraybuffer";
          xhr.onload = () => {
            if (xhr.status == 200 || (xhr.status == 0 && xhr.response)) {
              onload(xhr.response);
              return;
            }
            onerror();
          };
          xhr.onerror = onerror;
          xhr.send(null);
        };
      }
    } else {
    }
    var out = Module["print"] || console.log.bind(console);
    var err = Module["printErr"] || console.error.bind(console);
    Object.assign(Module, moduleOverrides);
    moduleOverrides = null;
    if (Module["arguments"]) arguments_ = Module["arguments"];
    if (Module["thisProgram"]) thisProgram = Module["thisProgram"];
    if (Module["quit"]) quit_ = Module["quit"];
    var wasmBinary;
    if (Module["wasmBinary"]) wasmBinary = Module["wasmBinary"];
    if (typeof WebAssembly != "object") {
      abort("no native wasm support detected");
    }
    var wasmMemory;
    var wasmModule;
    var ABORT = false;
    var EXITSTATUS;
    function assert(condition, text) {
      if (!condition) {
        abort(text);
      }
    }
    var HEAP8,
      HEAPU8,
      HEAP16,
      HEAPU16,
      HEAP32,
      HEAPU32,
      HEAPF32,
      HEAP64,
      HEAPU64,
      HEAPF64;
    function updateMemoryViews() {
      var b = wasmMemory.buffer;
      Module["HEAP8"] = HEAP8 = new Int8Array(b);
      Module["HEAP16"] = HEAP16 = new Int16Array(b);
      Module["HEAPU8"] = HEAPU8 = new Uint8Array(b);
      Module["HEAPU16"] = HEAPU16 = new Uint16Array(b);
      Module["HEAP32"] = HEAP32 = new Int32Array(b);
      Module["HEAPU32"] = HEAPU32 = new Uint32Array(b);
      Module["HEAPF32"] = HEAPF32 = new Float32Array(b);
      Module["HEAPF64"] = HEAPF64 = new Float64Array(b);
      Module["HEAP64"] = HEAP64 = new BigInt64Array(b);
      Module["HEAPU64"] = HEAPU64 = new BigUint64Array(b);
    }
    var INITIAL_MEMORY = Module["INITIAL_MEMORY"] || 16777216;
    if (ENVIRONMENT_IS_PTHREAD) {
      wasmMemory = Module["wasmMemory"];
    } else {
      if (Module["wasmMemory"]) {
        wasmMemory = Module["wasmMemory"];
      } else {
        wasmMemory = new WebAssembly.Memory({
          initial: INITIAL_MEMORY / 65536,
          maximum: 2147483648 / 65536,
          shared: true,
        });
        if (!(wasmMemory.buffer instanceof SharedArrayBuffer)) {
          err(
            "requested a shared WebAssembly.Memory but the returned buffer is not a SharedArrayBuffer, indicating that while the browser has SharedArrayBuffer it does not have WebAssembly threads support - you may need to set a flag",
          );
          if (ENVIRONMENT_IS_NODE) {
            err(
              "(on node you may need: --experimental-wasm-threads --experimental-wasm-bulk-memory and/or recent version)",
            );
          }
          throw Error("bad memory");
        }
      }
    }
    updateMemoryViews();
    INITIAL_MEMORY = wasmMemory.buffer.byteLength;
    var __ATPRERUN__ = [];
    var __ATINIT__ = [];
    var __ATMAIN__ = [];
    var __ATEXIT__ = [];
    var __ATPOSTRUN__ = [];
    var runtimeInitialized = false;
    function preRun() {
      if (Module["preRun"]) {
        if (typeof Module["preRun"] == "function")
          Module["preRun"] = [Module["preRun"]];
        while (Module["preRun"].length) {
          addOnPreRun(Module["preRun"].shift());
        }
      }
      callRuntimeCallbacks(__ATPRERUN__);
    }
    function initRuntime() {
      runtimeInitialized = true;
      if (ENVIRONMENT_IS_PTHREAD) return;
      if (!Module["noFSInit"] && !FS.init.initialized) FS.init();
      FS.ignorePermissions = false;
      TTY.init();
      callRuntimeCallbacks(__ATINIT__);
    }
    function preMain() {
      if (ENVIRONMENT_IS_PTHREAD) return;
      callRuntimeCallbacks(__ATMAIN__);
    }
    function postRun() {
      if (ENVIRONMENT_IS_PTHREAD) return;
      if (Module["postRun"]) {
        if (typeof Module["postRun"] == "function")
          Module["postRun"] = [Module["postRun"]];
        while (Module["postRun"].length) {
          addOnPostRun(Module["postRun"].shift());
        }
      }
      callRuntimeCallbacks(__ATPOSTRUN__);
    }
    function addOnPreRun(cb) {
      __ATPRERUN__.unshift(cb);
    }
    function addOnInit(cb) {
      __ATINIT__.unshift(cb);
    }
    function addOnPostRun(cb) {
      __ATPOSTRUN__.unshift(cb);
    }
    var runDependencies = 0;
    var runDependencyWatcher = null;
    var dependenciesFulfilled = null;
    function getUniqueRunDependency(id) {
      return id;
    }
    function addRunDependency(id) {
      runDependencies++;
      Module["monitorRunDependencies"]?.(runDependencies);
    }
    function removeRunDependency(id) {
      runDependencies--;
      Module["monitorRunDependencies"]?.(runDependencies);
      if (runDependencies == 0) {
        if (runDependencyWatcher !== null) {
          clearInterval(runDependencyWatcher);
          runDependencyWatcher = null;
        }
        if (dependenciesFulfilled) {
          var callback = dependenciesFulfilled;
          dependenciesFulfilled = null;
          callback();
        }
      }
    }
    function abort(what) {
      Module["onAbort"]?.(what);
      what = "Aborted(" + what + ")";
      err(what);
      ABORT = true;
      EXITSTATUS = 1;
      what += ". Build with -sASSERTIONS for more info.";
      var e = new WebAssembly.RuntimeError(what);
      readyPromiseReject(e);
      throw e;
    }
    var dataURIPrefix = "data:application/octet-stream;base64,";
    var isDataURI = (filename) => filename.startsWith(dataURIPrefix);
    var wasmBinaryFile;
    wasmBinaryFile = "playps2.wasm";
    if (!isDataURI(wasmBinaryFile)) {
      wasmBinaryFile = locateFile(wasmBinaryFile);
    }
    function getBinarySync(file) {
      if (file == wasmBinaryFile && wasmBinary) {
        return new Uint8Array(wasmBinary);
      }
      if (readBinary) {
        return readBinary(file);
      }
      throw "both async and sync fetching of the wasm failed";
    }
    function getBinaryPromise(binaryFile) {
      if (!wasmBinary && (ENVIRONMENT_IS_WEB || ENVIRONMENT_IS_WORKER)) {
        if (typeof fetch == "function") {
          return fetch(binaryFile, { credentials: "same-origin" })
            .then((response) => {
              if (!response["ok"]) {
                throw "failed to load wasm binary file at '" + binaryFile + "'";
              }
              return response["arrayBuffer"]();
            })
            .catch(() => getBinarySync(binaryFile));
        }
      }
      return Promise.resolve().then(() => getBinarySync(binaryFile));
    }
    function instantiateArrayBuffer(binaryFile, imports, receiver) {
      return getBinaryPromise(binaryFile)
        .then((binary) => WebAssembly.instantiate(binary, imports))
        .then((instance) => instance)
        .then(receiver, (reason) => {
          err(`failed to asynchronously prepare wasm: ${reason}`);
          abort(reason);
        });
    }
    function instantiateAsync(binary, binaryFile, imports, callback) {
      if (
        !binary &&
        typeof WebAssembly.instantiateStreaming == "function" &&
        !isDataURI(binaryFile) &&
        typeof fetch == "function"
      ) {
        return fetch(binaryFile, { credentials: "same-origin" }).then(
          (response) => {
            var result = WebAssembly.instantiateStreaming(response, imports);
            return result.then(callback, function (reason) {
              err(`wasm streaming compile failed: ${reason}`);
              err("falling back to ArrayBuffer instantiation");
              return instantiateArrayBuffer(binaryFile, imports, callback);
            });
          },
        );
      }
      return instantiateArrayBuffer(binaryFile, imports, callback);
    }
    function createWasm() {
      var info = { a: wasmImports };
      function receiveInstance(instance, module) {
        wasmExports = instance.exports;
        registerTLSInit(wasmExports["kd"]);
        wasmTable = wasmExports["Pc"];
        addOnInit(wasmExports["Oc"]);
        wasmModule = module;
        removeRunDependency("wasm-instantiate");
        return wasmExports;
      }
      addRunDependency("wasm-instantiate");
      function receiveInstantiationResult(result) {
        receiveInstance(result["instance"], result["module"]);
      }
      if (Module["instantiateWasm"]) {
        try {
          return Module["instantiateWasm"](info, receiveInstance);
        } catch (e) {
          err(`Module.instantiateWasm callback failed with error: ${e}`);
          readyPromiseReject(e);
        }
      }
      instantiateAsync(
        wasmBinary,
        wasmBinaryFile,
        info,
        receiveInstantiationResult,
      ).catch(readyPromiseReject);
      return {};
    }
    var ASM_CONSTS = {
      231788: () => Module.discImageDevice.getFileSize(),
      231834: () => Module.discImageDevice.getFileSize() / 4294967296,
      231893: ($0, $1, $2, $3) => {
        let posLow = $1 >>> 0;
        let posHigh = $2 >>> 0;
        let position = posLow + posHigh * 4294967296;
        Module.discImageDevice.read($0, position, $3);
      },
      232039: () => Module.discImageDevice.isDone(),
    };
    function RegisterExternFunction(functionName, functionSig) {
      let fctName = UTF8ToString(functionName);
      let fctSig = UTF8ToString(functionSig);
      let fct = Module[fctName];
      if (fct === undefined) {
        out(`Warning: Could not find function '${fctName}' (missing export?).`);
      }
      if (Module.codeGenImportTable === undefined) {
        out("Creating import table...");
        Module.codeGenImportTable = new WebAssembly.Table({
          element: "anyfunc",
          initial: 32,
        });
        Module.codeGenImportTableNextIndex = 0;
      }
      let wrappedFct = convertJsFunctionToWasm(fct, fctSig);
      let fctId = Module.codeGenImportTableNextIndex++;
      Module.codeGenImportTable.set(fctId, wrappedFct);
      out(`Registered function '${fctName}(${fctSig})' = > id = ${fctId}.`);
      return fctId;
    }
    function WasmCreateFunction(moduleHandle) {
      let module = Emval.toValue(moduleHandle);
      let moduleInstance = new WebAssembly.Instance(module, {
        env: { memory: wasmMemory, fctTable: Module.codeGenImportTable },
      });
      let fct = moduleInstance.exports.codeGenFunc;
      let fctId = addFunction(fct, "vi");
      return fctId;
    }
    function WasmDeleteFunction(fctId) {
      removeFunction(fctId);
    }
    function WasmCreateModule(code, size) {
      let moduleBytes = GROWABLE_HEAP_I8().subarray(code, code + size);
      let module = new WebAssembly.Module(moduleBytes);
      return Emval.toHandle(module);
    }
    function ExitStatus(status) {
      this.name = "ExitStatus";
      this.message = `Program terminated with exit(${status})`;
      this.status = status;
    }
    var terminateWorker = (worker) => {
      worker.terminate();
      worker.onmessage = (e) => {};
    };
    var killThread = (pthread_ptr) => {
      var worker = PThread.pthreads[pthread_ptr];
      delete PThread.pthreads[pthread_ptr];
      terminateWorker(worker);
      __emscripten_thread_free_data(pthread_ptr);
      PThread.runningWorkers.splice(PThread.runningWorkers.indexOf(worker), 1);
      worker.pthread_ptr = 0;
    };
    var cancelThread = (pthread_ptr) => {
      var worker = PThread.pthreads[pthread_ptr];
      worker.postMessage({ cmd: "cancel" });
    };
    var cleanupThread = (pthread_ptr) => {
      var worker = PThread.pthreads[pthread_ptr];
      PThread.returnWorkerToPool(worker);
    };
    var spawnThread = (threadParams) => {
      var worker = PThread.getNewWorker();
      if (!worker) {
        return 6;
      }
      PThread.runningWorkers.push(worker);
      PThread.pthreads[threadParams.pthread_ptr] = worker;
      worker.pthread_ptr = threadParams.pthread_ptr;
      var msg = {
        cmd: "run",
        start_routine: threadParams.startRoutine,
        arg: threadParams.arg,
        pthread_ptr: threadParams.pthread_ptr,
      };
      worker.postMessage(msg, threadParams.transferList);
      return 0;
    };
    var runtimeKeepaliveCounter = 0;
    var keepRuntimeAlive = () => noExitRuntime || runtimeKeepaliveCounter > 0;
    var PATH = {
      isAbs: (path) => path.charAt(0) === "/",
      splitPath: (filename) => {
        var splitPathRe =
          /^(\/?|)([\s\S]*?)((?:\.{1,2}|[^\/]+?|)(\.[^.\/]*|))(?:[\/]*)$/;
        return splitPathRe.exec(filename).slice(1);
      },
      normalizeArray: (parts, allowAboveRoot) => {
        var up = 0;
        for (var i = parts.length - 1; i >= 0; i--) {
          var last = parts[i];
          if (last === ".") {
            parts.splice(i, 1);
          } else if (last === "..") {
            parts.splice(i, 1);
            up++;
          } else if (up) {
            parts.splice(i, 1);
            up--;
          }
        }
        if (allowAboveRoot) {
          for (; up; up--) {
            parts.unshift("..");
          }
        }
        return parts;
      },
      normalize: (path) => {
        var isAbsolute = PATH.isAbs(path),
          trailingSlash = path.substr(-1) === "/";
        path = PATH.normalizeArray(
          path.split("/").filter((p) => !!p),
          !isAbsolute,
        ).join("/");
        if (!path && !isAbsolute) {
          path = ".";
        }
        if (path && trailingSlash) {
          path += "/";
        }
        return (isAbsolute ? "/" : "") + path;
      },
      dirname: (path) => {
        var result = PATH.splitPath(path),
          root = result[0],
          dir = result[1];
        if (!root && !dir) {
          return ".";
        }
        if (dir) {
          dir = dir.substr(0, dir.length - 1);
        }
        return root + dir;
      },
      basename: (path) => {
        if (path === "/") return "/";
        path = PATH.normalize(path);
        path = path.replace(/\/$/, "");
        var lastSlash = path.lastIndexOf("/");
        if (lastSlash === -1) return path;
        return path.substr(lastSlash + 1);
      },
      join: function () {
        var paths = Array.prototype.slice.call(arguments);
        return PATH.normalize(paths.join("/"));
      },
      join2: (l, r) => PATH.normalize(l + "/" + r),
    };
    var initRandomFill = () => {
      if (
        typeof crypto == "object" &&
        typeof crypto["getRandomValues"] == "function"
      ) {
        return (view) => (
          view.set(crypto.getRandomValues(new Uint8Array(view.byteLength))),
          view
        );
      } else abort("initRandomDevice");
    };
    var randomFill = (view) => (randomFill = initRandomFill())(view);
    var PATH_FS = {
      resolve: function () {
        var resolvedPath = "",
          resolvedAbsolute = false;
        for (var i = arguments.length - 1; i >= -1 && !resolvedAbsolute; i--) {
          var path = i >= 0 ? arguments[i] : FS.cwd();
          if (typeof path != "string") {
            throw new TypeError("Arguments to path.resolve must be strings");
          } else if (!path) {
            return "";
          }
          resolvedPath = path + "/" + resolvedPath;
          resolvedAbsolute = PATH.isAbs(path);
        }
        resolvedPath = PATH.normalizeArray(
          resolvedPath.split("/").filter((p) => !!p),
          !resolvedAbsolute,
        ).join("/");
        return (resolvedAbsolute ? "/" : "") + resolvedPath || ".";
      },
      relative: (from, to) => {
        from = PATH_FS.resolve(from).substr(1);
        to = PATH_FS.resolve(to).substr(1);
        function trim(arr) {
          var start = 0;
          for (; start < arr.length; start++) {
            if (arr[start] !== "") break;
          }
          var end = arr.length - 1;
          for (; end >= 0; end--) {
            if (arr[end] !== "") break;
          }
          if (start > end) return [];
          return arr.slice(start, end - start + 1);
        }
        var fromParts = trim(from.split("/"));
        var toParts = trim(to.split("/"));
        var length = Math.min(fromParts.length, toParts.length);
        var samePartsLength = length;
        for (var i = 0; i < length; i++) {
          if (fromParts[i] !== toParts[i]) {
            samePartsLength = i;
            break;
          }
        }
        var outputParts = [];
        for (var i = samePartsLength; i < fromParts.length; i++) {
          outputParts.push("..");
        }
        outputParts = outputParts.concat(toParts.slice(samePartsLength));
        return outputParts.join("/");
      },
    };
    var UTF8Decoder =
      typeof TextDecoder != "undefined" ? new TextDecoder("utf8") : undefined;
    var UTF8ArrayToString = (heapOrArray, idx, maxBytesToRead) => {
      var endIdx = idx + maxBytesToRead;
      var endPtr = idx;
      while (heapOrArray[endPtr] && !(endPtr >= endIdx)) ++endPtr;
      if (endPtr - idx > 16 && heapOrArray.buffer && UTF8Decoder) {
        return UTF8Decoder.decode(
          heapOrArray.buffer instanceof SharedArrayBuffer
            ? heapOrArray.slice(idx, endPtr)
            : heapOrArray.subarray(idx, endPtr),
        );
      }
      var str = "";
      while (idx < endPtr) {
        var u0 = heapOrArray[idx++];
        if (!(u0 & 128)) {
          str += String.fromCharCode(u0);
          continue;
        }
        var u1 = heapOrArray[idx++] & 63;
        if ((u0 & 224) == 192) {
          str += String.fromCharCode(((u0 & 31) << 6) | u1);
          continue;
        }
        var u2 = heapOrArray[idx++] & 63;
        if ((u0 & 240) == 224) {
          u0 = ((u0 & 15) << 12) | (u1 << 6) | u2;
        } else {
          u0 =
            ((u0 & 7) << 18) |
            (u1 << 12) |
            (u2 << 6) |
            (heapOrArray[idx++] & 63);
        }
        if (u0 < 65536) {
          str += String.fromCharCode(u0);
        } else {
          var ch = u0 - 65536;
          str += String.fromCharCode(55296 | (ch >> 10), 56320 | (ch & 1023));
        }
      }
      return str;
    };
    var FS_stdin_getChar_buffer = [];
    var lengthBytesUTF8 = (str) => {
      var len = 0;
      for (var i = 0; i < str.length; ++i) {
        var c = str.charCodeAt(i);
        if (c <= 127) {
          len++;
        } else if (c <= 2047) {
          len += 2;
        } else if (c >= 55296 && c <= 57343) {
          len += 4;
          ++i;
        } else {
          len += 3;
        }
      }
      return len;
    };
    var stringToUTF8Array = (str, heap, outIdx, maxBytesToWrite) => {
      if (!(maxBytesToWrite > 0)) return 0;
      var startIdx = outIdx;
      var endIdx = outIdx + maxBytesToWrite - 1;
      for (var i = 0; i < str.length; ++i) {
        var u = str.charCodeAt(i);
        if (u >= 55296 && u <= 57343) {
          var u1 = str.charCodeAt(++i);
          u = (65536 + ((u & 1023) << 10)) | (u1 & 1023);
        }
        if (u <= 127) {
          if (outIdx >= endIdx) break;
          heap[outIdx++] = u;
        } else if (u <= 2047) {
          if (outIdx + 1 >= endIdx) break;
          heap[outIdx++] = 192 | (u >> 6);
          heap[outIdx++] = 128 | (u & 63);
        } else if (u <= 65535) {
          if (outIdx + 2 >= endIdx) break;
          heap[outIdx++] = 224 | (u >> 12);
          heap[outIdx++] = 128 | ((u >> 6) & 63);
          heap[outIdx++] = 128 | (u & 63);
        } else {
          if (outIdx + 3 >= endIdx) break;
          heap[outIdx++] = 240 | (u >> 18);
          heap[outIdx++] = 128 | ((u >> 12) & 63);
          heap[outIdx++] = 128 | ((u >> 6) & 63);
          heap[outIdx++] = 128 | (u & 63);
        }
      }
      heap[outIdx] = 0;
      return outIdx - startIdx;
    };
    function intArrayFromString(stringy, dontAddNull, length) {
      var len = length > 0 ? length : lengthBytesUTF8(stringy) + 1;
      var u8array = new Array(len);
      var numBytesWritten = stringToUTF8Array(
        stringy,
        u8array,
        0,
        u8array.length,
      );
      if (dontAddNull) u8array.length = numBytesWritten;
      return u8array;
    }
    var FS_stdin_getChar = () => {
      if (!FS_stdin_getChar_buffer.length) {
        var result = null;
        if (
          typeof window != "undefined" &&
          typeof window.prompt == "function"
        ) {
          result = window.prompt("Input: ");
          if (result !== null) {
            result += "\n";
          }
        } else if (typeof readline == "function") {
          result = readline();
          if (result !== null) {
            result += "\n";
          }
        }
        if (!result) {
          return null;
        }
        FS_stdin_getChar_buffer = intArrayFromString(result, true);
      }
      return FS_stdin_getChar_buffer.shift();
    };
    var TTY = {
      ttys: [],
      init() {},
      shutdown() {},
      register(dev, ops) {
        TTY.ttys[dev] = { input: [], output: [], ops: ops };
        FS.registerDevice(dev, TTY.stream_ops);
      },
      stream_ops: {
        open(stream) {
          var tty = TTY.ttys[stream.node.rdev];
          if (!tty) {
            throw new FS.ErrnoError(43);
          }
          stream.tty = tty;
          stream.seekable = false;
        },
        close(stream) {
          stream.tty.ops.fsync(stream.tty);
        },
        fsync(stream) {
          stream.tty.ops.fsync(stream.tty);
        },
        read(stream, buffer, offset, length, pos) {
          if (!stream.tty || !stream.tty.ops.get_char) {
            throw new FS.ErrnoError(60);
          }
          var bytesRead = 0;
          for (var i = 0; i < length; i++) {
            var result;
            try {
              result = stream.tty.ops.get_char(stream.tty);
            } catch (e) {
              throw new FS.ErrnoError(29);
            }
            if (result === undefined && bytesRead === 0) {
              throw new FS.ErrnoError(6);
            }
            if (result === null || result === undefined) break;
            bytesRead++;
            buffer[offset + i] = result;
          }
          if (bytesRead) {
            stream.node.timestamp = Date.now();
          }
          return bytesRead;
        },
        write(stream, buffer, offset, length, pos) {
          if (!stream.tty || !stream.tty.ops.put_char) {
            throw new FS.ErrnoError(60);
          }
          try {
            for (var i = 0; i < length; i++) {
              stream.tty.ops.put_char(stream.tty, buffer[offset + i]);
            }
          } catch (e) {
            throw new FS.ErrnoError(29);
          }
          if (length) {
            stream.node.timestamp = Date.now();
          }
          return i;
        },
      },
      default_tty_ops: {
        get_char(tty) {
          return FS_stdin_getChar();
        },
        put_char(tty, val) {
          if (val === null || val === 10) {
            out(UTF8ArrayToString(tty.output, 0));
            tty.output = [];
          } else {
            if (val != 0) tty.output.push(val);
          }
        },
        fsync(tty) {
          if (tty.output && tty.output.length > 0) {
            out(UTF8ArrayToString(tty.output, 0));
            tty.output = [];
          }
        },
        ioctl_tcgets(tty) {
          return {
            c_iflag: 25856,
            c_oflag: 5,
            c_cflag: 191,
            c_lflag: 35387,
            c_cc: [
              3, 28, 127, 21, 4, 0, 1, 0, 17, 19, 26, 0, 18, 15, 23, 22, 0, 0,
              0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            ],
          };
        },
        ioctl_tcsets(tty, optional_actions, data) {
          return 0;
        },
        ioctl_tiocgwinsz(tty) {
          return [24, 80];
        },
      },
      default_tty1_ops: {
        put_char(tty, val) {
          if (val === null || val === 10) {
            err(UTF8ArrayToString(tty.output, 0));
            tty.output = [];
          } else {
            if (val != 0) tty.output.push(val);
          }
        },
        fsync(tty) {
          if (tty.output && tty.output.length > 0) {
            err(UTF8ArrayToString(tty.output, 0));
            tty.output = [];
          }
        },
      },
    };
    var mmapAlloc = (size) => {
      abort();
    };
    var MEMFS = {
      ops_table: null,
      mount(mount) {
        return MEMFS.createNode(null, "/", 16384 | 511, 0);
      },
      createNode(parent, name, mode, dev) {
        if (FS.isBlkdev(mode) || FS.isFIFO(mode)) {
          throw new FS.ErrnoError(63);
        }
        MEMFS.ops_table ||= {
          dir: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
              lookup: MEMFS.node_ops.lookup,
              mknod: MEMFS.node_ops.mknod,
              rename: MEMFS.node_ops.rename,
              unlink: MEMFS.node_ops.unlink,
              rmdir: MEMFS.node_ops.rmdir,
              readdir: MEMFS.node_ops.readdir,
              symlink: MEMFS.node_ops.symlink,
            },
            stream: { llseek: MEMFS.stream_ops.llseek },
          },
          file: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
            },
            stream: {
              llseek: MEMFS.stream_ops.llseek,
              read: MEMFS.stream_ops.read,
              write: MEMFS.stream_ops.write,
              allocate: MEMFS.stream_ops.allocate,
              mmap: MEMFS.stream_ops.mmap,
              msync: MEMFS.stream_ops.msync,
            },
          },
          link: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
              readlink: MEMFS.node_ops.readlink,
            },
            stream: {},
          },
          chrdev: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
            },
            stream: FS.chrdev_stream_ops,
          },
        };
        var node = FS.createNode(parent, name, mode, dev);
        if (FS.isDir(node.mode)) {
          node.node_ops = MEMFS.ops_table.dir.node;
          node.stream_ops = MEMFS.ops_table.dir.stream;
          node.contents = {};
        } else if (FS.isFile(node.mode)) {
          node.node_ops = MEMFS.ops_table.file.node;
          node.stream_ops = MEMFS.ops_table.file.stream;
          node.usedBytes = 0;
          node.contents = null;
        } else if (FS.isLink(node.mode)) {
          node.node_ops = MEMFS.ops_table.link.node;
          node.stream_ops = MEMFS.ops_table.link.stream;
        } else if (FS.isChrdev(node.mode)) {
          node.node_ops = MEMFS.ops_table.chrdev.node;
          node.stream_ops = MEMFS.ops_table.chrdev.stream;
        }
        node.timestamp = Date.now();
        if (parent) {
          parent.contents[name] = node;
          parent.timestamp = node.timestamp;
        }
        return node;
      },
      getFileDataAsTypedArray(node) {
        if (!node.contents) return new Uint8Array(0);
        if (node.contents.subarray)
          return node.contents.subarray(0, node.usedBytes);
        return new Uint8Array(node.contents);
      },
      expandFileStorage(node, newCapacity) {
        var prevCapacity = node.contents ? node.contents.length : 0;
        if (prevCapacity >= newCapacity) return;
        var CAPACITY_DOUBLING_MAX = 1024 * 1024;
        newCapacity = Math.max(
          newCapacity,
          (prevCapacity *
            (prevCapacity < CAPACITY_DOUBLING_MAX ? 2 : 1.125)) >>>
            0,
        );
        if (prevCapacity != 0) newCapacity = Math.max(newCapacity, 256);
        var oldContents = node.contents;
        node.contents = new Uint8Array(newCapacity);
        if (node.usedBytes > 0)
          node.contents.set(oldContents.subarray(0, node.usedBytes), 0);
      },
      resizeFileStorage(node, newSize) {
        if (node.usedBytes == newSize) return;
        if (newSize == 0) {
          node.contents = null;
          node.usedBytes = 0;
        } else {
          var oldContents = node.contents;
          node.contents = new Uint8Array(newSize);
          if (oldContents) {
            node.contents.set(
              oldContents.subarray(0, Math.min(newSize, node.usedBytes)),
            );
          }
          node.usedBytes = newSize;
        }
      },
      node_ops: {
        getattr(node) {
          var attr = {};
          attr.dev = FS.isChrdev(node.mode) ? node.id : 1;
          attr.ino = node.id;
          attr.mode = node.mode;
          attr.nlink = 1;
          attr.uid = 0;
          attr.gid = 0;
          attr.rdev = node.rdev;
          if (FS.isDir(node.mode)) {
            attr.size = 4096;
          } else if (FS.isFile(node.mode)) {
            attr.size = node.usedBytes;
          } else if (FS.isLink(node.mode)) {
            attr.size = node.link.length;
          } else {
            attr.size = 0;
          }
          attr.atime = new Date(node.timestamp);
          attr.mtime = new Date(node.timestamp);
          attr.ctime = new Date(node.timestamp);
          attr.blksize = 4096;
          attr.blocks = Math.ceil(attr.size / attr.blksize);
          return attr;
        },
        setattr(node, attr) {
          if (attr.mode !== undefined) {
            node.mode = attr.mode;
          }
          if (attr.timestamp !== undefined) {
            node.timestamp = attr.timestamp;
          }
          if (attr.size !== undefined) {
            MEMFS.resizeFileStorage(node, attr.size);
          }
        },
        lookup(parent, name) {
          throw FS.genericErrors[44];
        },
        mknod(parent, name, mode, dev) {
          return MEMFS.createNode(parent, name, mode, dev);
        },
        rename(old_node, new_dir, new_name) {
          if (FS.isDir(old_node.mode)) {
            var new_node;
            try {
              new_node = FS.lookupNode(new_dir, new_name);
            } catch (e) {}
            if (new_node) {
              for (var i in new_node.contents) {
                throw new FS.ErrnoError(55);
              }
            }
          }
          delete old_node.parent.contents[old_node.name];
          old_node.parent.timestamp = Date.now();
          old_node.name = new_name;
          new_dir.contents[new_name] = old_node;
          new_dir.timestamp = old_node.parent.timestamp;
          old_node.parent = new_dir;
        },
        unlink(parent, name) {
          delete parent.contents[name];
          parent.timestamp = Date.now();
        },
        rmdir(parent, name) {
          var node = FS.lookupNode(parent, name);
          for (var i in node.contents) {
            throw new FS.ErrnoError(55);
          }
          delete parent.contents[name];
          parent.timestamp = Date.now();
        },
        readdir(node) {
          var entries = [".", ".."];
          for (var key of Object.keys(node.contents)) {
            entries.push(key);
          }
          return entries;
        },
        symlink(parent, newname, oldpath) {
          var node = MEMFS.createNode(parent, newname, 511 | 40960, 0);
          node.link = oldpath;
          return node;
        },
        readlink(node) {
          if (!FS.isLink(node.mode)) {
            throw new FS.ErrnoError(28);
          }
          return node.link;
        },
      },
      stream_ops: {
        read(stream, buffer, offset, length, position) {
          var contents = stream.node.contents;
          if (position >= stream.node.usedBytes) return 0;
          var size = Math.min(stream.node.usedBytes - position, length);
          if (size > 8 && contents.subarray) {
            buffer.set(contents.subarray(position, position + size), offset);
          } else {
            for (var i = 0; i < size; i++)
              buffer[offset + i] = contents[position + i];
          }
          return size;
        },
        write(stream, buffer, offset, length, position, canOwn) {
          if (buffer.buffer === GROWABLE_HEAP_I8().buffer) {
            canOwn = false;
          }
          if (!length) return 0;
          var node = stream.node;
          node.timestamp = Date.now();
          if (buffer.subarray && (!node.contents || node.contents.subarray)) {
            if (canOwn) {
              node.contents = buffer.subarray(offset, offset + length);
              node.usedBytes = length;
              return length;
            } else if (node.usedBytes === 0 && position === 0) {
              node.contents = buffer.slice(offset, offset + length);
              node.usedBytes = length;
              return length;
            } else if (position + length <= node.usedBytes) {
              node.contents.set(
                buffer.subarray(offset, offset + length),
                position,
              );
              return length;
            }
          }
          MEMFS.expandFileStorage(node, position + length);
          if (node.contents.subarray && buffer.subarray) {
            node.contents.set(
              buffer.subarray(offset, offset + length),
              position,
            );
          } else {
            for (var i = 0; i < length; i++) {
              node.contents[position + i] = buffer[offset + i];
            }
          }
          node.usedBytes = Math.max(node.usedBytes, position + length);
          return length;
        },
        llseek(stream, offset, whence) {
          var position = offset;
          if (whence === 1) {
            position += stream.position;
          } else if (whence === 2) {
            if (FS.isFile(stream.node.mode)) {
              position += stream.node.usedBytes;
            }
          }
          if (position < 0) {
            throw new FS.ErrnoError(28);
          }
          return position;
        },
        allocate(stream, offset, length) {
          MEMFS.expandFileStorage(stream.node, offset + length);
          stream.node.usedBytes = Math.max(
            stream.node.usedBytes,
            offset + length,
          );
        },
        mmap(stream, length, position, prot, flags) {
          if (!FS.isFile(stream.node.mode)) {
            throw new FS.ErrnoError(43);
          }
          var ptr;
          var allocated;
          var contents = stream.node.contents;
          if (!(flags & 2) && contents.buffer === GROWABLE_HEAP_I8().buffer) {
            allocated = false;
            ptr = contents.byteOffset;
          } else {
            if (position > 0 || position + length < contents.length) {
              if (contents.subarray) {
                contents = contents.subarray(position, position + length);
              } else {
                contents = Array.prototype.slice.call(
                  contents,
                  position,
                  position + length,
                );
              }
            }
            allocated = true;
            ptr = mmapAlloc(length);
            if (!ptr) {
              throw new FS.ErrnoError(48);
            }
            GROWABLE_HEAP_I8().set(contents, ptr);
          }
          return { ptr: ptr, allocated: allocated };
        },
        msync(stream, buffer, offset, length, mmapFlags) {
          MEMFS.stream_ops.write(stream, buffer, 0, length, offset, false);
          return 0;
        },
      },
    };
    var asyncLoad = (url, onload, onerror, noRunDep) => {
      var dep = !noRunDep ? getUniqueRunDependency(`al ${url}`) : "";
      readAsync(
        url,
        (arrayBuffer) => {
          assert(
            arrayBuffer,
            `Loading data file "${url}" failed (no arrayBuffer).`,
          );
          onload(new Uint8Array(arrayBuffer));
          if (dep) removeRunDependency(dep);
        },
        (event) => {
          if (onerror) {
            onerror();
          } else {
            throw `Loading data file "${url}" failed.`;
          }
        },
      );
      if (dep) addRunDependency(dep);
    };
    var FS_createDataFile = (
      parent,
      name,
      fileData,
      canRead,
      canWrite,
      canOwn,
    ) => {
      FS.createDataFile(parent, name, fileData, canRead, canWrite, canOwn);
    };
    var preloadPlugins = Module["preloadPlugins"] || [];
    var FS_handledByPreloadPlugin = (byteArray, fullname, finish, onerror) => {
      if (typeof Browser != "undefined") Browser.init();
      var handled = false;
      preloadPlugins.forEach((plugin) => {
        if (handled) return;
        if (plugin["canHandle"](fullname)) {
          plugin["handle"](byteArray, fullname, finish, onerror);
          handled = true;
        }
      });
      return handled;
    };
    var FS_createPreloadedFile = (
      parent,
      name,
      url,
      canRead,
      canWrite,
      onload,
      onerror,
      dontCreateFile,
      canOwn,
      preFinish,
    ) => {
      var fullname = name ? PATH_FS.resolve(PATH.join2(parent, name)) : parent;
      var dep = getUniqueRunDependency(`cp ${fullname}`);
      function processData(byteArray) {
        function finish(byteArray) {
          preFinish?.();
          if (!dontCreateFile) {
            FS_createDataFile(
              parent,
              name,
              byteArray,
              canRead,
              canWrite,
              canOwn,
            );
          }
          onload?.();
          removeRunDependency(dep);
        }
        if (
          FS_handledByPreloadPlugin(byteArray, fullname, finish, () => {
            onerror?.();
            removeRunDependency(dep);
          })
        ) {
          return;
        }
        finish(byteArray);
      }
      addRunDependency(dep);
      if (typeof url == "string") {
        asyncLoad(url, (byteArray) => processData(byteArray), onerror);
      } else {
        processData(url);
      }
    };
    var FS_modeStringToFlags = (str) => {
      var flagModes = {
        r: 0,
        "r+": 2,
        w: 512 | 64 | 1,
        "w+": 512 | 64 | 2,
        a: 1024 | 64 | 1,
        "a+": 1024 | 64 | 2,
      };
      var flags = flagModes[str];
      if (typeof flags == "undefined") {
        throw new Error(`Unknown file open mode: ${str}`);
      }
      return flags;
    };
    var FS_getMode = (canRead, canWrite) => {
      var mode = 0;
      if (canRead) mode |= 292 | 73;
      if (canWrite) mode |= 146;
      return mode;
    };
    var FS = {
      root: null,
      mounts: [],
      devices: {},
      streams: [],
      nextInode: 1,
      nameTable: null,
      currentPath: "/",
      initialized: false,
      ignorePermissions: true,
      ErrnoError: null,
      genericErrors: {},
      filesystems: null,
      syncFSRequests: 0,
      lookupPath(path, opts = {}) {
        path = PATH_FS.resolve(path);
        if (!path) return { path: "", node: null };
        var defaults = { follow_mount: true, recurse_count: 0 };
        opts = Object.assign(defaults, opts);
        if (opts.recurse_count > 8) {
          throw new FS.ErrnoError(32);
        }
        var parts = path.split("/").filter((p) => !!p);
        var current = FS.root;
        var current_path = "/";
        for (var i = 0; i < parts.length; i++) {
          var islast = i === parts.length - 1;
          if (islast && opts.parent) {
            break;
          }
          current = FS.lookupNode(current, parts[i]);
          current_path = PATH.join2(current_path, parts[i]);
          if (FS.isMountpoint(current)) {
            if (!islast || (islast && opts.follow_mount)) {
              current = current.mounted.root;
            }
          }
          if (!islast || opts.follow) {
            var count = 0;
            while (FS.isLink(current.mode)) {
              var link = FS.readlink(current_path);
              current_path = PATH_FS.resolve(PATH.dirname(current_path), link);
              var lookup = FS.lookupPath(current_path, {
                recurse_count: opts.recurse_count + 1,
              });
              current = lookup.node;
              if (count++ > 40) {
                throw new FS.ErrnoError(32);
              }
            }
          }
        }
        return { path: current_path, node: current };
      },
      getPath(node) {
        var path;
        while (true) {
          if (FS.isRoot(node)) {
            var mount = node.mount.mountpoint;
            if (!path) return mount;
            return mount[mount.length - 1] !== "/"
              ? `${mount}/${path}`
              : mount + path;
          }
          path = path ? `${node.name}/${path}` : node.name;
          node = node.parent;
        }
      },
      hashName(parentid, name) {
        var hash = 0;
        for (var i = 0; i < name.length; i++) {
          hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
        }
        return ((parentid + hash) >>> 0) % FS.nameTable.length;
      },
      hashAddNode(node) {
        var hash = FS.hashName(node.parent.id, node.name);
        node.name_next = FS.nameTable[hash];
        FS.nameTable[hash] = node;
      },
      hashRemoveNode(node) {
        var hash = FS.hashName(node.parent.id, node.name);
        if (FS.nameTable[hash] === node) {
          FS.nameTable[hash] = node.name_next;
        } else {
          var current = FS.nameTable[hash];
          while (current) {
            if (current.name_next === node) {
              current.name_next = node.name_next;
              break;
            }
            current = current.name_next;
          }
        }
      },
      lookupNode(parent, name) {
        var errCode = FS.mayLookup(parent);
        if (errCode) {
          throw new FS.ErrnoError(errCode, parent);
        }
        var hash = FS.hashName(parent.id, name);
        for (var node = FS.nameTable[hash]; node; node = node.name_next) {
          var nodeName = node.name;
          if (node.parent.id === parent.id && nodeName === name) {
            return node;
          }
        }
        return FS.lookup(parent, name);
      },
      createNode(parent, name, mode, rdev) {
        var node = new FS.FSNode(parent, name, mode, rdev);
        FS.hashAddNode(node);
        return node;
      },
      destroyNode(node) {
        FS.hashRemoveNode(node);
      },
      isRoot(node) {
        return node === node.parent;
      },
      isMountpoint(node) {
        return !!node.mounted;
      },
      isFile(mode) {
        return (mode & 61440) === 32768;
      },
      isDir(mode) {
        return (mode & 61440) === 16384;
      },
      isLink(mode) {
        return (mode & 61440) === 40960;
      },
      isChrdev(mode) {
        return (mode & 61440) === 8192;
      },
      isBlkdev(mode) {
        return (mode & 61440) === 24576;
      },
      isFIFO(mode) {
        return (mode & 61440) === 4096;
      },
      isSocket(mode) {
        return (mode & 49152) === 49152;
      },
      flagsToPermissionString(flag) {
        var perms = ["r", "w", "rw"][flag & 3];
        if (flag & 512) {
          perms += "w";
        }
        return perms;
      },
      nodePermissions(node, perms) {
        if (FS.ignorePermissions) {
          return 0;
        }
        if (perms.includes("r") && !(node.mode & 292)) {
          return 2;
        } else if (perms.includes("w") && !(node.mode & 146)) {
          return 2;
        } else if (perms.includes("x") && !(node.mode & 73)) {
          return 2;
        }
        return 0;
      },
      mayLookup(dir) {
        var errCode = FS.nodePermissions(dir, "x");
        if (errCode) return errCode;
        if (!dir.node_ops.lookup) return 2;
        return 0;
      },
      mayCreate(dir, name) {
        try {
          var node = FS.lookupNode(dir, name);
          return 20;
        } catch (e) {}
        return FS.nodePermissions(dir, "wx");
      },
      mayDelete(dir, name, isdir) {
        var node;
        try {
          node = FS.lookupNode(dir, name);
        } catch (e) {
          return e.errno;
        }
        var errCode = FS.nodePermissions(dir, "wx");
        if (errCode) {
          return errCode;
        }
        if (isdir) {
          if (!FS.isDir(node.mode)) {
            return 54;
          }
          if (FS.isRoot(node) || FS.getPath(node) === FS.cwd()) {
            return 10;
          }
        } else {
          if (FS.isDir(node.mode)) {
            return 31;
          }
        }
        return 0;
      },
      mayOpen(node, flags) {
        if (!node) {
          return 44;
        }
        if (FS.isLink(node.mode)) {
          return 32;
        } else if (FS.isDir(node.mode)) {
          if (FS.flagsToPermissionString(flags) !== "r" || flags & 512) {
            return 31;
          }
        }
        return FS.nodePermissions(node, FS.flagsToPermissionString(flags));
      },
      MAX_OPEN_FDS: 4096,
      nextfd() {
        for (var fd = 0; fd <= FS.MAX_OPEN_FDS; fd++) {
          if (!FS.streams[fd]) {
            return fd;
          }
        }
        throw new FS.ErrnoError(33);
      },
      getStreamChecked(fd) {
        var stream = FS.getStream(fd);
        if (!stream) {
          throw new FS.ErrnoError(8);
        }
        return stream;
      },
      getStream: (fd) => FS.streams[fd],
      createStream(stream, fd = -1) {
        if (!FS.FSStream) {
          FS.FSStream = function () {
            this.shared = {};
          };
          FS.FSStream.prototype = {};
          Object.defineProperties(FS.FSStream.prototype, {
            object: {
              get() {
                return this.node;
              },
              set(val) {
                this.node = val;
              },
            },
            isRead: {
              get() {
                return (this.flags & 2097155) !== 1;
              },
            },
            isWrite: {
              get() {
                return (this.flags & 2097155) !== 0;
              },
            },
            isAppend: {
              get() {
                return this.flags & 1024;
              },
            },
            flags: {
              get() {
                return this.shared.flags;
              },
              set(val) {
                this.shared.flags = val;
              },
            },
            position: {
              get() {
                return this.shared.position;
              },
              set(val) {
                this.shared.position = val;
              },
            },
          });
        }
        stream = Object.assign(new FS.FSStream(), stream);
        if (fd == -1) {
          fd = FS.nextfd();
        }
        stream.fd = fd;
        FS.streams[fd] = stream;
        return stream;
      },
      closeStream(fd) {
        FS.streams[fd] = null;
      },
      chrdev_stream_ops: {
        open(stream) {
          var device = FS.getDevice(stream.node.rdev);
          stream.stream_ops = device.stream_ops;
          stream.stream_ops.open?.(stream);
        },
        llseek() {
          throw new FS.ErrnoError(70);
        },
      },
      major: (dev) => dev >> 8,
      minor: (dev) => dev & 255,
      makedev: (ma, mi) => (ma << 8) | mi,
      registerDevice(dev, ops) {
        FS.devices[dev] = { stream_ops: ops };
      },
      getDevice: (dev) => FS.devices[dev],
      getMounts(mount) {
        var mounts = [];
        var check = [mount];
        while (check.length) {
          var m = check.pop();
          mounts.push(m);
          check.push.apply(check, m.mounts);
        }
        return mounts;
      },
      syncfs(populate, callback) {
        if (typeof populate == "function") {
          callback = populate;
          populate = false;
        }
        FS.syncFSRequests++;
        if (FS.syncFSRequests > 1) {
          err(
            `warning: ${FS.syncFSRequests} FS.syncfs operations in flight at once, probably just doing extra work`,
          );
        }
        var mounts = FS.getMounts(FS.root.mount);
        var completed = 0;
        function doCallback(errCode) {
          FS.syncFSRequests--;
          return callback(errCode);
        }
        function done(errCode) {
          if (errCode) {
            if (!done.errored) {
              done.errored = true;
              return doCallback(errCode);
            }
            return;
          }
          if (++completed >= mounts.length) {
            doCallback(null);
          }
        }
        mounts.forEach((mount) => {
          if (!mount.type.syncfs) {
            return done(null);
          }
          mount.type.syncfs(mount, populate, done);
        });
      },
      mount(type, opts, mountpoint) {
        var root = mountpoint === "/";
        var pseudo = !mountpoint;
        var node;
        if (root && FS.root) {
          throw new FS.ErrnoError(10);
        } else if (!root && !pseudo) {
          var lookup = FS.lookupPath(mountpoint, { follow_mount: false });
          mountpoint = lookup.path;
          node = lookup.node;
          if (FS.isMountpoint(node)) {
            throw new FS.ErrnoError(10);
          }
          if (!FS.isDir(node.mode)) {
            throw new FS.ErrnoError(54);
          }
        }
        var mount = {
          type: type,
          opts: opts,
          mountpoint: mountpoint,
          mounts: [],
        };
        var mountRoot = type.mount(mount);
        mountRoot.mount = mount;
        mount.root = mountRoot;
        if (root) {
          FS.root = mountRoot;
        } else if (node) {
          node.mounted = mount;
          if (node.mount) {
            node.mount.mounts.push(mount);
          }
        }
        return mountRoot;
      },
      unmount(mountpoint) {
        var lookup = FS.lookupPath(mountpoint, { follow_mount: false });
        if (!FS.isMountpoint(lookup.node)) {
          throw new FS.ErrnoError(28);
        }
        var node = lookup.node;
        var mount = node.mounted;
        var mounts = FS.getMounts(mount);
        Object.keys(FS.nameTable).forEach((hash) => {
          var current = FS.nameTable[hash];
          while (current) {
            var next = current.name_next;
            if (mounts.includes(current.mount)) {
              FS.destroyNode(current);
            }
            current = next;
          }
        });
        node.mounted = null;
        var idx = node.mount.mounts.indexOf(mount);
        node.mount.mounts.splice(idx, 1);
      },
      lookup(parent, name) {
        return parent.node_ops.lookup(parent, name);
      },
      mknod(path, mode, dev) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        var name = PATH.basename(path);
        if (!name || name === "." || name === "..") {
          throw new FS.ErrnoError(28);
        }
        var errCode = FS.mayCreate(parent, name);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.mknod) {
          throw new FS.ErrnoError(63);
        }
        return parent.node_ops.mknod(parent, name, mode, dev);
      },
      create(path, mode) {
        mode = mode !== undefined ? mode : 438;
        mode &= 4095;
        mode |= 32768;
        return FS.mknod(path, mode, 0);
      },
      mkdir(path, mode) {
        mode = mode !== undefined ? mode : 511;
        mode &= 511 | 512;
        mode |= 16384;
        return FS.mknod(path, mode, 0);
      },
      mkdirTree(path, mode) {
        var dirs = path.split("/");
        var d = "";
        for (var i = 0; i < dirs.length; ++i) {
          if (!dirs[i]) continue;
          d += "/" + dirs[i];
          try {
            FS.mkdir(d, mode);
          } catch (e) {
            if (e.errno != 20) throw e;
          }
        }
      },
      mkdev(path, mode, dev) {
        if (typeof dev == "undefined") {
          dev = mode;
          mode = 438;
        }
        mode |= 8192;
        return FS.mknod(path, mode, dev);
      },
      symlink(oldpath, newpath) {
        if (!PATH_FS.resolve(oldpath)) {
          throw new FS.ErrnoError(44);
        }
        var lookup = FS.lookupPath(newpath, { parent: true });
        var parent = lookup.node;
        if (!parent) {
          throw new FS.ErrnoError(44);
        }
        var newname = PATH.basename(newpath);
        var errCode = FS.mayCreate(parent, newname);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.symlink) {
          throw new FS.ErrnoError(63);
        }
        return parent.node_ops.symlink(parent, newname, oldpath);
      },
      rename(old_path, new_path) {
        var old_dirname = PATH.dirname(old_path);
        var new_dirname = PATH.dirname(new_path);
        var old_name = PATH.basename(old_path);
        var new_name = PATH.basename(new_path);
        var lookup, old_dir, new_dir;
        lookup = FS.lookupPath(old_path, { parent: true });
        old_dir = lookup.node;
        lookup = FS.lookupPath(new_path, { parent: true });
        new_dir = lookup.node;
        if (!old_dir || !new_dir) throw new FS.ErrnoError(44);
        if (old_dir.mount !== new_dir.mount) {
          throw new FS.ErrnoError(75);
        }
        var old_node = FS.lookupNode(old_dir, old_name);
        var relative = PATH_FS.relative(old_path, new_dirname);
        if (relative.charAt(0) !== ".") {
          throw new FS.ErrnoError(28);
        }
        relative = PATH_FS.relative(new_path, old_dirname);
        if (relative.charAt(0) !== ".") {
          throw new FS.ErrnoError(55);
        }
        var new_node;
        try {
          new_node = FS.lookupNode(new_dir, new_name);
        } catch (e) {}
        if (old_node === new_node) {
          return;
        }
        var isdir = FS.isDir(old_node.mode);
        var errCode = FS.mayDelete(old_dir, old_name, isdir);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        errCode = new_node
          ? FS.mayDelete(new_dir, new_name, isdir)
          : FS.mayCreate(new_dir, new_name);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!old_dir.node_ops.rename) {
          throw new FS.ErrnoError(63);
        }
        if (
          FS.isMountpoint(old_node) ||
          (new_node && FS.isMountpoint(new_node))
        ) {
          throw new FS.ErrnoError(10);
        }
        if (new_dir !== old_dir) {
          errCode = FS.nodePermissions(old_dir, "w");
          if (errCode) {
            throw new FS.ErrnoError(errCode);
          }
        }
        FS.hashRemoveNode(old_node);
        try {
          old_dir.node_ops.rename(old_node, new_dir, new_name);
        } catch (e) {
          throw e;
        } finally {
          FS.hashAddNode(old_node);
        }
      },
      rmdir(path) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        var name = PATH.basename(path);
        var node = FS.lookupNode(parent, name);
        var errCode = FS.mayDelete(parent, name, true);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.rmdir) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isMountpoint(node)) {
          throw new FS.ErrnoError(10);
        }
        parent.node_ops.rmdir(parent, name);
        FS.destroyNode(node);
      },
      readdir(path) {
        var lookup = FS.lookupPath(path, { follow: true });
        var node = lookup.node;
        if (!node.node_ops.readdir) {
          throw new FS.ErrnoError(54);
        }
        return node.node_ops.readdir(node);
      },
      unlink(path) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        if (!parent) {
          throw new FS.ErrnoError(44);
        }
        var name = PATH.basename(path);
        var node = FS.lookupNode(parent, name);
        var errCode = FS.mayDelete(parent, name, false);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.unlink) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isMountpoint(node)) {
          throw new FS.ErrnoError(10);
        }
        parent.node_ops.unlink(parent, name);
        FS.destroyNode(node);
      },
      readlink(path) {
        var lookup = FS.lookupPath(path);
        var link = lookup.node;
        if (!link) {
          throw new FS.ErrnoError(44);
        }
        if (!link.node_ops.readlink) {
          throw new FS.ErrnoError(28);
        }
        return PATH_FS.resolve(
          FS.getPath(link.parent),
          link.node_ops.readlink(link),
        );
      },
      stat(path, dontFollow) {
        var lookup = FS.lookupPath(path, { follow: !dontFollow });
        var node = lookup.node;
        if (!node) {
          throw new FS.ErrnoError(44);
        }
        if (!node.node_ops.getattr) {
          throw new FS.ErrnoError(63);
        }
        return node.node_ops.getattr(node);
      },
      lstat(path) {
        return FS.stat(path, true);
      },
      chmod(path, mode, dontFollow) {
        var node;
        if (typeof path == "string") {
          var lookup = FS.lookupPath(path, { follow: !dontFollow });
          node = lookup.node;
        } else {
          node = path;
        }
        if (!node.node_ops.setattr) {
          throw new FS.ErrnoError(63);
        }
        node.node_ops.setattr(node, {
          mode: (mode & 4095) | (node.mode & ~4095),
          timestamp: Date.now(),
        });
      },
      lchmod(path, mode) {
        FS.chmod(path, mode, true);
      },
      fchmod(fd, mode) {
        var stream = FS.getStreamChecked(fd);
        FS.chmod(stream.node, mode);
      },
      chown(path, uid, gid, dontFollow) {
        var node;
        if (typeof path == "string") {
          var lookup = FS.lookupPath(path, { follow: !dontFollow });
          node = lookup.node;
        } else {
          node = path;
        }
        if (!node.node_ops.setattr) {
          throw new FS.ErrnoError(63);
        }
        node.node_ops.setattr(node, { timestamp: Date.now() });
      },
      lchown(path, uid, gid) {
        FS.chown(path, uid, gid, true);
      },
      fchown(fd, uid, gid) {
        var stream = FS.getStreamChecked(fd);
        FS.chown(stream.node, uid, gid);
      },
      truncate(path, len) {
        if (len < 0) {
          throw new FS.ErrnoError(28);
        }
        var node;
        if (typeof path == "string") {
          var lookup = FS.lookupPath(path, { follow: true });
          node = lookup.node;
        } else {
          node = path;
        }
        if (!node.node_ops.setattr) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isDir(node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!FS.isFile(node.mode)) {
          throw new FS.ErrnoError(28);
        }
        var errCode = FS.nodePermissions(node, "w");
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        node.node_ops.setattr(node, { size: len, timestamp: Date.now() });
      },
      ftruncate(fd, len) {
        var stream = FS.getStreamChecked(fd);
        if ((stream.flags & 2097155) === 0) {
          throw new FS.ErrnoError(28);
        }
        FS.truncate(stream.node, len);
      },
      utime(path, atime, mtime) {
        var lookup = FS.lookupPath(path, { follow: true });
        var node = lookup.node;
        node.node_ops.setattr(node, { timestamp: Math.max(atime, mtime) });
      },
      open(path, flags, mode) {
        if (path === "") {
          throw new FS.ErrnoError(44);
        }
        flags = typeof flags == "string" ? FS_modeStringToFlags(flags) : flags;
        mode = typeof mode == "undefined" ? 438 : mode;
        if (flags & 64) {
          mode = (mode & 4095) | 32768;
        } else {
          mode = 0;
        }
        var node;
        if (typeof path == "object") {
          node = path;
        } else {
          path = PATH.normalize(path);
          try {
            var lookup = FS.lookupPath(path, { follow: !(flags & 131072) });
            node = lookup.node;
          } catch (e) {}
        }
        var created = false;
        if (flags & 64) {
          if (node) {
            if (flags & 128) {
              throw new FS.ErrnoError(20);
            }
          } else {
            node = FS.mknod(path, mode, 0);
            created = true;
          }
        }
        if (!node) {
          throw new FS.ErrnoError(44);
        }
        if (FS.isChrdev(node.mode)) {
          flags &= ~512;
        }
        if (flags & 65536 && !FS.isDir(node.mode)) {
          throw new FS.ErrnoError(54);
        }
        if (!created) {
          var errCode = FS.mayOpen(node, flags);
          if (errCode) {
            throw new FS.ErrnoError(errCode);
          }
        }
        if (flags & 512 && !created) {
          FS.truncate(node, 0);
        }
        flags &= ~(128 | 512 | 131072);
        var stream = FS.createStream({
          node: node,
          path: FS.getPath(node),
          flags: flags,
          seekable: true,
          position: 0,
          stream_ops: node.stream_ops,
          ungotten: [],
          error: false,
        });
        if (stream.stream_ops.open) {
          stream.stream_ops.open(stream);
        }
        if (Module["logReadFiles"] && !(flags & 1)) {
          if (!FS.readFiles) FS.readFiles = {};
          if (!(path in FS.readFiles)) {
            FS.readFiles[path] = 1;
          }
        }
        return stream;
      },
      close(stream) {
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if (stream.getdents) stream.getdents = null;
        try {
          if (stream.stream_ops.close) {
            stream.stream_ops.close(stream);
          }
        } catch (e) {
          throw e;
        } finally {
          FS.closeStream(stream.fd);
        }
        stream.fd = null;
      },
      isClosed(stream) {
        return stream.fd === null;
      },
      llseek(stream, offset, whence) {
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if (!stream.seekable || !stream.stream_ops.llseek) {
          throw new FS.ErrnoError(70);
        }
        if (whence != 0 && whence != 1 && whence != 2) {
          throw new FS.ErrnoError(28);
        }
        stream.position = stream.stream_ops.llseek(stream, offset, whence);
        stream.ungotten = [];
        return stream.position;
      },
      read(stream, buffer, offset, length, position) {
        if (length < 0 || position < 0) {
          throw new FS.ErrnoError(28);
        }
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if ((stream.flags & 2097155) === 1) {
          throw new FS.ErrnoError(8);
        }
        if (FS.isDir(stream.node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!stream.stream_ops.read) {
          throw new FS.ErrnoError(28);
        }
        var seeking = typeof position != "undefined";
        if (!seeking) {
          position = stream.position;
        } else if (!stream.seekable) {
          throw new FS.ErrnoError(70);
        }
        var bytesRead = stream.stream_ops.read(
          stream,
          buffer,
          offset,
          length,
          position,
        );
        if (!seeking) stream.position += bytesRead;
        return bytesRead;
      },
      write(stream, buffer, offset, length, position, canOwn) {
        if (length < 0 || position < 0) {
          throw new FS.ErrnoError(28);
        }
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if ((stream.flags & 2097155) === 0) {
          throw new FS.ErrnoError(8);
        }
        if (FS.isDir(stream.node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!stream.stream_ops.write) {
          throw new FS.ErrnoError(28);
        }
        if (stream.seekable && stream.flags & 1024) {
          FS.llseek(stream, 0, 2);
        }
        var seeking = typeof position != "undefined";
        if (!seeking) {
          position = stream.position;
        } else if (!stream.seekable) {
          throw new FS.ErrnoError(70);
        }
        var bytesWritten = stream.stream_ops.write(
          stream,
          buffer,
          offset,
          length,
          position,
          canOwn,
        );
        if (!seeking) stream.position += bytesWritten;
        return bytesWritten;
      },
      allocate(stream, offset, length) {
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if (offset < 0 || length <= 0) {
          throw new FS.ErrnoError(28);
        }
        if ((stream.flags & 2097155) === 0) {
          throw new FS.ErrnoError(8);
        }
        if (!FS.isFile(stream.node.mode) && !FS.isDir(stream.node.mode)) {
          throw new FS.ErrnoError(43);
        }
        if (!stream.stream_ops.allocate) {
          throw new FS.ErrnoError(138);
        }
        stream.stream_ops.allocate(stream, offset, length);
      },
      mmap(stream, length, position, prot, flags) {
        if (
          (prot & 2) !== 0 &&
          (flags & 2) === 0 &&
          (stream.flags & 2097155) !== 2
        ) {
          throw new FS.ErrnoError(2);
        }
        if ((stream.flags & 2097155) === 1) {
          throw new FS.ErrnoError(2);
        }
        if (!stream.stream_ops.mmap) {
          throw new FS.ErrnoError(43);
        }
        return stream.stream_ops.mmap(stream, length, position, prot, flags);
      },
      msync(stream, buffer, offset, length, mmapFlags) {
        if (!stream.stream_ops.msync) {
          return 0;
        }
        return stream.stream_ops.msync(
          stream,
          buffer,
          offset,
          length,
          mmapFlags,
        );
      },
      munmap: (stream) => 0,
      ioctl(stream, cmd, arg) {
        if (!stream.stream_ops.ioctl) {
          throw new FS.ErrnoError(59);
        }
        return stream.stream_ops.ioctl(stream, cmd, arg);
      },
      readFile(path, opts = {}) {
        opts.flags = opts.flags || 0;
        opts.encoding = opts.encoding || "binary";
        if (opts.encoding !== "utf8" && opts.encoding !== "binary") {
          throw new Error(`Invalid encoding type "${opts.encoding}"`);
        }
        var ret;
        var stream = FS.open(path, opts.flags);
        var stat = FS.stat(path);
        var length = stat.size;
        var buf = new Uint8Array(length);
        FS.read(stream, buf, 0, length, 0);
        if (opts.encoding === "utf8") {
          ret = UTF8ArrayToString(buf, 0);
        } else if (opts.encoding === "binary") {
          ret = buf;
        }
        FS.close(stream);
        return ret;
      },
      writeFile(path, data, opts = {}) {
        opts.flags = opts.flags || 577;
        var stream = FS.open(path, opts.flags, opts.mode);
        if (typeof data == "string") {
          var buf = new Uint8Array(lengthBytesUTF8(data) + 1);
          var actualNumBytes = stringToUTF8Array(data, buf, 0, buf.length);
          FS.write(stream, buf, 0, actualNumBytes, undefined, opts.canOwn);
        } else if (ArrayBuffer.isView(data)) {
          FS.write(stream, data, 0, data.byteLength, undefined, opts.canOwn);
        } else {
          throw new Error("Unsupported data type");
        }
        FS.close(stream);
      },
      cwd: () => FS.currentPath,
      chdir(path) {
        var lookup = FS.lookupPath(path, { follow: true });
        if (lookup.node === null) {
          throw new FS.ErrnoError(44);
        }
        if (!FS.isDir(lookup.node.mode)) {
          throw new FS.ErrnoError(54);
        }
        var errCode = FS.nodePermissions(lookup.node, "x");
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        FS.currentPath = lookup.path;
      },
      createDefaultDirectories() {
        FS.mkdir("/tmp");
        FS.mkdir("/home");
        FS.mkdir("/home/web_user");
      },
      createDefaultDevices() {
        FS.mkdir("/dev");
        FS.registerDevice(FS.makedev(1, 3), {
          read: () => 0,
          write: (stream, buffer, offset, length, pos) => length,
        });
        FS.mkdev("/dev/null", FS.makedev(1, 3));
        TTY.register(FS.makedev(5, 0), TTY.default_tty_ops);
        TTY.register(FS.makedev(6, 0), TTY.default_tty1_ops);
        FS.mkdev("/dev/tty", FS.makedev(5, 0));
        FS.mkdev("/dev/tty1", FS.makedev(6, 0));
        var randomBuffer = new Uint8Array(1024),
          randomLeft = 0;
        var randomByte = () => {
          if (randomLeft === 0) {
            randomLeft = randomFill(randomBuffer).byteLength;
          }
          return randomBuffer[--randomLeft];
        };
        FS.createDevice("/dev", "random", randomByte);
        FS.createDevice("/dev", "urandom", randomByte);
        FS.mkdir("/dev/shm");
        FS.mkdir("/dev/shm/tmp");
      },
      createSpecialDirectories() {
        FS.mkdir("/proc");
        var proc_self = FS.mkdir("/proc/self");
        FS.mkdir("/proc/self/fd");
        FS.mount(
          {
            mount() {
              var node = FS.createNode(proc_self, "fd", 16384 | 511, 73);
              node.node_ops = {
                lookup(parent, name) {
                  var fd = +name;
                  var stream = FS.getStreamChecked(fd);
                  var ret = {
                    parent: null,
                    mount: { mountpoint: "fake" },
                    node_ops: { readlink: () => stream.path },
                  };
                  ret.parent = ret;
                  return ret;
                },
              };
              return node;
            },
          },
          {},
          "/proc/self/fd",
        );
      },
      createStandardStreams() {
        if (Module["stdin"]) {
          FS.createDevice("/dev", "stdin", Module["stdin"]);
        } else {
          FS.symlink("/dev/tty", "/dev/stdin");
        }
        if (Module["stdout"]) {
          FS.createDevice("/dev", "stdout", null, Module["stdout"]);
        } else {
          FS.symlink("/dev/tty", "/dev/stdout");
        }
        if (Module["stderr"]) {
          FS.createDevice("/dev", "stderr", null, Module["stderr"]);
        } else {
          FS.symlink("/dev/tty1", "/dev/stderr");
        }
        var stdin = FS.open("/dev/stdin", 0);
        var stdout = FS.open("/dev/stdout", 1);
        var stderr = FS.open("/dev/stderr", 1);
      },
      ensureErrnoError() {
        if (FS.ErrnoError) return;
        FS.ErrnoError = function ErrnoError(errno, node) {
          this.name = "ErrnoError";
          this.node = node;
          this.setErrno = function (errno) {
            this.errno = errno;
          };
          this.setErrno(errno);
          this.message = "FS error";
        };
        FS.ErrnoError.prototype = new Error();
        FS.ErrnoError.prototype.constructor = FS.ErrnoError;
        [44].forEach((code) => {
          FS.genericErrors[code] = new FS.ErrnoError(code);
          FS.genericErrors[code].stack = "<generic error, no stack>";
        });
      },
      staticInit() {
        FS.ensureErrnoError();
        FS.nameTable = new Array(4096);
        FS.mount(MEMFS, {}, "/");
        FS.createDefaultDirectories();
        FS.createDefaultDevices();
        FS.createSpecialDirectories();
        FS.filesystems = { MEMFS: MEMFS };
      },
      init(input, output, error) {
        FS.init.initialized = true;
        FS.ensureErrnoError();
        Module["stdin"] = input || Module["stdin"];
        Module["stdout"] = output || Module["stdout"];
        Module["stderr"] = error || Module["stderr"];
        FS.createStandardStreams();
      },
      quit() {
        FS.init.initialized = false;
        for (var i = 0; i < FS.streams.length; i++) {
          var stream = FS.streams[i];
          if (!stream) {
            continue;
          }
          FS.close(stream);
        }
      },
      findObject(path, dontResolveLastLink) {
        var ret = FS.analyzePath(path, dontResolveLastLink);
        if (!ret.exists) {
          return null;
        }
        return ret.object;
      },
      analyzePath(path, dontResolveLastLink) {
        try {
          var lookup = FS.lookupPath(path, { follow: !dontResolveLastLink });
          path = lookup.path;
        } catch (e) {}
        var ret = {
          isRoot: false,
          exists: false,
          error: 0,
          name: null,
          path: null,
          object: null,
          parentExists: false,
          parentPath: null,
          parentObject: null,
        };
        try {
          var lookup = FS.lookupPath(path, { parent: true });
          ret.parentExists = true;
          ret.parentPath = lookup.path;
          ret.parentObject = lookup.node;
          ret.name = PATH.basename(path);
          lookup = FS.lookupPath(path, { follow: !dontResolveLastLink });
          ret.exists = true;
          ret.path = lookup.path;
          ret.object = lookup.node;
          ret.name = lookup.node.name;
          ret.isRoot = lookup.path === "/";
        } catch (e) {
          ret.error = e.errno;
        }
        return ret;
      },
      createPath(parent, path, canRead, canWrite) {
        parent = typeof parent == "string" ? parent : FS.getPath(parent);
        var parts = path.split("/").reverse();
        while (parts.length) {
          var part = parts.pop();
          if (!part) continue;
          var current = PATH.join2(parent, part);
          try {
            FS.mkdir(current);
          } catch (e) {}
          parent = current;
        }
        return current;
      },
      createFile(parent, name, properties, canRead, canWrite) {
        var path = PATH.join2(
          typeof parent == "string" ? parent : FS.getPath(parent),
          name,
        );
        var mode = FS_getMode(canRead, canWrite);
        return FS.create(path, mode);
      },
      createDataFile(parent, name, data, canRead, canWrite, canOwn) {
        var path = name;
        if (parent) {
          parent = typeof parent == "string" ? parent : FS.getPath(parent);
          path = name ? PATH.join2(parent, name) : parent;
        }
        var mode = FS_getMode(canRead, canWrite);
        var node = FS.create(path, mode);
        if (data) {
          if (typeof data == "string") {
            var arr = new Array(data.length);
            for (var i = 0, len = data.length; i < len; ++i)
              arr[i] = data.charCodeAt(i);
            data = arr;
          }
          FS.chmod(node, mode | 146);
          var stream = FS.open(node, 577);
          FS.write(stream, data, 0, data.length, 0, canOwn);
          FS.close(stream);
          FS.chmod(node, mode);
        }
      },
      createDevice(parent, name, input, output) {
        var path = PATH.join2(
          typeof parent == "string" ? parent : FS.getPath(parent),
          name,
        );
        var mode = FS_getMode(!!input, !!output);
        if (!FS.createDevice.major) FS.createDevice.major = 64;
        var dev = FS.makedev(FS.createDevice.major++, 0);
        FS.registerDevice(dev, {
          open(stream) {
            stream.seekable = false;
          },
          close(stream) {
            if (output?.buffer?.length) {
              output(10);
            }
          },
          read(stream, buffer, offset, length, pos) {
            var bytesRead = 0;
            for (var i = 0; i < length; i++) {
              var result;
              try {
                result = input();
              } catch (e) {
                throw new FS.ErrnoError(29);
              }
              if (result === undefined && bytesRead === 0) {
                throw new FS.ErrnoError(6);
              }
              if (result === null || result === undefined) break;
              bytesRead++;
              buffer[offset + i] = result;
            }
            if (bytesRead) {
              stream.node.timestamp = Date.now();
            }
            return bytesRead;
          },
          write(stream, buffer, offset, length, pos) {
            for (var i = 0; i < length; i++) {
              try {
                output(buffer[offset + i]);
              } catch (e) {
                throw new FS.ErrnoError(29);
              }
            }
            if (length) {
              stream.node.timestamp = Date.now();
            }
            return i;
          },
        });
        return FS.mkdev(path, mode, dev);
      },
      forceLoadFile(obj) {
        if (obj.isDevice || obj.isFolder || obj.link || obj.contents)
          return true;
        if (typeof XMLHttpRequest != "undefined") {
          throw new Error(
            "Lazy loading should have been performed (contents set) in createLazyFile, but it was not. Lazy loading only works in web workers. Use --embed-file or --preload-file in emcc on the main thread.",
          );
        } else if (read_) {
          try {
            obj.contents = intArrayFromString(read_(obj.url), true);
            obj.usedBytes = obj.contents.length;
          } catch (e) {
            throw new FS.ErrnoError(29);
          }
        } else {
          throw new Error("Cannot load without read() or XMLHttpRequest.");
        }
      },
      createLazyFile(parent, name, url, canRead, canWrite) {
        function LazyUint8Array() {
          this.lengthKnown = false;
          this.chunks = [];
        }
        LazyUint8Array.prototype.get = function LazyUint8Array_get(idx) {
          if (idx > this.length - 1 || idx < 0) {
            return undefined;
          }
          var chunkOffset = idx % this.chunkSize;
          var chunkNum = (idx / this.chunkSize) | 0;
          return this.getter(chunkNum)[chunkOffset];
        };
        LazyUint8Array.prototype.setDataGetter =
          function LazyUint8Array_setDataGetter(getter) {
            this.getter = getter;
          };
        LazyUint8Array.prototype.cacheLength =
          function LazyUint8Array_cacheLength() {
            var xhr = new XMLHttpRequest();
            xhr.open("HEAD", url, false);
            xhr.send(null);
            if (
              !((xhr.status >= 200 && xhr.status < 300) || xhr.status === 304)
            )
              throw new Error(
                "Couldn't load " + url + ". Status: " + xhr.status,
              );
            var datalength = Number(xhr.getResponseHeader("Content-length"));
            var header;
            var hasByteServing =
              (header = xhr.getResponseHeader("Accept-Ranges")) &&
              header === "bytes";
            var usesGzip =
              (header = xhr.getResponseHeader("Content-Encoding")) &&
              header === "gzip";
            var chunkSize = 1024 * 1024;
            if (!hasByteServing) chunkSize = datalength;
            var doXHR = (from, to) => {
              if (from > to)
                throw new Error(
                  "invalid range (" +
                    from +
                    ", " +
                    to +
                    ") or no bytes requested!",
                );
              if (to > datalength - 1)
                throw new Error(
                  "only " + datalength + " bytes available! programmer error!",
                );
              var xhr = new XMLHttpRequest();
              xhr.open("GET", url, false);
              if (datalength !== chunkSize)
                xhr.setRequestHeader("Range", "bytes=" + from + "-" + to);
              xhr.responseType = "arraybuffer";
              if (xhr.overrideMimeType) {
                xhr.overrideMimeType("text/plain; charset=x-user-defined");
              }
              xhr.send(null);
              if (
                !((xhr.status >= 200 && xhr.status < 300) || xhr.status === 304)
              )
                throw new Error(
                  "Couldn't load " + url + ". Status: " + xhr.status,
                );
              if (xhr.response !== undefined) {
                return new Uint8Array(xhr.response || []);
              }
              return intArrayFromString(xhr.responseText || "", true);
            };
            var lazyArray = this;
            lazyArray.setDataGetter((chunkNum) => {
              var start = chunkNum * chunkSize;
              var end = (chunkNum + 1) * chunkSize - 1;
              end = Math.min(end, datalength - 1);
              if (typeof lazyArray.chunks[chunkNum] == "undefined") {
                lazyArray.chunks[chunkNum] = doXHR(start, end);
              }
              if (typeof lazyArray.chunks[chunkNum] == "undefined")
                throw new Error("doXHR failed!");
              return lazyArray.chunks[chunkNum];
            });
            if (usesGzip || !datalength) {
              chunkSize = datalength = 1;
              datalength = this.getter(0).length;
              chunkSize = datalength;
              out(
                "LazyFiles on gzip forces download of the whole file when length is accessed",
              );
            }
            this._length = datalength;
            this._chunkSize = chunkSize;
            this.lengthKnown = true;
          };
        if (typeof XMLHttpRequest != "undefined") {
          if (!ENVIRONMENT_IS_WORKER)
            throw "Cannot do synchronous binary XHRs outside webworkers in modern browsers. Use --embed-file or --preload-file in emcc";
          var lazyArray = new LazyUint8Array();
          Object.defineProperties(lazyArray, {
            length: {
              get: function () {
                if (!this.lengthKnown) {
                  this.cacheLength();
                }
                return this._length;
              },
            },
            chunkSize: {
              get: function () {
                if (!this.lengthKnown) {
                  this.cacheLength();
                }
                return this._chunkSize;
              },
            },
          });
          var properties = { isDevice: false, contents: lazyArray };
        } else {
          var properties = { isDevice: false, url: url };
        }
        var node = FS.createFile(parent, name, properties, canRead, canWrite);
        if (properties.contents) {
          node.contents = properties.contents;
        } else if (properties.url) {
          node.contents = null;
          node.url = properties.url;
        }
        Object.defineProperties(node, {
          usedBytes: {
            get: function () {
              return this.contents.length;
            },
          },
        });
        var stream_ops = {};
        var keys = Object.keys(node.stream_ops);
        keys.forEach((key) => {
          var fn = node.stream_ops[key];
          stream_ops[key] = function forceLoadLazyFile() {
            FS.forceLoadFile(node);
            return fn.apply(null, arguments);
          };
        });
        function writeChunks(stream, buffer, offset, length, position) {
          var contents = stream.node.contents;
          if (position >= contents.length) return 0;
          var size = Math.min(contents.length - position, length);
          if (contents.slice) {
            for (var i = 0; i < size; i++) {
              buffer[offset + i] = contents[position + i];
            }
          } else {
            for (var i = 0; i < size; i++) {
              buffer[offset + i] = contents.get(position + i);
            }
          }
          return size;
        }
        stream_ops.read = (stream, buffer, offset, length, position) => {
          FS.forceLoadFile(node);
          return writeChunks(stream, buffer, offset, length, position);
        };
        stream_ops.mmap = (stream, length, position, prot, flags) => {
          FS.forceLoadFile(node);
          var ptr = mmapAlloc(length);
          if (!ptr) {
            throw new FS.ErrnoError(48);
          }
          writeChunks(stream, GROWABLE_HEAP_I8(), ptr, length, position);
          return { ptr: ptr, allocated: true };
        };
        node.stream_ops = stream_ops;
        return node;
      },
    };
    var UTF8ToString = (ptr, maxBytesToRead) =>
      ptr ? UTF8ArrayToString(GROWABLE_HEAP_U8(), ptr, maxBytesToRead) : "";
    var SYSCALLS = {
      DEFAULT_POLLMASK: 5,
      calculateAt(dirfd, path, allowEmpty) {
        if (PATH.isAbs(path)) {
          return path;
        }
        var dir;
        if (dirfd === -100) {
          dir = FS.cwd();
        } else {
          var dirstream = SYSCALLS.getStreamFromFD(dirfd);
          dir = dirstream.path;
        }
        if (path.length == 0) {
          if (!allowEmpty) {
            throw new FS.ErrnoError(44);
          }
          return dir;
        }
        return PATH.join2(dir, path);
      },
      doStat(func, path, buf) {
        try {
          var stat = func(path);
        } catch (e) {
          if (
            e &&
            e.node &&
            PATH.normalize(path) !== PATH.normalize(FS.getPath(e.node))
          ) {
            return -54;
          }
          throw e;
        }
        GROWABLE_HEAP_I32()[buf >> 2] = stat.dev;
        GROWABLE_HEAP_I32()[(buf + 4) >> 2] = stat.mode;
        GROWABLE_HEAP_U32()[(buf + 8) >> 2] = stat.nlink;
        GROWABLE_HEAP_I32()[(buf + 12) >> 2] = stat.uid;
        GROWABLE_HEAP_I32()[(buf + 16) >> 2] = stat.gid;
        GROWABLE_HEAP_I32()[(buf + 20) >> 2] = stat.rdev;
        HEAP64[(buf + 24) >> 3] = BigInt(stat.size);
        GROWABLE_HEAP_I32()[(buf + 32) >> 2] = 4096;
        GROWABLE_HEAP_I32()[(buf + 36) >> 2] = stat.blocks;
        var atime = stat.atime.getTime();
        var mtime = stat.mtime.getTime();
        var ctime = stat.ctime.getTime();
        HEAP64[(buf + 40) >> 3] = BigInt(Math.floor(atime / 1e3));
        GROWABLE_HEAP_U32()[(buf + 48) >> 2] = (atime % 1e3) * 1e3;
        HEAP64[(buf + 56) >> 3] = BigInt(Math.floor(mtime / 1e3));
        GROWABLE_HEAP_U32()[(buf + 64) >> 2] = (mtime % 1e3) * 1e3;
        HEAP64[(buf + 72) >> 3] = BigInt(Math.floor(ctime / 1e3));
        GROWABLE_HEAP_U32()[(buf + 80) >> 2] = (ctime % 1e3) * 1e3;
        HEAP64[(buf + 88) >> 3] = BigInt(stat.ino);
        return 0;
      },
      doMsync(addr, stream, len, flags, offset) {
        if (!FS.isFile(stream.node.mode)) {
          throw new FS.ErrnoError(43);
        }
        if (flags & 2) {
          return 0;
        }
        var buffer = GROWABLE_HEAP_U8().slice(addr, addr + len);
        FS.msync(stream, buffer, offset, len, flags);
      },
      varargs: undefined,
      get() {
        var ret = GROWABLE_HEAP_I32()[+SYSCALLS.varargs >> 2];
        SYSCALLS.varargs += 4;
        return ret;
      },
      getp() {
        return SYSCALLS.get();
      },
      getStr(ptr) {
        var ret = UTF8ToString(ptr);
        return ret;
      },
      getStreamFromFD(fd) {
        var stream = FS.getStreamChecked(fd);
        return stream;
      },
    };
    var withStackSave = (f) => {
      var stack = stackSave();
      var ret = f();
      stackRestore(stack);
      return ret;
    };
    var MAX_INT53 = 9007199254740992;
    var MIN_INT53 = -9007199254740992;
    var bigintToI53Checked = (num) =>
      num < MIN_INT53 || num > MAX_INT53 ? NaN : Number(num);
    var proxyToMainThread = function (index, sync) {
      var numCallArgs = arguments.length - 2;
      var outerArgs = arguments;
      return withStackSave(() => {
        var serializedNumCallArgs = numCallArgs * 2;
        var args = stackAlloc(serializedNumCallArgs * 8);
        var b = args >> 3;
        for (var i = 0; i < numCallArgs; i++) {
          var arg = outerArgs[2 + i];
          if (typeof arg == "bigint") {
            HEAP64[b + 2 * i] = 1n;
            HEAP64[b + 2 * i + 1] = arg;
          } else {
            HEAP64[b + 2 * i] = 0n;
            GROWABLE_HEAP_F64()[b + 2 * i + 1] = arg;
          }
        }
        return __emscripten_run_on_main_thread_js(
          index,
          serializedNumCallArgs,
          args,
          sync,
        );
      });
    };
    function _proc_exit(code) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(0, 1, code);
      EXITSTATUS = code;
      if (!keepRuntimeAlive()) {
        PThread.terminateAllThreads();
        Module["onExit"]?.(code);
        ABORT = true;
      }
      quit_(code, new ExitStatus(code));
    }
    var exitJS = (status, implicit) => {
      EXITSTATUS = status;
      if (ENVIRONMENT_IS_PTHREAD) {
        exitOnMainThread(status);
        throw "unwind";
      }
      _proc_exit(status);
    };
    var _exit = exitJS;
    var handleException = (e) => {
      if (e instanceof ExitStatus || e == "unwind") {
        return EXITSTATUS;
      }
      quit_(1, e);
    };
    var PThread = {
      unusedWorkers: [],
      runningWorkers: [],
      tlsInitFunctions: [],
      pthreads: {},
      init() {
        if (ENVIRONMENT_IS_PTHREAD) {
          PThread.initWorker();
        } else {
          PThread.initMainThread();
        }
      },
      initMainThread() {
        var pthreadPoolSize = 2;
        while (pthreadPoolSize--) {
          PThread.allocateUnusedWorker();
        }
        addOnPreRun(() => {
          addRunDependency("loading-workers");
          PThread.loadWasmModuleToAllWorkers(() =>
            removeRunDependency("loading-workers"),
          );
        });
      },
      initWorker() {
        noExitRuntime = false;
      },
      setExitStatus: (status) => (EXITSTATUS = status),
      terminateAllThreads__deps: ["$terminateWorker"],
      terminateAllThreads: () => {
        for (var worker of PThread.runningWorkers) {
          terminateWorker(worker);
        }
        for (var worker of PThread.unusedWorkers) {
          terminateWorker(worker);
        }
        PThread.unusedWorkers = [];
        PThread.runningWorkers = [];
        PThread.pthreads = [];
      },
      returnWorkerToPool: (worker) => {
        var pthread_ptr = worker.pthread_ptr;
        delete PThread.pthreads[pthread_ptr];
        PThread.unusedWorkers.push(worker);
        PThread.runningWorkers.splice(
          PThread.runningWorkers.indexOf(worker),
          1,
        );
        worker.pthread_ptr = 0;
        __emscripten_thread_free_data(pthread_ptr);
      },
      receiveObjectTransfer(data) {},
      threadInitTLS() {
        PThread.tlsInitFunctions.forEach((f) => f());
      },
      loadWasmModuleToWorker: (worker) =>
        new Promise((onFinishedLoading) => {
          worker.onmessage = (e) => {
            var d = e["data"];
            var cmd = d["cmd"];
            if (d["targetThread"] && d["targetThread"] != _pthread_self()) {
              var targetWorker = PThread.pthreads[d["targetThread"]];
              if (targetWorker) {
                targetWorker.postMessage(d, d["transferList"]);
              } else {
                err(
                  `Internal error! Worker sent a message "${cmd}" to target pthread ${d["targetThread"]}, but that thread no longer exists!`,
                );
              }
              return;
            }
            if (cmd === "checkMailbox") {
              checkMailbox();
            } else if (cmd === "spawnThread") {
              spawnThread(d);
            } else if (cmd === "cleanupThread") {
              cleanupThread(d["thread"]);
            } else if (cmd === "killThread") {
              killThread(d["thread"]);
            } else if (cmd === "cancelThread") {
              cancelThread(d["thread"]);
            } else if (cmd === "loaded") {
              worker.loaded = true;
              onFinishedLoading(worker);
            } else if (cmd === "alert") {
              alert(`Thread ${d["threadId"]}: ${d["text"]}`);
            } else if (d.target === "setimmediate") {
              worker.postMessage(d);
            } else if (cmd === "callHandler") {
              Module[d["handler"]](...d["args"]);
            } else if (cmd) {
              err(`worker sent an unknown command ${cmd}`);
            }
          };
          worker.onerror = (e) => {
            var message = "worker sent an error!";
            err(`${message} ${e.filename}:${e.lineno}: ${e.message}`);
            throw e;
          };
          var handlers = [];
          var knownHandlers = ["onExit", "onAbort", "print", "printErr"];
          for (var handler of knownHandlers) {
            if (Module.hasOwnProperty(handler)) {
              handlers.push(handler);
            }
          }
          worker.postMessage({
            cmd: "load",
            handlers: handlers,
            urlOrBlob: Module["mainScriptUrlOrBlob"],
            wasmMemory: wasmMemory,
            wasmModule: wasmModule,
          });
        }),
      loadWasmModuleToAllWorkers(onMaybeReady) {
        if (ENVIRONMENT_IS_PTHREAD) {
          return onMaybeReady();
        }
        let pthreadPoolReady = Promise.all(
          PThread.unusedWorkers.map(PThread.loadWasmModuleToWorker),
        );
        pthreadPoolReady.then(onMaybeReady);
      },
      allocateUnusedWorker() {
        var worker;
        var pthreadMainJs = locateFile("playps2.worker.js");
        worker = new Worker(pthreadMainJs, { type: "module" });
        PThread.unusedWorkers.push(worker);
      },
      getNewWorker() {
        if (PThread.unusedWorkers.length == 0) {
          PThread.allocateUnusedWorker();
          PThread.loadWasmModuleToWorker(PThread.unusedWorkers[0]);
        }
        return PThread.unusedWorkers.pop();
      },
    };
    Module["PThread"] = PThread;
    var callRuntimeCallbacks = (callbacks) => {
      while (callbacks.length > 0) {
        callbacks.shift()(Module);
      }
    };
    var establishStackSpace = () => {
      var pthread_ptr = _pthread_self();
      var stackHigh = GROWABLE_HEAP_U32()[(pthread_ptr + 52) >> 2];
      var stackSize = GROWABLE_HEAP_U32()[(pthread_ptr + 56) >> 2];
      var stackLow = stackHigh - stackSize;
      _emscripten_stack_set_limits(stackHigh, stackLow);
      stackRestore(stackHigh);
    };
    Module["establishStackSpace"] = establishStackSpace;
    function exitOnMainThread(returnCode) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(1, 0, returnCode);
      _exit(returnCode);
    }
    var wasmTableMirror = [];
    var wasmTable;
    var getWasmTableEntry = (funcPtr) => {
      var func = wasmTableMirror[funcPtr];
      if (!func) {
        if (funcPtr >= wasmTableMirror.length)
          wasmTableMirror.length = funcPtr + 1;
        wasmTableMirror[funcPtr] = func = wasmTable.get(funcPtr);
      }
      return func;
    };
    var invokeEntryPoint = (ptr, arg) => {
      var result = getWasmTableEntry(ptr)(arg);
      function finish(result) {
        if (keepRuntimeAlive()) {
          PThread.setExitStatus(result);
        } else {
          __emscripten_thread_exit(result);
        }
      }
      finish(result);
    };
    Module["invokeEntryPoint"] = invokeEntryPoint;
    var noExitRuntime = Module["noExitRuntime"] || true;
    var registerTLSInit = (tlsInitFunc) =>
      PThread.tlsInitFunctions.push(tlsInitFunc);
    var ___assert_fail = (condition, filename, line, func) => {
      abort(
        `Assertion failed: ${UTF8ToString(condition)}, at: ` +
          [
            filename ? UTF8ToString(filename) : "unknown filename",
            line,
            func ? UTF8ToString(func) : "unknown function",
          ],
      );
    };
    var exceptionCaught = [];
    var uncaughtExceptionCount = 0;
    var ___cxa_begin_catch = (ptr) => {
      var info = new ExceptionInfo(ptr);
      if (!info.get_caught()) {
        info.set_caught(true);
        uncaughtExceptionCount--;
      }
      info.set_rethrown(false);
      exceptionCaught.push(info);
      ___cxa_increment_exception_refcount(info.excPtr);
      return info.get_exception_ptr();
    };
    var ___cxa_current_primary_exception = () => {
      if (!exceptionCaught.length) {
        return 0;
      }
      var info = exceptionCaught[exceptionCaught.length - 1];
      ___cxa_increment_exception_refcount(info.excPtr);
      return info.excPtr;
    };
    var exceptionLast = 0;
    var ___cxa_end_catch = () => {
      _setThrew(0, 0);
      var info = exceptionCaught.pop();
      ___cxa_decrement_exception_refcount(info.excPtr);
      exceptionLast = 0;
    };
    function ExceptionInfo(excPtr) {
      this.excPtr = excPtr;
      this.ptr = excPtr - 24;
      this.set_type = function (type) {
        GROWABLE_HEAP_U32()[(this.ptr + 4) >> 2] = type;
      };
      this.get_type = function () {
        return GROWABLE_HEAP_U32()[(this.ptr + 4) >> 2];
      };
      this.set_destructor = function (destructor) {
        GROWABLE_HEAP_U32()[(this.ptr + 8) >> 2] = destructor;
      };
      this.get_destructor = function () {
        return GROWABLE_HEAP_U32()[(this.ptr + 8) >> 2];
      };
      this.set_caught = function (caught) {
        caught = caught ? 1 : 0;
        GROWABLE_HEAP_I8()[(this.ptr + 12) >> 0] = caught;
      };
      this.get_caught = function () {
        return GROWABLE_HEAP_I8()[(this.ptr + 12) >> 0] != 0;
      };
      this.set_rethrown = function (rethrown) {
        rethrown = rethrown ? 1 : 0;
        GROWABLE_HEAP_I8()[(this.ptr + 13) >> 0] = rethrown;
      };
      this.get_rethrown = function () {
        return GROWABLE_HEAP_I8()[(this.ptr + 13) >> 0] != 0;
      };
      this.init = function (type, destructor) {
        this.set_adjusted_ptr(0);
        this.set_type(type);
        this.set_destructor(destructor);
      };
      this.set_adjusted_ptr = function (adjustedPtr) {
        GROWABLE_HEAP_U32()[(this.ptr + 16) >> 2] = adjustedPtr;
      };
      this.get_adjusted_ptr = function () {
        return GROWABLE_HEAP_U32()[(this.ptr + 16) >> 2];
      };
      this.get_exception_ptr = function () {
        var isPointer = ___cxa_is_pointer_type(this.get_type());
        if (isPointer) {
          return GROWABLE_HEAP_U32()[this.excPtr >> 2];
        }
        var adjusted = this.get_adjusted_ptr();
        if (adjusted !== 0) return adjusted;
        return this.excPtr;
      };
    }
    var ___resumeException = (ptr) => {
      if (!exceptionLast) {
        exceptionLast = ptr;
      }
      throw exceptionLast;
    };
    var findMatchingCatch = (args) => {
      var thrown = exceptionLast;
      if (!thrown) {
        setTempRet0(0);
        return 0;
      }
      var info = new ExceptionInfo(thrown);
      info.set_adjusted_ptr(thrown);
      var thrownType = info.get_type();
      if (!thrownType) {
        setTempRet0(0);
        return thrown;
      }
      for (var arg in args) {
        var caughtType = args[arg];
        if (caughtType === 0 || caughtType === thrownType) {
          break;
        }
        var adjusted_ptr_addr = info.ptr + 16;
        if (___cxa_can_catch(caughtType, thrownType, adjusted_ptr_addr)) {
          setTempRet0(caughtType);
          return thrown;
        }
      }
      setTempRet0(thrownType);
      return thrown;
    };
    var ___cxa_find_matching_catch_2 = () => findMatchingCatch([]);
    var ___cxa_find_matching_catch_3 = (arg0) => findMatchingCatch([arg0]);
    var ___cxa_find_matching_catch_4 = (arg0, arg1) =>
      findMatchingCatch([arg0, arg1]);
    var ___cxa_find_matching_catch_5 = (arg0, arg1, arg2) =>
      findMatchingCatch([arg0, arg1, arg2]);
    var ___cxa_rethrow = () => {
      var info = exceptionCaught.pop();
      if (!info) {
        abort("no exception to throw");
      }
      var ptr = info.excPtr;
      if (!info.get_rethrown()) {
        exceptionCaught.push(info);
        info.set_rethrown(true);
        info.set_caught(false);
        uncaughtExceptionCount++;
      }
      exceptionLast = ptr;
      throw exceptionLast;
    };
    var ___cxa_rethrow_primary_exception = (ptr) => {
      if (!ptr) return;
      var info = new ExceptionInfo(ptr);
      exceptionCaught.push(info);
      info.set_rethrown(true);
      ___cxa_rethrow();
    };
    var ___cxa_throw = (ptr, type, destructor) => {
      var info = new ExceptionInfo(ptr);
      info.init(type, destructor);
      exceptionLast = ptr;
      uncaughtExceptionCount++;
      throw exceptionLast;
    };
    var ___cxa_uncaught_exceptions = () => uncaughtExceptionCount;
    var ___emscripten_init_main_thread_js = (tb) => {
      __emscripten_thread_init(
        tb,
        !ENVIRONMENT_IS_WORKER,
        1,
        !ENVIRONMENT_IS_WEB,
        65536,
        false,
      );
      PThread.threadInitTLS();
    };
    var ___emscripten_thread_cleanup = (thread) => {
      if (!ENVIRONMENT_IS_PTHREAD) cleanupThread(thread);
      else postMessage({ cmd: "cleanupThread", thread: thread });
    };
    function pthreadCreateProxied(pthread_ptr, attr, startRoutine, arg) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(2, 1, pthread_ptr, attr, startRoutine, arg);
      return ___pthread_create_js(pthread_ptr, attr, startRoutine, arg);
    }
    var ___pthread_create_js = (pthread_ptr, attr, startRoutine, arg) => {
      if (typeof SharedArrayBuffer == "undefined") {
        err(
          "Current environment does not support SharedArrayBuffer, pthreads are not available!",
        );
        return 6;
      }
      var transferList = [];
      var error = 0;
      if (ENVIRONMENT_IS_PTHREAD && (transferList.length === 0 || error)) {
        return pthreadCreateProxied(pthread_ptr, attr, startRoutine, arg);
      }
      if (error) return error;
      var threadParams = {
        startRoutine: startRoutine,
        pthread_ptr: pthread_ptr,
        arg: arg,
        transferList: transferList,
      };
      if (ENVIRONMENT_IS_PTHREAD) {
        threadParams.cmd = "spawnThread";
        postMessage(threadParams, transferList);
        return 0;
      }
      return spawnThread(threadParams);
    };
    var setErrNo = (value) => {
      GROWABLE_HEAP_I32()[___errno_location() >> 2] = value;
      return value;
    };
    function ___syscall_fcntl64(fd, cmd, varargs) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(3, 1, fd, cmd, varargs);
      SYSCALLS.varargs = varargs;
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        switch (cmd) {
          case 0: {
            var arg = SYSCALLS.get();
            if (arg < 0) {
              return -28;
            }
            while (FS.streams[arg]) {
              arg++;
            }
            var newStream;
            newStream = FS.createStream(stream, arg);
            return newStream.fd;
          }
          case 1:
          case 2:
            return 0;
          case 3:
            return stream.flags;
          case 4: {
            var arg = SYSCALLS.get();
            stream.flags |= arg;
            return 0;
          }
          case 5: {
            var arg = SYSCALLS.getp();
            var offset = 0;
            GROWABLE_HEAP_I16()[(arg + offset) >> 1] = 2;
            return 0;
          }
          case 6:
          case 7:
            return 0;
          case 16:
          case 8:
            return -28;
          case 9:
            setErrNo(28);
            return -1;
          default: {
            return -28;
          }
        }
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_fstat64(fd, buf) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(4, 1, fd, buf);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        return SYSCALLS.doStat(FS.stat, stream.path, buf);
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_statfs64(path, size, buf) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(6, 1, path, size, buf);
      try {
        path = SYSCALLS.getStr(path);
        GROWABLE_HEAP_I32()[(buf + 4) >> 2] = 4096;
        GROWABLE_HEAP_I32()[(buf + 40) >> 2] = 4096;
        GROWABLE_HEAP_I32()[(buf + 8) >> 2] = 1e6;
        GROWABLE_HEAP_I32()[(buf + 12) >> 2] = 5e5;
        GROWABLE_HEAP_I32()[(buf + 16) >> 2] = 5e5;
        GROWABLE_HEAP_I32()[(buf + 20) >> 2] = FS.nextInode;
        GROWABLE_HEAP_I32()[(buf + 24) >> 2] = 1e6;
        GROWABLE_HEAP_I32()[(buf + 28) >> 2] = 42;
        GROWABLE_HEAP_I32()[(buf + 44) >> 2] = 2;
        GROWABLE_HEAP_I32()[(buf + 36) >> 2] = 255;
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_fstatfs64(fd, size, buf) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(5, 1, fd, size, buf);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        return ___syscall_statfs64(0, size, buf);
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    var stringToUTF8 = (str, outPtr, maxBytesToWrite) =>
      stringToUTF8Array(str, GROWABLE_HEAP_U8(), outPtr, maxBytesToWrite);
    function ___syscall_getcwd(buf, size) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(7, 1, buf, size);
      try {
        if (size === 0) return -28;
        var cwd = FS.cwd();
        var cwdLengthInBytes = lengthBytesUTF8(cwd) + 1;
        if (size < cwdLengthInBytes) return -68;
        stringToUTF8(cwd, buf, size);
        return cwdLengthInBytes;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_getdents64(fd, dirp, count) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(8, 1, fd, dirp, count);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        stream.getdents ||= FS.readdir(stream.path);
        var struct_size = 280;
        var pos = 0;
        var off = FS.llseek(stream, 0, 1);
        var idx = Math.floor(off / struct_size);
        while (idx < stream.getdents.length && pos + struct_size <= count) {
          var id;
          var type;
          var name = stream.getdents[idx];
          if (name === ".") {
            id = stream.node.id;
            type = 4;
          } else if (name === "..") {
            var lookup = FS.lookupPath(stream.path, { parent: true });
            id = lookup.node.id;
            type = 4;
          } else {
            var child = FS.lookupNode(stream.node, name);
            id = child.id;
            type = FS.isChrdev(child.mode)
              ? 2
              : FS.isDir(child.mode)
                ? 4
                : FS.isLink(child.mode)
                  ? 10
                  : 8;
          }
          HEAP64[(dirp + pos) >> 3] = BigInt(id);
          HEAP64[(dirp + pos + 8) >> 3] = BigInt((idx + 1) * struct_size);
          GROWABLE_HEAP_I16()[(dirp + pos + 16) >> 1] = 280;
          GROWABLE_HEAP_I8()[(dirp + pos + 18) >> 0] = type;
          stringToUTF8(name, dirp + pos + 19, 256);
          pos += struct_size;
          idx += 1;
        }
        FS.llseek(stream, idx * struct_size, 0);
        return pos;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_ioctl(fd, op, varargs) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(9, 1, fd, op, varargs);
      SYSCALLS.varargs = varargs;
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        switch (op) {
          case 21509: {
            if (!stream.tty) return -59;
            return 0;
          }
          case 21505: {
            if (!stream.tty) return -59;
            if (stream.tty.ops.ioctl_tcgets) {
              var termios = stream.tty.ops.ioctl_tcgets(stream);
              var argp = SYSCALLS.getp();
              GROWABLE_HEAP_I32()[argp >> 2] = termios.c_iflag || 0;
              GROWABLE_HEAP_I32()[(argp + 4) >> 2] = termios.c_oflag || 0;
              GROWABLE_HEAP_I32()[(argp + 8) >> 2] = termios.c_cflag || 0;
              GROWABLE_HEAP_I32()[(argp + 12) >> 2] = termios.c_lflag || 0;
              for (var i = 0; i < 32; i++) {
                GROWABLE_HEAP_I8()[(argp + i + 17) >> 0] = termios.c_cc[i] || 0;
              }
              return 0;
            }
            return 0;
          }
          case 21510:
          case 21511:
          case 21512: {
            if (!stream.tty) return -59;
            return 0;
          }
          case 21506:
          case 21507:
          case 21508: {
            if (!stream.tty) return -59;
            if (stream.tty.ops.ioctl_tcsets) {
              var argp = SYSCALLS.getp();
              var c_iflag = GROWABLE_HEAP_I32()[argp >> 2];
              var c_oflag = GROWABLE_HEAP_I32()[(argp + 4) >> 2];
              var c_cflag = GROWABLE_HEAP_I32()[(argp + 8) >> 2];
              var c_lflag = GROWABLE_HEAP_I32()[(argp + 12) >> 2];
              var c_cc = [];
              for (var i = 0; i < 32; i++) {
                c_cc.push(GROWABLE_HEAP_I8()[(argp + i + 17) >> 0]);
              }
              return stream.tty.ops.ioctl_tcsets(stream.tty, op, {
                c_iflag: c_iflag,
                c_oflag: c_oflag,
                c_cflag: c_cflag,
                c_lflag: c_lflag,
                c_cc: c_cc,
              });
            }
            return 0;
          }
          case 21519: {
            if (!stream.tty) return -59;
            var argp = SYSCALLS.getp();
            GROWABLE_HEAP_I32()[argp >> 2] = 0;
            return 0;
          }
          case 21520: {
            if (!stream.tty) return -59;
            return -28;
          }
          case 21531: {
            var argp = SYSCALLS.getp();
            return FS.ioctl(stream, op, argp);
          }
          case 21523: {
            if (!stream.tty) return -59;
            if (stream.tty.ops.ioctl_tiocgwinsz) {
              var winsize = stream.tty.ops.ioctl_tiocgwinsz(stream.tty);
              var argp = SYSCALLS.getp();
              GROWABLE_HEAP_I16()[argp >> 1] = winsize[0];
              GROWABLE_HEAP_I16()[(argp + 2) >> 1] = winsize[1];
            }
            return 0;
          }
          case 21524: {
            if (!stream.tty) return -59;
            return 0;
          }
          case 21515: {
            if (!stream.tty) return -59;
            return 0;
          }
          default:
            return -28;
        }
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_lstat64(path, buf) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(10, 1, path, buf);
      try {
        path = SYSCALLS.getStr(path);
        return SYSCALLS.doStat(FS.lstat, path, buf);
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_mkdirat(dirfd, path, mode) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(11, 1, dirfd, path, mode);
      try {
        path = SYSCALLS.getStr(path);
        path = SYSCALLS.calculateAt(dirfd, path);
        path = PATH.normalize(path);
        if (path[path.length - 1] === "/")
          path = path.substr(0, path.length - 1);
        FS.mkdir(path, mode, 0);
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_newfstatat(dirfd, path, buf, flags) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(12, 1, dirfd, path, buf, flags);
      try {
        path = SYSCALLS.getStr(path);
        var nofollow = flags & 256;
        var allowEmpty = flags & 4096;
        flags = flags & ~6400;
        path = SYSCALLS.calculateAt(dirfd, path, allowEmpty);
        return SYSCALLS.doStat(nofollow ? FS.lstat : FS.stat, path, buf);
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_openat(dirfd, path, flags, varargs) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(13, 1, dirfd, path, flags, varargs);
      SYSCALLS.varargs = varargs;
      try {
        path = SYSCALLS.getStr(path);
        path = SYSCALLS.calculateAt(dirfd, path);
        var mode = varargs ? SYSCALLS.get() : 0;
        return FS.open(path, flags, mode).fd;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_readlinkat(dirfd, path, buf, bufsize) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(14, 1, dirfd, path, buf, bufsize);
      try {
        path = SYSCALLS.getStr(path);
        path = SYSCALLS.calculateAt(dirfd, path);
        if (bufsize <= 0) return -28;
        var ret = FS.readlink(path);
        var len = Math.min(bufsize, lengthBytesUTF8(ret));
        var endChar = GROWABLE_HEAP_I8()[buf + len];
        stringToUTF8(ret, buf, bufsize + 1);
        GROWABLE_HEAP_I8()[buf + len] = endChar;
        return len;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_renameat(olddirfd, oldpath, newdirfd, newpath) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(15, 1, olddirfd, oldpath, newdirfd, newpath);
      try {
        oldpath = SYSCALLS.getStr(oldpath);
        newpath = SYSCALLS.getStr(newpath);
        oldpath = SYSCALLS.calculateAt(olddirfd, oldpath);
        newpath = SYSCALLS.calculateAt(newdirfd, newpath);
        FS.rename(oldpath, newpath);
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_rmdir(path) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(16, 1, path);
      try {
        path = SYSCALLS.getStr(path);
        FS.rmdir(path);
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_stat64(path, buf) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(17, 1, path, buf);
      try {
        path = SYSCALLS.getStr(path);
        return SYSCALLS.doStat(FS.stat, path, buf);
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    function ___syscall_unlinkat(dirfd, path, flags) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(18, 1, dirfd, path, flags);
      try {
        path = SYSCALLS.getStr(path);
        path = SYSCALLS.calculateAt(dirfd, path);
        if (flags === 0) {
          FS.unlink(path);
        } else if (flags === 512) {
          FS.rmdir(path);
        } else {
          abort("Invalid flags passed to unlinkat");
        }
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return -e.errno;
      }
    }
    var embindRepr = (v) => {
      if (v === null) {
        return "null";
      }
      var t = typeof v;
      if (t === "object" || t === "array" || t === "function") {
        return v.toString();
      } else {
        return "" + v;
      }
    };
    var embind_init_charCodes = () => {
      var codes = new Array(256);
      for (var i = 0; i < 256; ++i) {
        codes[i] = String.fromCharCode(i);
      }
      embind_charCodes = codes;
    };
    var embind_charCodes;
    var readLatin1String = (ptr) => {
      var ret = "";
      var c = ptr;
      while (GROWABLE_HEAP_U8()[c]) {
        ret += embind_charCodes[GROWABLE_HEAP_U8()[c++]];
      }
      return ret;
    };
    var awaitingDependencies = {};
    var registeredTypes = {};
    var typeDependencies = {};
    var BindingError;
    var throwBindingError = (message) => {
      throw new BindingError(message);
    };
    var InternalError;
    var throwInternalError = (message) => {
      throw new InternalError(message);
    };
    var whenDependentTypesAreResolved = (
      myTypes,
      dependentTypes,
      getTypeConverters,
    ) => {
      myTypes.forEach(function (type) {
        typeDependencies[type] = dependentTypes;
      });
      function onComplete(typeConverters) {
        var myTypeConverters = getTypeConverters(typeConverters);
        if (myTypeConverters.length !== myTypes.length) {
          throwInternalError("Mismatched type converter count");
        }
        for (var i = 0; i < myTypes.length; ++i) {
          registerType(myTypes[i], myTypeConverters[i]);
        }
      }
      var typeConverters = new Array(dependentTypes.length);
      var unregisteredTypes = [];
      var registered = 0;
      dependentTypes.forEach((dt, i) => {
        if (registeredTypes.hasOwnProperty(dt)) {
          typeConverters[i] = registeredTypes[dt];
        } else {
          unregisteredTypes.push(dt);
          if (!awaitingDependencies.hasOwnProperty(dt)) {
            awaitingDependencies[dt] = [];
          }
          awaitingDependencies[dt].push(() => {
            typeConverters[i] = registeredTypes[dt];
            ++registered;
            if (registered === unregisteredTypes.length) {
              onComplete(typeConverters);
            }
          });
        }
      });
      if (0 === unregisteredTypes.length) {
        onComplete(typeConverters);
      }
    };
    function sharedRegisterType(rawType, registeredInstance, options = {}) {
      var name = registeredInstance.name;
      if (!rawType) {
        throwBindingError(
          `type "${name}" must have a positive integer typeid pointer`,
        );
      }
      if (registeredTypes.hasOwnProperty(rawType)) {
        if (options.ignoreDuplicateRegistrations) {
          return;
        } else {
          throwBindingError(`Cannot register type '${name}' twice`);
        }
      }
      registeredTypes[rawType] = registeredInstance;
      delete typeDependencies[rawType];
      if (awaitingDependencies.hasOwnProperty(rawType)) {
        var callbacks = awaitingDependencies[rawType];
        delete awaitingDependencies[rawType];
        callbacks.forEach((cb) => cb());
      }
    }
    function registerType(rawType, registeredInstance, options = {}) {
      if (!("argPackAdvance" in registeredInstance)) {
        throw new TypeError(
          "registerType registeredInstance requires argPackAdvance",
        );
      }
      return sharedRegisterType(rawType, registeredInstance, options);
    }
    var integerReadValueFromPointer = (name, width, signed) => {
      switch (width) {
        case 1:
          return signed
            ? (pointer) => GROWABLE_HEAP_I8()[pointer >> 0]
            : (pointer) => GROWABLE_HEAP_U8()[pointer >> 0];
        case 2:
          return signed
            ? (pointer) => GROWABLE_HEAP_I16()[pointer >> 1]
            : (pointer) => GROWABLE_HEAP_U16()[pointer >> 1];
        case 4:
          return signed
            ? (pointer) => GROWABLE_HEAP_I32()[pointer >> 2]
            : (pointer) => GROWABLE_HEAP_U32()[pointer >> 2];
        case 8:
          return signed
            ? (pointer) => HEAP64[pointer >> 3]
            : (pointer) => HEAPU64[pointer >> 3];
        default:
          throw new TypeError(`invalid integer width (${width}): ${name}`);
      }
    };
    var __embind_register_bigint = (
      primitiveType,
      name,
      size,
      minRange,
      maxRange,
    ) => {
      name = readLatin1String(name);
      var isUnsignedType = name.indexOf("u") != -1;
      if (isUnsignedType) {
        maxRange = (1n << 64n) - 1n;
      }
      registerType(primitiveType, {
        name: name,
        fromWireType: (value) => value,
        toWireType: function (destructors, value) {
          if (typeof value != "bigint" && typeof value != "number") {
            throw new TypeError(
              `Cannot convert "${embindRepr(value)}" to ${this.name}`,
            );
          }
          if (value < minRange || value > maxRange) {
            throw new TypeError(
              `Passing a number "${embindRepr(value)}" from JS side to C/C++ side to an argument of type "${name}", which is outside the valid range [${minRange}, ${maxRange}]!`,
            );
          }
          return value;
        },
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: integerReadValueFromPointer(
          name,
          size,
          !isUnsignedType,
        ),
        destructorFunction: null,
      });
    };
    var GenericWireTypeSize = 8;
    var __embind_register_bool = (rawType, name, trueValue, falseValue) => {
      name = readLatin1String(name);
      registerType(rawType, {
        name: name,
        fromWireType: function (wt) {
          return !!wt;
        },
        toWireType: function (destructors, o) {
          return o ? trueValue : falseValue;
        },
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: function (pointer) {
          return this["fromWireType"](GROWABLE_HEAP_U8()[pointer]);
        },
        destructorFunction: null,
      });
    };
    function handleAllocatorInit() {
      Object.assign(HandleAllocator.prototype, {
        get(id) {
          return this.allocated[id];
        },
        has(id) {
          return this.allocated[id] !== undefined;
        },
        allocate(handle) {
          var id = this.freelist.pop() || this.allocated.length;
          this.allocated[id] = handle;
          return id;
        },
        free(id) {
          this.allocated[id] = undefined;
          this.freelist.push(id);
        },
      });
    }
    function HandleAllocator() {
      this.allocated = [undefined];
      this.freelist = [];
    }
    var emval_handles = new HandleAllocator();
    var __emval_decref = (handle) => {
      if (
        handle >= emval_handles.reserved &&
        0 === --emval_handles.get(handle).refcount
      ) {
        emval_handles.free(handle);
      }
    };
    var count_emval_handles = () => {
      var count = 0;
      for (
        var i = emval_handles.reserved;
        i < emval_handles.allocated.length;
        ++i
      ) {
        if (emval_handles.allocated[i] !== undefined) {
          ++count;
        }
      }
      return count;
    };
    var init_emval = () => {
      emval_handles.allocated.push(
        { value: undefined },
        { value: null },
        { value: true },
        { value: false },
      );
      emval_handles.reserved = emval_handles.allocated.length;
      Module["count_emval_handles"] = count_emval_handles;
    };
    var Emval = {
      toValue: (handle) => {
        if (!handle) {
          throwBindingError("Cannot use deleted val. handle = " + handle);
        }
        return emval_handles.get(handle).value;
      },
      toHandle: (value) => {
        switch (value) {
          case undefined:
            return 1;
          case null:
            return 2;
          case true:
            return 3;
          case false:
            return 4;
          default: {
            return emval_handles.allocate({ refcount: 1, value: value });
          }
        }
      },
    };
    function simpleReadValueFromPointer(pointer) {
      return this["fromWireType"](GROWABLE_HEAP_I32()[pointer >> 2]);
    }
    var __embind_register_emval = (rawType, name) => {
      name = readLatin1String(name);
      registerType(rawType, {
        name: name,
        fromWireType: (handle) => {
          var rv = Emval.toValue(handle);
          __emval_decref(handle);
          return rv;
        },
        toWireType: (destructors, value) => Emval.toHandle(value),
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: simpleReadValueFromPointer,
        destructorFunction: null,
      });
    };
    var floatReadValueFromPointer = (name, width) => {
      switch (width) {
        case 4:
          return function (pointer) {
            return this["fromWireType"](GROWABLE_HEAP_F32()[pointer >> 2]);
          };
        case 8:
          return function (pointer) {
            return this["fromWireType"](GROWABLE_HEAP_F64()[pointer >> 3]);
          };
        default:
          throw new TypeError(`invalid float width (${width}): ${name}`);
      }
    };
    var __embind_register_float = (rawType, name, size) => {
      name = readLatin1String(name);
      registerType(rawType, {
        name: name,
        fromWireType: (value) => value,
        toWireType: (destructors, value) => value,
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: floatReadValueFromPointer(name, size),
        destructorFunction: null,
      });
    };
    var createNamedFunction = (name, body) =>
      Object.defineProperty(body, "name", { value: name });
    var runDestructors = (destructors) => {
      while (destructors.length) {
        var ptr = destructors.pop();
        var del = destructors.pop();
        del(ptr);
      }
    };
    function usesDestructorStack(argTypes) {
      for (var i = 1; i < argTypes.length; ++i) {
        if (
          argTypes[i] !== null &&
          argTypes[i].destructorFunction === undefined
        ) {
          return true;
        }
      }
      return false;
    }
    function newFunc(constructor, argumentList) {
      if (!(constructor instanceof Function)) {
        throw new TypeError(
          `new_ called with constructor type ${typeof constructor} which is not a function`,
        );
      }
      var dummy = createNamedFunction(
        constructor.name || "unknownFunctionName",
        function () {},
      );
      dummy.prototype = constructor.prototype;
      var obj = new dummy();
      var r = constructor.apply(obj, argumentList);
      return r instanceof Object ? r : obj;
    }
    function createJsInvoker(
      humanName,
      argTypes,
      isClassMethodFunc,
      returns,
      isAsync,
    ) {
      var needsDestructorStack = usesDestructorStack(argTypes);
      var argCount = argTypes.length;
      var argsList = "";
      var argsListWired = "";
      for (var i = 0; i < argCount - 2; ++i) {
        argsList += (i !== 0 ? ", " : "") + "arg" + i;
        argsListWired += (i !== 0 ? ", " : "") + "arg" + i + "Wired";
      }
      var invokerFnBody = `\n        return function (${argsList}) {\n        if (arguments.length !== ${argCount - 2}) {\n          throwBindingError('function ${humanName} called with ' + arguments.length + ' arguments, expected ${argCount - 2}');\n        }`;
      if (needsDestructorStack) {
        invokerFnBody += "var destructors = [];\n";
      }
      var dtorStack = needsDestructorStack ? "destructors" : "null";
      var args1 = [
        "throwBindingError",
        "invoker",
        "fn",
        "runDestructors",
        "retType",
        "classParam",
      ];
      if (isClassMethodFunc) {
        invokerFnBody +=
          "var thisWired = classParam['toWireType'](" +
          dtorStack +
          ", this);\n";
      }
      for (var i = 0; i < argCount - 2; ++i) {
        invokerFnBody +=
          "var arg" +
          i +
          "Wired = argType" +
          i +
          "['toWireType'](" +
          dtorStack +
          ", arg" +
          i +
          "); // " +
          argTypes[i + 2].name +
          "\n";
        args1.push("argType" + i);
      }
      if (isClassMethodFunc) {
        argsListWired =
          "thisWired" + (argsListWired.length > 0 ? ", " : "") + argsListWired;
      }
      invokerFnBody +=
        (returns || isAsync ? "var rv = " : "") +
        "invoker(fn" +
        (argsListWired.length > 0 ? ", " : "") +
        argsListWired +
        ");\n";
      if (needsDestructorStack) {
        invokerFnBody += "runDestructors(destructors);\n";
      } else {
        for (var i = isClassMethodFunc ? 1 : 2; i < argTypes.length; ++i) {
          var paramName = i === 1 ? "thisWired" : "arg" + (i - 2) + "Wired";
          if (argTypes[i].destructorFunction !== null) {
            invokerFnBody +=
              paramName +
              "_dtor(" +
              paramName +
              "); // " +
              argTypes[i].name +
              "\n";
            args1.push(paramName + "_dtor");
          }
        }
      }
      if (returns) {
        invokerFnBody +=
          "var ret = retType['fromWireType'](rv);\n" + "return ret;\n";
      } else {
      }
      invokerFnBody += "}\n";
      return [args1, invokerFnBody];
    }
    function craftInvokerFunction(
      humanName,
      argTypes,
      classType,
      cppInvokerFunc,
      cppTargetFunc,
      isAsync,
    ) {
      var argCount = argTypes.length;
      if (argCount < 2) {
        throwBindingError(
          "argTypes array size mismatch! Must at least get return value and 'this' types!",
        );
      }
      var isClassMethodFunc = argTypes[1] !== null && classType !== null;
      var needsDestructorStack = usesDestructorStack(argTypes);
      var returns = argTypes[0].name !== "void";
      var closureArgs = [
        throwBindingError,
        cppInvokerFunc,
        cppTargetFunc,
        runDestructors,
        argTypes[0],
        argTypes[1],
      ];
      for (var i = 0; i < argCount - 2; ++i) {
        closureArgs.push(argTypes[i + 2]);
      }
      if (!needsDestructorStack) {
        for (var i = isClassMethodFunc ? 1 : 2; i < argTypes.length; ++i) {
          if (argTypes[i].destructorFunction !== null) {
            closureArgs.push(argTypes[i].destructorFunction);
          }
        }
      }
      let [args, invokerFnBody] = createJsInvoker(
        humanName,
        argTypes,
        isClassMethodFunc,
        returns,
        isAsync,
      );
      args.push(invokerFnBody);
      var invokerFn = newFunc(Function, args).apply(null, closureArgs);
      return createNamedFunction(humanName, invokerFn);
    }
    var ensureOverloadTable = (proto, methodName, humanName) => {
      if (undefined === proto[methodName].overloadTable) {
        var prevFunc = proto[methodName];
        proto[methodName] = function () {
          if (
            !proto[methodName].overloadTable.hasOwnProperty(arguments.length)
          ) {
            throwBindingError(
              `Function '${humanName}' called with an invalid number of arguments (${arguments.length}) - expects one of (${proto[methodName].overloadTable})!`,
            );
          }
          return proto[methodName].overloadTable[arguments.length].apply(
            this,
            arguments,
          );
        };
        proto[methodName].overloadTable = [];
        proto[methodName].overloadTable[prevFunc.argCount] = prevFunc;
      }
    };
    var exposePublicSymbol = (name, value, numArguments) => {
      if (Module.hasOwnProperty(name)) {
        if (
          undefined === numArguments ||
          (undefined !== Module[name].overloadTable &&
            undefined !== Module[name].overloadTable[numArguments])
        ) {
          throwBindingError(`Cannot register public name '${name}' twice`);
        }
        ensureOverloadTable(Module, name, name);
        if (Module.hasOwnProperty(numArguments)) {
          throwBindingError(
            `Cannot register multiple overloads of a function with the same number of arguments (${numArguments})!`,
          );
        }
        Module[name].overloadTable[numArguments] = value;
      } else {
        Module[name] = value;
        if (undefined !== numArguments) {
          Module[name].numArguments = numArguments;
        }
      }
    };
    var heap32VectorToArray = (count, firstElement) => {
      var array = [];
      for (var i = 0; i < count; i++) {
        array.push(GROWABLE_HEAP_U32()[(firstElement + i * 4) >> 2]);
      }
      return array;
    };
    var replacePublicSymbol = (name, value, numArguments) => {
      if (!Module.hasOwnProperty(name)) {
        throwInternalError("Replacing nonexistant public symbol");
      }
      if (
        undefined !== Module[name].overloadTable &&
        undefined !== numArguments
      ) {
        Module[name].overloadTable[numArguments] = value;
      } else {
        Module[name] = value;
        Module[name].argCount = numArguments;
      }
    };
    var embind__requireFunction = (signature, rawFunction) => {
      signature = readLatin1String(signature);
      function makeDynCaller() {
        return getWasmTableEntry(rawFunction);
      }
      var fp = makeDynCaller();
      if (typeof fp != "function") {
        throwBindingError(
          `unknown function pointer with signature ${signature}: ${rawFunction}`,
        );
      }
      return fp;
    };
    var extendError = (baseErrorType, errorName) => {
      var errorClass = createNamedFunction(errorName, function (message) {
        this.name = errorName;
        this.message = message;
        var stack = new Error(message).stack;
        if (stack !== undefined) {
          this.stack =
            this.toString() + "\n" + stack.replace(/^Error(:[^\n]*)?\n/, "");
        }
      });
      errorClass.prototype = Object.create(baseErrorType.prototype);
      errorClass.prototype.constructor = errorClass;
      errorClass.prototype.toString = function () {
        if (this.message === undefined) {
          return this.name;
        } else {
          return `${this.name}: ${this.message}`;
        }
      };
      return errorClass;
    };
    var UnboundTypeError;
    var getTypeName = (type) => {
      var ptr = ___getTypeName(type);
      var rv = readLatin1String(ptr);
      _free(ptr);
      return rv;
    };
    var throwUnboundTypeError = (message, types) => {
      var unboundTypes = [];
      var seen = {};
      function visit(type) {
        if (seen[type]) {
          return;
        }
        if (registeredTypes[type]) {
          return;
        }
        if (typeDependencies[type]) {
          typeDependencies[type].forEach(visit);
          return;
        }
        unboundTypes.push(type);
        seen[type] = true;
      }
      types.forEach(visit);
      throw new UnboundTypeError(
        `${message}: ` + unboundTypes.map(getTypeName).join([", "]),
      );
    };
    var getFunctionName = (signature) => {
      signature = signature.trim();
      const argsIndex = signature.indexOf("(");
      if (argsIndex !== -1) {
        return signature.substr(0, argsIndex);
      } else {
        return signature;
      }
    };
    var __embind_register_function = (
      name,
      argCount,
      rawArgTypesAddr,
      signature,
      rawInvoker,
      fn,
      isAsync,
    ) => {
      var argTypes = heap32VectorToArray(argCount, rawArgTypesAddr);
      name = readLatin1String(name);
      name = getFunctionName(name);
      rawInvoker = embind__requireFunction(signature, rawInvoker);
      exposePublicSymbol(
        name,
        function () {
          throwUnboundTypeError(
            `Cannot call ${name} due to unbound types`,
            argTypes,
          );
        },
        argCount - 1,
      );
      whenDependentTypesAreResolved([], argTypes, function (argTypes) {
        var invokerArgsArray = [argTypes[0], null].concat(argTypes.slice(1));
        replacePublicSymbol(
          name,
          craftInvokerFunction(
            name,
            invokerArgsArray,
            null,
            rawInvoker,
            fn,
            isAsync,
          ),
          argCount - 1,
        );
        return [];
      });
    };
    var __embind_register_integer = (
      primitiveType,
      name,
      size,
      minRange,
      maxRange,
    ) => {
      name = readLatin1String(name);
      if (maxRange === -1) {
        maxRange = 4294967295;
      }
      var fromWireType = (value) => value;
      if (minRange === 0) {
        var bitshift = 32 - 8 * size;
        fromWireType = (value) => (value << bitshift) >>> bitshift;
      }
      var isUnsignedType = name.includes("unsigned");
      var checkAssertions = (value, toTypeName) => {};
      var toWireType;
      if (isUnsignedType) {
        toWireType = function (destructors, value) {
          checkAssertions(value, this.name);
          return value >>> 0;
        };
      } else {
        toWireType = function (destructors, value) {
          checkAssertions(value, this.name);
          return value;
        };
      }
      registerType(primitiveType, {
        name: name,
        fromWireType: fromWireType,
        toWireType: toWireType,
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: integerReadValueFromPointer(
          name,
          size,
          minRange !== 0,
        ),
        destructorFunction: null,
      });
    };
    var __embind_register_memory_view = (rawType, dataTypeIndex, name) => {
      var typeMapping = [
        Int8Array,
        Uint8Array,
        Int16Array,
        Uint16Array,
        Int32Array,
        Uint32Array,
        Float32Array,
        Float64Array,
        BigInt64Array,
        BigUint64Array,
      ];
      var TA = typeMapping[dataTypeIndex];
      function decodeMemoryView(handle) {
        var size = GROWABLE_HEAP_U32()[handle >> 2];
        var data = GROWABLE_HEAP_U32()[(handle + 4) >> 2];
        return new TA(GROWABLE_HEAP_I8().buffer, data, size);
      }
      name = readLatin1String(name);
      registerType(
        rawType,
        {
          name: name,
          fromWireType: decodeMemoryView,
          argPackAdvance: GenericWireTypeSize,
          readValueFromPointer: decodeMemoryView,
        },
        { ignoreDuplicateRegistrations: true },
      );
    };
    function readPointer(pointer) {
      return this["fromWireType"](GROWABLE_HEAP_U32()[pointer >> 2]);
    }
    var __embind_register_std_string = (rawType, name) => {
      name = readLatin1String(name);
      var stdStringIsUTF8 = name === "std::string";
      registerType(rawType, {
        name: name,
        fromWireType(value) {
          var length = GROWABLE_HEAP_U32()[value >> 2];
          var payload = value + 4;
          var str;
          if (stdStringIsUTF8) {
            var decodeStartPtr = payload;
            for (var i = 0; i <= length; ++i) {
              var currentBytePtr = payload + i;
              if (i == length || GROWABLE_HEAP_U8()[currentBytePtr] == 0) {
                var maxRead = currentBytePtr - decodeStartPtr;
                var stringSegment = UTF8ToString(decodeStartPtr, maxRead);
                if (str === undefined) {
                  str = stringSegment;
                } else {
                  str += String.fromCharCode(0);
                  str += stringSegment;
                }
                decodeStartPtr = currentBytePtr + 1;
              }
            }
          } else {
            var a = new Array(length);
            for (var i = 0; i < length; ++i) {
              a[i] = String.fromCharCode(GROWABLE_HEAP_U8()[payload + i]);
            }
            str = a.join("");
          }
          _free(value);
          return str;
        },
        toWireType(destructors, value) {
          if (value instanceof ArrayBuffer) {
            value = new Uint8Array(value);
          }
          var length;
          var valueIsOfTypeString = typeof value == "string";
          if (
            !(
              valueIsOfTypeString ||
              value instanceof Uint8Array ||
              value instanceof Uint8ClampedArray ||
              value instanceof Int8Array
            )
          ) {
            throwBindingError("Cannot pass non-string to std::string");
          }
          if (stdStringIsUTF8 && valueIsOfTypeString) {
            length = lengthBytesUTF8(value);
          } else {
            length = value.length;
          }
          var base = _malloc(4 + length + 1);
          var ptr = base + 4;
          GROWABLE_HEAP_U32()[base >> 2] = length;
          if (stdStringIsUTF8 && valueIsOfTypeString) {
            stringToUTF8(value, ptr, length + 1);
          } else {
            if (valueIsOfTypeString) {
              for (var i = 0; i < length; ++i) {
                var charCode = value.charCodeAt(i);
                if (charCode > 255) {
                  _free(ptr);
                  throwBindingError(
                    "String has UTF-16 code units that do not fit in 8 bits",
                  );
                }
                GROWABLE_HEAP_U8()[ptr + i] = charCode;
              }
            } else {
              for (var i = 0; i < length; ++i) {
                GROWABLE_HEAP_U8()[ptr + i] = value[i];
              }
            }
          }
          if (destructors !== null) {
            destructors.push(_free, base);
          }
          return base;
        },
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: readPointer,
        destructorFunction(ptr) {
          _free(ptr);
        },
      });
    };
    var UTF16Decoder =
      typeof TextDecoder != "undefined"
        ? new TextDecoder("utf-16le")
        : undefined;
    var UTF16ToString = (ptr, maxBytesToRead) => {
      var endPtr = ptr;
      var idx = endPtr >> 1;
      var maxIdx = idx + maxBytesToRead / 2;
      while (!(idx >= maxIdx) && GROWABLE_HEAP_U16()[idx]) ++idx;
      endPtr = idx << 1;
      if (endPtr - ptr > 32 && UTF16Decoder)
        return UTF16Decoder.decode(GROWABLE_HEAP_U8().slice(ptr, endPtr));
      var str = "";
      for (var i = 0; !(i >= maxBytesToRead / 2); ++i) {
        var codeUnit = GROWABLE_HEAP_I16()[(ptr + i * 2) >> 1];
        if (codeUnit == 0) break;
        str += String.fromCharCode(codeUnit);
      }
      return str;
    };
    var stringToUTF16 = (str, outPtr, maxBytesToWrite) => {
      maxBytesToWrite ??= 2147483647;
      if (maxBytesToWrite < 2) return 0;
      maxBytesToWrite -= 2;
      var startPtr = outPtr;
      var numCharsToWrite =
        maxBytesToWrite < str.length * 2 ? maxBytesToWrite / 2 : str.length;
      for (var i = 0; i < numCharsToWrite; ++i) {
        var codeUnit = str.charCodeAt(i);
        GROWABLE_HEAP_I16()[outPtr >> 1] = codeUnit;
        outPtr += 2;
      }
      GROWABLE_HEAP_I16()[outPtr >> 1] = 0;
      return outPtr - startPtr;
    };
    var lengthBytesUTF16 = (str) => str.length * 2;
    var UTF32ToString = (ptr, maxBytesToRead) => {
      var i = 0;
      var str = "";
      while (!(i >= maxBytesToRead / 4)) {
        var utf32 = GROWABLE_HEAP_I32()[(ptr + i * 4) >> 2];
        if (utf32 == 0) break;
        ++i;
        if (utf32 >= 65536) {
          var ch = utf32 - 65536;
          str += String.fromCharCode(55296 | (ch >> 10), 56320 | (ch & 1023));
        } else {
          str += String.fromCharCode(utf32);
        }
      }
      return str;
    };
    var stringToUTF32 = (str, outPtr, maxBytesToWrite) => {
      maxBytesToWrite ??= 2147483647;
      if (maxBytesToWrite < 4) return 0;
      var startPtr = outPtr;
      var endPtr = startPtr + maxBytesToWrite - 4;
      for (var i = 0; i < str.length; ++i) {
        var codeUnit = str.charCodeAt(i);
        if (codeUnit >= 55296 && codeUnit <= 57343) {
          var trailSurrogate = str.charCodeAt(++i);
          codeUnit =
            (65536 + ((codeUnit & 1023) << 10)) | (trailSurrogate & 1023);
        }
        GROWABLE_HEAP_I32()[outPtr >> 2] = codeUnit;
        outPtr += 4;
        if (outPtr + 4 > endPtr) break;
      }
      GROWABLE_HEAP_I32()[outPtr >> 2] = 0;
      return outPtr - startPtr;
    };
    var lengthBytesUTF32 = (str) => {
      var len = 0;
      for (var i = 0; i < str.length; ++i) {
        var codeUnit = str.charCodeAt(i);
        if (codeUnit >= 55296 && codeUnit <= 57343) ++i;
        len += 4;
      }
      return len;
    };
    var __embind_register_std_wstring = (rawType, charSize, name) => {
      name = readLatin1String(name);
      var decodeString, encodeString, getHeap, lengthBytesUTF, shift;
      if (charSize === 2) {
        decodeString = UTF16ToString;
        encodeString = stringToUTF16;
        lengthBytesUTF = lengthBytesUTF16;
        getHeap = () => GROWABLE_HEAP_U16();
        shift = 1;
      } else if (charSize === 4) {
        decodeString = UTF32ToString;
        encodeString = stringToUTF32;
        lengthBytesUTF = lengthBytesUTF32;
        getHeap = () => GROWABLE_HEAP_U32();
        shift = 2;
      }
      registerType(rawType, {
        name: name,
        fromWireType: (value) => {
          var length = GROWABLE_HEAP_U32()[value >> 2];
          var HEAP = getHeap();
          var str;
          var decodeStartPtr = value + 4;
          for (var i = 0; i <= length; ++i) {
            var currentBytePtr = value + 4 + i * charSize;
            if (i == length || HEAP[currentBytePtr >> shift] == 0) {
              var maxReadBytes = currentBytePtr - decodeStartPtr;
              var stringSegment = decodeString(decodeStartPtr, maxReadBytes);
              if (str === undefined) {
                str = stringSegment;
              } else {
                str += String.fromCharCode(0);
                str += stringSegment;
              }
              decodeStartPtr = currentBytePtr + charSize;
            }
          }
          _free(value);
          return str;
        },
        toWireType: (destructors, value) => {
          if (!(typeof value == "string")) {
            throwBindingError(
              `Cannot pass non-string to C++ string type ${name}`,
            );
          }
          var length = lengthBytesUTF(value);
          var ptr = _malloc(4 + length + charSize);
          GROWABLE_HEAP_U32()[ptr >> 2] = length >> shift;
          encodeString(value, ptr + 4, length + charSize);
          if (destructors !== null) {
            destructors.push(_free, ptr);
          }
          return ptr;
        },
        argPackAdvance: GenericWireTypeSize,
        readValueFromPointer: simpleReadValueFromPointer,
        destructorFunction(ptr) {
          _free(ptr);
        },
      });
    };
    var __embind_register_void = (rawType, name) => {
      name = readLatin1String(name);
      registerType(rawType, {
        isVoid: true,
        name: name,
        argPackAdvance: 0,
        fromWireType: () => undefined,
        toWireType: (destructors, o) => undefined,
      });
    };
    var nowIsMonotonic = 1;
    var __emscripten_get_now_is_monotonic = () => nowIsMonotonic;
    var maybeExit = () => {
      if (!keepRuntimeAlive()) {
        try {
          if (ENVIRONMENT_IS_PTHREAD) __emscripten_thread_exit(EXITSTATUS);
          else _exit(EXITSTATUS);
        } catch (e) {
          handleException(e);
        }
      }
    };
    var callUserCallback = (func) => {
      if (ABORT) {
        return;
      }
      try {
        func();
        maybeExit();
      } catch (e) {
        handleException(e);
      }
    };
    var __emscripten_thread_mailbox_await = (pthread_ptr) => {
      if (typeof Atomics.waitAsync === "function") {
        var wait = Atomics.waitAsync(
          GROWABLE_HEAP_I32(),
          pthread_ptr >> 2,
          pthread_ptr,
        );
        wait.value.then(checkMailbox);
        var waitingAsync = pthread_ptr + 128;
        Atomics.store(GROWABLE_HEAP_I32(), waitingAsync >> 2, 1);
      }
    };
    Module["__emscripten_thread_mailbox_await"] =
      __emscripten_thread_mailbox_await;
    var checkMailbox = () => {
      var pthread_ptr = _pthread_self();
      if (pthread_ptr) {
        __emscripten_thread_mailbox_await(pthread_ptr);
        callUserCallback(__emscripten_check_mailbox);
      }
    };
    Module["checkMailbox"] = checkMailbox;
    var __emscripten_notify_mailbox_postmessage = (
      targetThreadId,
      currThreadId,
      mainThreadId,
    ) => {
      if (targetThreadId == currThreadId) {
        setTimeout(() => checkMailbox());
      } else if (ENVIRONMENT_IS_PTHREAD) {
        postMessage({ targetThread: targetThreadId, cmd: "checkMailbox" });
      } else {
        var worker = PThread.pthreads[targetThreadId];
        if (!worker) {
          return;
        }
        worker.postMessage({ cmd: "checkMailbox" });
      }
    };
    var webgl_enable_ANGLE_instanced_arrays = (ctx) => {
      var ext = ctx.getExtension("ANGLE_instanced_arrays");
      if (ext) {
        ctx["vertexAttribDivisor"] = (index, divisor) =>
          ext["vertexAttribDivisorANGLE"](index, divisor);
        ctx["drawArraysInstanced"] = (mode, first, count, primcount) =>
          ext["drawArraysInstancedANGLE"](mode, first, count, primcount);
        ctx["drawElementsInstanced"] = (
          mode,
          count,
          type,
          indices,
          primcount,
        ) =>
          ext["drawElementsInstancedANGLE"](
            mode,
            count,
            type,
            indices,
            primcount,
          );
        return 1;
      }
    };
    var webgl_enable_OES_vertex_array_object = (ctx) => {
      var ext = ctx.getExtension("OES_vertex_array_object");
      if (ext) {
        ctx["createVertexArray"] = () => ext["createVertexArrayOES"]();
        ctx["deleteVertexArray"] = (vao) => ext["deleteVertexArrayOES"](vao);
        ctx["bindVertexArray"] = (vao) => ext["bindVertexArrayOES"](vao);
        ctx["isVertexArray"] = (vao) => ext["isVertexArrayOES"](vao);
        return 1;
      }
    };
    var webgl_enable_WEBGL_draw_buffers = (ctx) => {
      var ext = ctx.getExtension("WEBGL_draw_buffers");
      if (ext) {
        ctx["drawBuffers"] = (n, bufs) => ext["drawBuffersWEBGL"](n, bufs);
        return 1;
      }
    };
    var webgl_enable_WEBGL_draw_instanced_base_vertex_base_instance = (ctx) =>
      !!(ctx.dibvbi = ctx.getExtension(
        "WEBGL_draw_instanced_base_vertex_base_instance",
      ));
    var webgl_enable_WEBGL_multi_draw_instanced_base_vertex_base_instance = (
      ctx,
    ) =>
      !!(ctx.mdibvbi = ctx.getExtension(
        "WEBGL_multi_draw_instanced_base_vertex_base_instance",
      ));
    var webgl_enable_WEBGL_multi_draw = (ctx) =>
      !!(ctx.multiDrawWebgl = ctx.getExtension("WEBGL_multi_draw"));
    var GL = {
      counter: 1,
      buffers: [],
      programs: [],
      framebuffers: [],
      renderbuffers: [],
      textures: [],
      shaders: [],
      vaos: [],
      contexts: {},
      offscreenCanvases: {},
      queries: [],
      samplers: [],
      transformFeedbacks: [],
      syncs: [],
      stringCache: {},
      stringiCache: {},
      unpackAlignment: 4,
      recordError: function recordError(errorCode) {
        if (!GL.lastError) {
          GL.lastError = errorCode;
        }
      },
      getNewId: (table) => {
        var ret = GL.counter++;
        for (var i = table.length; i < ret; i++) {
          table[i] = null;
        }
        return ret;
      },
      getSource: (shader, count, string, length) => {
        var source = "";
        for (var i = 0; i < count; ++i) {
          var len = length ? GROWABLE_HEAP_I32()[(length + i * 4) >> 2] : -1;
          source += UTF8ToString(
            GROWABLE_HEAP_I32()[(string + i * 4) >> 2],
            len < 0 ? undefined : len,
          );
        }
        return source;
      },
      createContext: (canvas, webGLContextAttributes) => {
        if (webGLContextAttributes.renderViaOffscreenBackBuffer)
          webGLContextAttributes["preserveDrawingBuffer"] = true;
        if (!canvas.getContextSafariWebGL2Fixed) {
          canvas.getContextSafariWebGL2Fixed = canvas.getContext;
          function fixedGetContext(ver, attrs) {
            var gl = canvas.getContextSafariWebGL2Fixed(ver, attrs);
            return (ver == "webgl") == gl instanceof WebGLRenderingContext
              ? gl
              : null;
          }
          canvas.getContext = fixedGetContext;
        }
        var ctx =
          webGLContextAttributes.majorVersion > 1
            ? canvas.getContext("webgl2", webGLContextAttributes)
            : canvas.getContext("webgl", webGLContextAttributes);
        if (!ctx) return 0;
        var handle = GL.registerContext(ctx, webGLContextAttributes);
        return handle;
      },
      enableOffscreenFramebufferAttributes: (webGLContextAttributes) => {
        webGLContextAttributes.renderViaOffscreenBackBuffer = true;
        webGLContextAttributes.preserveDrawingBuffer = true;
      },
      createOffscreenFramebuffer: (context) => {
        var gl = context.GLctx;
        var fbo = gl.createFramebuffer();
        gl.bindFramebuffer(36160, fbo);
        context.defaultFbo = fbo;
        context.defaultFboForbidBlitFramebuffer = false;
        if (gl.getContextAttributes().antialias) {
          context.defaultFboForbidBlitFramebuffer = true;
        }
        context.defaultColorTarget = gl.createTexture();
        context.defaultDepthTarget = gl.createRenderbuffer();
        GL.resizeOffscreenFramebuffer(context);
        gl.bindTexture(3553, context.defaultColorTarget);
        gl.texParameteri(3553, 10241, 9728);
        gl.texParameteri(3553, 10240, 9728);
        gl.texParameteri(3553, 10242, 33071);
        gl.texParameteri(3553, 10243, 33071);
        gl.texImage2D(
          3553,
          0,
          6408,
          gl.canvas.width,
          gl.canvas.height,
          0,
          6408,
          5121,
          null,
        );
        gl.framebufferTexture2D(
          36160,
          36064,
          3553,
          context.defaultColorTarget,
          0,
        );
        gl.bindTexture(3553, null);
        var depthTarget = gl.createRenderbuffer();
        gl.bindRenderbuffer(36161, context.defaultDepthTarget);
        gl.renderbufferStorage(36161, 33189, gl.canvas.width, gl.canvas.height);
        gl.framebufferRenderbuffer(
          36160,
          36096,
          36161,
          context.defaultDepthTarget,
        );
        gl.bindRenderbuffer(36161, null);
        var vertices = [-1, -1, -1, 1, 1, -1, 1, 1];
        var vb = gl.createBuffer();
        gl.bindBuffer(34962, vb);
        gl.bufferData(34962, new Float32Array(vertices), 35044);
        gl.bindBuffer(34962, null);
        context.blitVB = vb;
        var vsCode =
          "attribute vec2 pos;" +
          "varying lowp vec2 tex;" +
          "void main() { tex = pos * 0.5 + vec2(0.5,0.5); gl_Position = vec4(pos, 0.0, 1.0); }";
        var vs = gl.createShader(35633);
        gl.shaderSource(vs, vsCode);
        gl.compileShader(vs);
        var fsCode =
          "varying lowp vec2 tex;" +
          "uniform sampler2D sampler;" +
          "void main() { gl_FragColor = texture2D(sampler, tex); }";
        var fs = gl.createShader(35632);
        gl.shaderSource(fs, fsCode);
        gl.compileShader(fs);
        var blitProgram = gl.createProgram();
        gl.attachShader(blitProgram, vs);
        gl.attachShader(blitProgram, fs);
        gl.linkProgram(blitProgram);
        context.blitProgram = blitProgram;
        context.blitPosLoc = gl.getAttribLocation(blitProgram, "pos");
        gl.useProgram(blitProgram);
        gl.uniform1i(gl.getUniformLocation(blitProgram, "sampler"), 0);
        gl.useProgram(null);
        context.defaultVao = undefined;
        if (gl.createVertexArray) {
          context.defaultVao = gl.createVertexArray();
          gl.bindVertexArray(context.defaultVao);
          gl.enableVertexAttribArray(context.blitPosLoc);
          gl.bindVertexArray(null);
        }
      },
      resizeOffscreenFramebuffer: (context) => {
        var gl = context.GLctx;
        if (context.defaultColorTarget) {
          var prevTextureBinding = gl.getParameter(32873);
          gl.bindTexture(3553, context.defaultColorTarget);
          gl.texImage2D(
            3553,
            0,
            6408,
            gl.drawingBufferWidth,
            gl.drawingBufferHeight,
            0,
            6408,
            5121,
            null,
          );
          gl.bindTexture(3553, prevTextureBinding);
        }
        if (context.defaultDepthTarget) {
          var prevRenderBufferBinding = gl.getParameter(36007);
          gl.bindRenderbuffer(36161, context.defaultDepthTarget);
          gl.renderbufferStorage(
            36161,
            33189,
            gl.drawingBufferWidth,
            gl.drawingBufferHeight,
          );
          gl.bindRenderbuffer(36161, prevRenderBufferBinding);
        }
      },
      blitOffscreenFramebuffer: (context) => {
        var gl = context.GLctx;
        var prevScissorTest = gl.getParameter(3089);
        if (prevScissorTest) gl.disable(3089);
        var prevFbo = gl.getParameter(36006);
        if (gl.blitFramebuffer && !context.defaultFboForbidBlitFramebuffer) {
          gl.bindFramebuffer(36008, context.defaultFbo);
          gl.bindFramebuffer(36009, null);
          gl.blitFramebuffer(
            0,
            0,
            gl.canvas.width,
            gl.canvas.height,
            0,
            0,
            gl.canvas.width,
            gl.canvas.height,
            16384,
            9728,
          );
        } else {
          gl.bindFramebuffer(36160, null);
          var prevProgram = gl.getParameter(35725);
          gl.useProgram(context.blitProgram);
          var prevVB = gl.getParameter(34964);
          gl.bindBuffer(34962, context.blitVB);
          var prevActiveTexture = gl.getParameter(34016);
          gl.activeTexture(33984);
          var prevTextureBinding = gl.getParameter(32873);
          gl.bindTexture(3553, context.defaultColorTarget);
          var prevBlend = gl.getParameter(3042);
          if (prevBlend) gl.disable(3042);
          var prevCullFace = gl.getParameter(2884);
          if (prevCullFace) gl.disable(2884);
          var prevDepthTest = gl.getParameter(2929);
          if (prevDepthTest) gl.disable(2929);
          var prevStencilTest = gl.getParameter(2960);
          if (prevStencilTest) gl.disable(2960);
          function draw() {
            gl.vertexAttribPointer(context.blitPosLoc, 2, 5126, false, 0, 0);
            gl.drawArrays(5, 0, 4);
          }
          if (context.defaultVao) {
            var prevVAO = gl.getParameter(34229);
            gl.bindVertexArray(context.defaultVao);
            draw();
            gl.bindVertexArray(prevVAO);
          } else {
            var prevVertexAttribPointer = {
              buffer: gl.getVertexAttrib(context.blitPosLoc, 34975),
              size: gl.getVertexAttrib(context.blitPosLoc, 34339),
              stride: gl.getVertexAttrib(context.blitPosLoc, 34340),
              type: gl.getVertexAttrib(context.blitPosLoc, 34341),
              normalized: gl.getVertexAttrib(context.blitPosLoc, 34922),
              pointer: gl.getVertexAttribOffset(context.blitPosLoc, 34373),
            };
            var maxVertexAttribs = gl.getParameter(34921);
            var prevVertexAttribEnables = [];
            for (var i = 0; i < maxVertexAttribs; ++i) {
              var prevEnabled = gl.getVertexAttrib(i, 34338);
              var wantEnabled = i == context.blitPosLoc;
              if (prevEnabled && !wantEnabled) {
                gl.disableVertexAttribArray(i);
              }
              if (!prevEnabled && wantEnabled) {
                gl.enableVertexAttribArray(i);
              }
              prevVertexAttribEnables[i] = prevEnabled;
            }
            draw();
            for (var i = 0; i < maxVertexAttribs; ++i) {
              var prevEnabled = prevVertexAttribEnables[i];
              var nowEnabled = i == context.blitPosLoc;
              if (prevEnabled && !nowEnabled) {
                gl.enableVertexAttribArray(i);
              }
              if (!prevEnabled && nowEnabled) {
                gl.disableVertexAttribArray(i);
              }
            }
            gl.bindBuffer(34962, prevVertexAttribPointer.buffer);
            gl.vertexAttribPointer(
              context.blitPosLoc,
              prevVertexAttribPointer.size,
              prevVertexAttribPointer.type,
              prevVertexAttribPointer.normalized,
              prevVertexAttribPointer.stride,
              prevVertexAttribPointer.offset,
            );
          }
          if (prevStencilTest) gl.enable(2960);
          if (prevDepthTest) gl.enable(2929);
          if (prevCullFace) gl.enable(2884);
          if (prevBlend) gl.enable(3042);
          gl.bindTexture(3553, prevTextureBinding);
          gl.activeTexture(prevActiveTexture);
          gl.bindBuffer(34962, prevVB);
          gl.useProgram(prevProgram);
        }
        gl.bindFramebuffer(36160, prevFbo);
        if (prevScissorTest) gl.enable(3089);
      },
      registerContext: (ctx, webGLContextAttributes) => {
        var handle = _malloc(8);
        GROWABLE_HEAP_U32()[(handle + 4) >> 2] = _pthread_self();
        var context = {
          handle: handle,
          attributes: webGLContextAttributes,
          version: webGLContextAttributes.majorVersion,
          GLctx: ctx,
        };
        if (ctx.canvas) ctx.canvas.GLctxObject = context;
        GL.contexts[handle] = context;
        if (
          typeof webGLContextAttributes.enableExtensionsByDefault ==
            "undefined" ||
          webGLContextAttributes.enableExtensionsByDefault
        ) {
          GL.initExtensions(context);
        }
        if (webGLContextAttributes.renderViaOffscreenBackBuffer)
          GL.createOffscreenFramebuffer(context);
        return handle;
      },
      makeContextCurrent: (contextHandle) => {
        GL.currentContext = GL.contexts[contextHandle];
        Module.ctx = GLctx = GL.currentContext?.GLctx;
        return !(contextHandle && !GLctx);
      },
      getContext: (contextHandle) => GL.contexts[contextHandle],
      deleteContext: (contextHandle) => {
        if (GL.currentContext === GL.contexts[contextHandle]) {
          GL.currentContext = null;
        }
        if (typeof JSEvents == "object") {
          JSEvents.removeAllHandlersOnTarget(
            GL.contexts[contextHandle].GLctx.canvas,
          );
        }
        if (
          GL.contexts[contextHandle] &&
          GL.contexts[contextHandle].GLctx.canvas
        ) {
          GL.contexts[contextHandle].GLctx.canvas.GLctxObject = undefined;
        }
        _free(GL.contexts[contextHandle].handle);
        GL.contexts[contextHandle] = null;
      },
      initExtensions: (context) => {
        context ||= GL.currentContext;
        if (context.initExtensionsDone) return;
        context.initExtensionsDone = true;
        var GLctx = context.GLctx;
        webgl_enable_ANGLE_instanced_arrays(GLctx);
        webgl_enable_OES_vertex_array_object(GLctx);
        webgl_enable_WEBGL_draw_buffers(GLctx);
        webgl_enable_WEBGL_draw_instanced_base_vertex_base_instance(GLctx);
        webgl_enable_WEBGL_multi_draw_instanced_base_vertex_base_instance(
          GLctx,
        );
        if (context.version >= 2) {
          GLctx.disjointTimerQueryExt = GLctx.getExtension(
            "EXT_disjoint_timer_query_webgl2",
          );
        }
        if (context.version < 2 || !GLctx.disjointTimerQueryExt) {
          GLctx.disjointTimerQueryExt = GLctx.getExtension(
            "EXT_disjoint_timer_query",
          );
        }
        webgl_enable_WEBGL_multi_draw(GLctx);
        var exts = GLctx.getSupportedExtensions() || [];
        exts.forEach((ext) => {
          if (!ext.includes("lose_context") && !ext.includes("debug")) {
            GLctx.getExtension(ext);
          }
        });
      },
      getExtensions() {
        var exts = GLctx.getSupportedExtensions() || [];
        exts = exts.concat(exts.map((e) => "GL_" + e));
        return exts;
      },
    };
    var __emscripten_proxied_gl_context_activated_from_main_browser_thread = (
      contextHandle,
    ) => {
      GLctx = Module.ctx = GL.currentContext = contextHandle;
      GL.currentContextIsProxied = true;
    };
    var proxiedJSCallArgs = [];
    var __emscripten_receive_on_main_thread_js = (
      index,
      callingThread,
      numCallArgs,
      args,
    ) => {
      numCallArgs /= 2;
      proxiedJSCallArgs.length = numCallArgs;
      var b = args >> 3;
      for (var i = 0; i < numCallArgs; i++) {
        if (HEAP64[b + 2 * i]) {
          proxiedJSCallArgs[i] = HEAP64[b + 2 * i + 1];
        } else {
          proxiedJSCallArgs[i] = GROWABLE_HEAP_F64()[b + 2 * i + 1];
        }
      }
      var isEmAsmConst = index < 0;
      var func = !isEmAsmConst
        ? proxiedFunctionTable[index]
        : ASM_CONSTS[-index - 1];
      PThread.currentProxiedOperationCallerThread = callingThread;
      var rtn = func.apply(null, proxiedJSCallArgs);
      PThread.currentProxiedOperationCallerThread = 0;
      return rtn;
    };
    var __emscripten_thread_set_strongref = (thread) => {};
    var __emval_incref = (handle) => {
      if (handle > 4) {
        emval_handles.get(handle).refcount += 1;
      }
    };
    function __gmtime_js(time, tmPtr) {
      time = bigintToI53Checked(time);
      var date = new Date(time * 1e3);
      GROWABLE_HEAP_I32()[tmPtr >> 2] = date.getUTCSeconds();
      GROWABLE_HEAP_I32()[(tmPtr + 4) >> 2] = date.getUTCMinutes();
      GROWABLE_HEAP_I32()[(tmPtr + 8) >> 2] = date.getUTCHours();
      GROWABLE_HEAP_I32()[(tmPtr + 12) >> 2] = date.getUTCDate();
      GROWABLE_HEAP_I32()[(tmPtr + 16) >> 2] = date.getUTCMonth();
      GROWABLE_HEAP_I32()[(tmPtr + 20) >> 2] = date.getUTCFullYear() - 1900;
      GROWABLE_HEAP_I32()[(tmPtr + 24) >> 2] = date.getUTCDay();
      var start = Date.UTC(date.getUTCFullYear(), 0, 1, 0, 0, 0, 0);
      var yday = ((date.getTime() - start) / (1e3 * 60 * 60 * 24)) | 0;
      GROWABLE_HEAP_I32()[(tmPtr + 28) >> 2] = yday;
    }
    var isLeapYear = (year) =>
      year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    var MONTH_DAYS_LEAP_CUMULATIVE = [
      0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335,
    ];
    var MONTH_DAYS_REGULAR_CUMULATIVE = [
      0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334,
    ];
    var ydayFromDate = (date) => {
      var leap = isLeapYear(date.getFullYear());
      var monthDaysCumulative = leap
        ? MONTH_DAYS_LEAP_CUMULATIVE
        : MONTH_DAYS_REGULAR_CUMULATIVE;
      var yday = monthDaysCumulative[date.getMonth()] + date.getDate() - 1;
      return yday;
    };
    function __localtime_js(time, tmPtr) {
      time = bigintToI53Checked(time);
      var date = new Date(time * 1e3);
      GROWABLE_HEAP_I32()[tmPtr >> 2] = date.getSeconds();
      GROWABLE_HEAP_I32()[(tmPtr + 4) >> 2] = date.getMinutes();
      GROWABLE_HEAP_I32()[(tmPtr + 8) >> 2] = date.getHours();
      GROWABLE_HEAP_I32()[(tmPtr + 12) >> 2] = date.getDate();
      GROWABLE_HEAP_I32()[(tmPtr + 16) >> 2] = date.getMonth();
      GROWABLE_HEAP_I32()[(tmPtr + 20) >> 2] = date.getFullYear() - 1900;
      GROWABLE_HEAP_I32()[(tmPtr + 24) >> 2] = date.getDay();
      var yday = ydayFromDate(date) | 0;
      GROWABLE_HEAP_I32()[(tmPtr + 28) >> 2] = yday;
      GROWABLE_HEAP_I32()[(tmPtr + 36) >> 2] = -(date.getTimezoneOffset() * 60);
      var start = new Date(date.getFullYear(), 0, 1);
      var summerOffset = new Date(date.getFullYear(), 6, 1).getTimezoneOffset();
      var winterOffset = start.getTimezoneOffset();
      var dst =
        (summerOffset != winterOffset &&
          date.getTimezoneOffset() == Math.min(winterOffset, summerOffset)) | 0;
      GROWABLE_HEAP_I32()[(tmPtr + 32) >> 2] = dst;
    }
    var stringToNewUTF8 = (str) => {
      var size = lengthBytesUTF8(str) + 1;
      var ret = _malloc(size);
      if (ret) stringToUTF8(str, ret, size);
      return ret;
    };
    var __tzset_js = (timezone, daylight, tzname) => {
      var currentYear = new Date().getFullYear();
      var winter = new Date(currentYear, 0, 1);
      var summer = new Date(currentYear, 6, 1);
      var winterOffset = winter.getTimezoneOffset();
      var summerOffset = summer.getTimezoneOffset();
      var stdTimezoneOffset = Math.max(winterOffset, summerOffset);
      GROWABLE_HEAP_U32()[timezone >> 2] = stdTimezoneOffset * 60;
      GROWABLE_HEAP_I32()[daylight >> 2] = Number(winterOffset != summerOffset);
      function extractZone(date) {
        var match = date.toTimeString().match(/\(([A-Za-z ]+)\)$/);
        return match ? match[1] : "GMT";
      }
      var winterName = extractZone(winter);
      var summerName = extractZone(summer);
      var winterNamePtr = stringToNewUTF8(winterName);
      var summerNamePtr = stringToNewUTF8(summerName);
      if (summerOffset < winterOffset) {
        GROWABLE_HEAP_U32()[tzname >> 2] = winterNamePtr;
        GROWABLE_HEAP_U32()[(tzname + 4) >> 2] = summerNamePtr;
      } else {
        GROWABLE_HEAP_U32()[tzname >> 2] = summerNamePtr;
        GROWABLE_HEAP_U32()[(tzname + 4) >> 2] = winterNamePtr;
      }
    };
    var _abort = () => {
      abort("");
    };
    var runtimeKeepalivePush = () => {
      runtimeKeepaliveCounter += 1;
    };
    var _emscripten_set_main_loop_timing = (mode, value) => {
      Browser.mainLoop.timingMode = mode;
      Browser.mainLoop.timingValue = value;
      if (!Browser.mainLoop.func) {
        return 1;
      }
      if (!Browser.mainLoop.running) {
        runtimeKeepalivePush();
        Browser.mainLoop.running = true;
      }
      if (mode == 0) {
        Browser.mainLoop.scheduler =
          function Browser_mainLoop_scheduler_setTimeout() {
            var timeUntilNextTick =
              Math.max(
                0,
                Browser.mainLoop.tickStartTime + value - _emscripten_get_now(),
              ) | 0;
            setTimeout(Browser.mainLoop.runner, timeUntilNextTick);
          };
        Browser.mainLoop.method = "timeout";
      } else if (mode == 1) {
        Browser.mainLoop.scheduler = function Browser_mainLoop_scheduler_rAF() {
          Browser.requestAnimationFrame(Browser.mainLoop.runner);
        };
        Browser.mainLoop.method = "rAF";
      } else if (mode == 2) {
        if (typeof Browser.setImmediate == "undefined") {
          if (typeof setImmediate == "undefined") {
            var setImmediates = [];
            var emscriptenMainLoopMessageId = "setimmediate";
            var Browser_setImmediate_messageHandler = (event) => {
              if (
                event.data === emscriptenMainLoopMessageId ||
                event.data.target === emscriptenMainLoopMessageId
              ) {
                event.stopPropagation();
                setImmediates.shift()();
              }
            };
            addEventListener(
              "message",
              Browser_setImmediate_messageHandler,
              true,
            );
            Browser.setImmediate = function Browser_emulated_setImmediate(
              func,
            ) {
              setImmediates.push(func);
              if (ENVIRONMENT_IS_WORKER) {
                if (Module["setImmediates"] === undefined)
                  Module["setImmediates"] = [];
                Module["setImmediates"].push(func);
                postMessage({ target: emscriptenMainLoopMessageId });
              } else postMessage(emscriptenMainLoopMessageId, "*");
            };
          } else {
            Browser.setImmediate = setImmediate;
          }
        }
        Browser.mainLoop.scheduler =
          function Browser_mainLoop_scheduler_setImmediate() {
            Browser.setImmediate(Browser.mainLoop.runner);
          };
        Browser.mainLoop.method = "immediate";
      }
      return 0;
    };
    var _emscripten_get_now;
    _emscripten_get_now = () => performance.timeOrigin + performance.now();
    var runtimeKeepalivePop = () => {
      runtimeKeepaliveCounter -= 1;
    };
    var setMainLoop = (
      browserIterationFunc,
      fps,
      simulateInfiniteLoop,
      arg,
      noSetTiming,
    ) => {
      assert(
        !Browser.mainLoop.func,
        "emscripten_set_main_loop: there can only be one main loop function at once: call emscripten_cancel_main_loop to cancel the previous one before setting a new one with different parameters.",
      );
      Browser.mainLoop.func = browserIterationFunc;
      Browser.mainLoop.arg = arg;
      var thisMainLoopId = Browser.mainLoop.currentlyRunningMainloop;
      function checkIsRunning() {
        if (thisMainLoopId < Browser.mainLoop.currentlyRunningMainloop) {
          runtimeKeepalivePop();
          return false;
        }
        return true;
      }
      Browser.mainLoop.running = false;
      Browser.mainLoop.runner = function Browser_mainLoop_runner() {
        if (ABORT) return;
        if (Browser.mainLoop.queue.length > 0) {
          var start = Date.now();
          var blocker = Browser.mainLoop.queue.shift();
          blocker.func(blocker.arg);
          if (Browser.mainLoop.remainingBlockers) {
            var remaining = Browser.mainLoop.remainingBlockers;
            var next =
              remaining % 1 == 0 ? remaining - 1 : Math.floor(remaining);
            if (blocker.counted) {
              Browser.mainLoop.remainingBlockers = next;
            } else {
              next = next + 0.5;
              Browser.mainLoop.remainingBlockers = (8 * remaining + next) / 9;
            }
          }
          Browser.mainLoop.updateStatus();
          if (!checkIsRunning()) return;
          setTimeout(Browser.mainLoop.runner, 0);
          return;
        }
        if (!checkIsRunning()) return;
        Browser.mainLoop.currentFrameNumber =
          (Browser.mainLoop.currentFrameNumber + 1) | 0;
        if (
          Browser.mainLoop.timingMode == 1 &&
          Browser.mainLoop.timingValue > 1 &&
          Browser.mainLoop.currentFrameNumber % Browser.mainLoop.timingValue !=
            0
        ) {
          Browser.mainLoop.scheduler();
          return;
        } else if (Browser.mainLoop.timingMode == 0) {
          Browser.mainLoop.tickStartTime = _emscripten_get_now();
        }
        Browser.mainLoop.runIter(browserIterationFunc);
        if (!checkIsRunning()) return;
        if (typeof SDL == "object") SDL.audio?.queueNewAudioData?.();
        Browser.mainLoop.scheduler();
      };
      if (!noSetTiming) {
        if (fps && fps > 0) {
          _emscripten_set_main_loop_timing(0, 1e3 / fps);
        } else {
          _emscripten_set_main_loop_timing(1, 1);
        }
        Browser.mainLoop.scheduler();
      }
      if (simulateInfiniteLoop) {
        throw "unwind";
      }
    };
    var safeSetTimeout = (func, timeout) => {
      runtimeKeepalivePush();
      return setTimeout(() => {
        runtimeKeepalivePop();
        callUserCallback(func);
      }, timeout);
    };
    var warnOnce = (text) => {
      warnOnce.shown ||= {};
      if (!warnOnce.shown[text]) {
        warnOnce.shown[text] = 1;
        err(text);
      }
    };
    var Browser = {
      mainLoop: {
        running: false,
        scheduler: null,
        method: "",
        currentlyRunningMainloop: 0,
        func: null,
        arg: 0,
        timingMode: 0,
        timingValue: 0,
        currentFrameNumber: 0,
        queue: [],
        pause() {
          Browser.mainLoop.scheduler = null;
          Browser.mainLoop.currentlyRunningMainloop++;
        },
        resume() {
          Browser.mainLoop.currentlyRunningMainloop++;
          var timingMode = Browser.mainLoop.timingMode;
          var timingValue = Browser.mainLoop.timingValue;
          var func = Browser.mainLoop.func;
          Browser.mainLoop.func = null;
          setMainLoop(func, 0, false, Browser.mainLoop.arg, true);
          _emscripten_set_main_loop_timing(timingMode, timingValue);
          Browser.mainLoop.scheduler();
        },
        updateStatus() {
          if (Module["setStatus"]) {
            var message = Module["statusMessage"] || "Please wait...";
            var remaining = Browser.mainLoop.remainingBlockers;
            var expected = Browser.mainLoop.expectedBlockers;
            if (remaining) {
              if (remaining < expected) {
                Module["setStatus"](
                  message +
                    " (" +
                    (expected - remaining) +
                    "/" +
                    expected +
                    ")",
                );
              } else {
                Module["setStatus"](message);
              }
            } else {
              Module["setStatus"]("");
            }
          }
        },
        runIter(func) {
          if (ABORT) return;
          if (Module["preMainLoop"]) {
            var preRet = Module["preMainLoop"]();
            if (preRet === false) {
              return;
            }
          }
          callUserCallback(func);
          Module["postMainLoop"]?.();
        },
      },
      isFullscreen: false,
      pointerLock: false,
      moduleContextCreatedCallbacks: [],
      workers: [],
      init() {
        if (Browser.initted) return;
        Browser.initted = true;
        var imagePlugin = {};
        imagePlugin["canHandle"] = function imagePlugin_canHandle(name) {
          return !Module.noImageDecoding && /\.(jpg|jpeg|png|bmp)$/i.test(name);
        };
        imagePlugin["handle"] = function imagePlugin_handle(
          byteArray,
          name,
          onload,
          onerror,
        ) {
          var b = new Blob([byteArray], { type: Browser.getMimetype(name) });
          if (b.size !== byteArray.length) {
            b = new Blob([new Uint8Array(byteArray).buffer], {
              type: Browser.getMimetype(name),
            });
          }
          var url = URL.createObjectURL(b);
          var img = new Image();
          img.onload = () => {
            assert(img.complete, `Image ${name} could not be decoded`);
            var canvas = document.createElement("canvas");
            canvas.width = img.width;
            canvas.height = img.height;
            var ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0);
            preloadedImages[name] = canvas;
            URL.revokeObjectURL(url);
            onload?.(byteArray);
          };
          img.onerror = (event) => {
            err(`Image ${url} could not be decoded`);
            onerror?.();
          };
          img.src = url;
        };
        preloadPlugins.push(imagePlugin);
        var audioPlugin = {};
        audioPlugin["canHandle"] = function audioPlugin_canHandle(name) {
          return (
            !Module.noAudioDecoding &&
            name.substr(-4) in { ".ogg": 1, ".wav": 1, ".mp3": 1 }
          );
        };
        audioPlugin["handle"] = function audioPlugin_handle(
          byteArray,
          name,
          onload,
          onerror,
        ) {
          var done = false;
          function finish(audio) {
            if (done) return;
            done = true;
            preloadedAudios[name] = audio;
            onload?.(byteArray);
          }
          var b = new Blob([byteArray], { type: Browser.getMimetype(name) });
          var url = URL.createObjectURL(b);
          var audio = new Audio();
          audio.addEventListener("canplaythrough", () => finish(audio), false);
          audio.onerror = function audio_onerror(event) {
            if (done) return;
            err(
              `warning: browser could not fully decode audio ${name}, trying slower base64 approach`,
            );
            function encode64(data) {
              var BASE =
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
              var PAD = "=";
              var ret = "";
              var leftchar = 0;
              var leftbits = 0;
              for (var i = 0; i < data.length; i++) {
                leftchar = (leftchar << 8) | data[i];
                leftbits += 8;
                while (leftbits >= 6) {
                  var curr = (leftchar >> (leftbits - 6)) & 63;
                  leftbits -= 6;
                  ret += BASE[curr];
                }
              }
              if (leftbits == 2) {
                ret += BASE[(leftchar & 3) << 4];
                ret += PAD + PAD;
              } else if (leftbits == 4) {
                ret += BASE[(leftchar & 15) << 2];
                ret += PAD;
              }
              return ret;
            }
            audio.src =
              "data:audio/x-" +
              name.substr(-3) +
              ";base64," +
              encode64(byteArray);
            finish(audio);
          };
          audio.src = url;
          safeSetTimeout(() => {
            finish(audio);
          }, 1e4);
        };
        preloadPlugins.push(audioPlugin);
        function pointerLockChange() {
          Browser.pointerLock =
            document["pointerLockElement"] === Module["canvas"] ||
            document["mozPointerLockElement"] === Module["canvas"] ||
            document["webkitPointerLockElement"] === Module["canvas"] ||
            document["msPointerLockElement"] === Module["canvas"];
        }
        var canvas = Module["canvas"];
        if (canvas) {
          canvas.requestPointerLock =
            canvas["requestPointerLock"] ||
            canvas["mozRequestPointerLock"] ||
            canvas["webkitRequestPointerLock"] ||
            canvas["msRequestPointerLock"] ||
            (() => {});
          canvas.exitPointerLock =
            document["exitPointerLock"] ||
            document["mozExitPointerLock"] ||
            document["webkitExitPointerLock"] ||
            document["msExitPointerLock"] ||
            (() => {});
          canvas.exitPointerLock = canvas.exitPointerLock.bind(document);
          document.addEventListener(
            "pointerlockchange",
            pointerLockChange,
            false,
          );
          document.addEventListener(
            "mozpointerlockchange",
            pointerLockChange,
            false,
          );
          document.addEventListener(
            "webkitpointerlockchange",
            pointerLockChange,
            false,
          );
          document.addEventListener(
            "mspointerlockchange",
            pointerLockChange,
            false,
          );
          if (Module["elementPointerLock"]) {
            canvas.addEventListener(
              "click",
              (ev) => {
                if (
                  !Browser.pointerLock &&
                  Module["canvas"].requestPointerLock
                ) {
                  Module["canvas"].requestPointerLock();
                  ev.preventDefault();
                }
              },
              false,
            );
          }
        }
      },
      createContext(canvas, useWebGL, setInModule, webGLContextAttributes) {
        if (useWebGL && Module.ctx && canvas == Module.canvas)
          return Module.ctx;
        var ctx;
        var contextHandle;
        if (useWebGL) {
          var contextAttributes = {
            antialias: false,
            alpha: false,
            majorVersion: typeof WebGL2RenderingContext != "undefined" ? 2 : 1,
          };
          if (webGLContextAttributes) {
            for (var attribute in webGLContextAttributes) {
              contextAttributes[attribute] = webGLContextAttributes[attribute];
            }
          }
          if (typeof GL != "undefined") {
            contextHandle = GL.createContext(canvas, contextAttributes);
            if (contextHandle) {
              ctx = GL.getContext(contextHandle).GLctx;
            }
          }
        } else {
          ctx = canvas.getContext("2d");
        }
        if (!ctx) return null;
        if (setInModule) {
          if (!useWebGL)
            assert(
              typeof GLctx == "undefined",
              "cannot set in module if GLctx is used, but we are a non-GL context that would replace it",
            );
          Module.ctx = ctx;
          if (useWebGL) GL.makeContextCurrent(contextHandle);
          Module.useWebGL = useWebGL;
          Browser.moduleContextCreatedCallbacks.forEach((callback) =>
            callback(),
          );
          Browser.init();
        }
        return ctx;
      },
      destroyContext(canvas, useWebGL, setInModule) {},
      fullscreenHandlersInstalled: false,
      lockPointer: undefined,
      resizeCanvas: undefined,
      requestFullscreen(lockPointer, resizeCanvas) {
        Browser.lockPointer = lockPointer;
        Browser.resizeCanvas = resizeCanvas;
        if (typeof Browser.lockPointer == "undefined")
          Browser.lockPointer = true;
        if (typeof Browser.resizeCanvas == "undefined")
          Browser.resizeCanvas = false;
        var canvas = Module["canvas"];
        function fullscreenChange() {
          Browser.isFullscreen = false;
          var canvasContainer = canvas.parentNode;
          if (
            (document["fullscreenElement"] ||
              document["mozFullScreenElement"] ||
              document["msFullscreenElement"] ||
              document["webkitFullscreenElement"] ||
              document["webkitCurrentFullScreenElement"]) === canvasContainer
          ) {
            canvas.exitFullscreen = Browser.exitFullscreen;
            if (Browser.lockPointer) canvas.requestPointerLock();
            Browser.isFullscreen = true;
            if (Browser.resizeCanvas) {
              Browser.setFullscreenCanvasSize();
            } else {
              Browser.updateCanvasDimensions(canvas);
            }
          } else {
            canvasContainer.parentNode.insertBefore(canvas, canvasContainer);
            canvasContainer.parentNode.removeChild(canvasContainer);
            if (Browser.resizeCanvas) {
              Browser.setWindowedCanvasSize();
            } else {
              Browser.updateCanvasDimensions(canvas);
            }
          }
          Module["onFullScreen"]?.(Browser.isFullscreen);
          Module["onFullscreen"]?.(Browser.isFullscreen);
        }
        if (!Browser.fullscreenHandlersInstalled) {
          Browser.fullscreenHandlersInstalled = true;
          document.addEventListener(
            "fullscreenchange",
            fullscreenChange,
            false,
          );
          document.addEventListener(
            "mozfullscreenchange",
            fullscreenChange,
            false,
          );
          document.addEventListener(
            "webkitfullscreenchange",
            fullscreenChange,
            false,
          );
          document.addEventListener(
            "MSFullscreenChange",
            fullscreenChange,
            false,
          );
        }
        var canvasContainer = document.createElement("div");
        canvas.parentNode.insertBefore(canvasContainer, canvas);
        canvasContainer.appendChild(canvas);
        canvasContainer.requestFullscreen =
          canvasContainer["requestFullscreen"] ||
          canvasContainer["mozRequestFullScreen"] ||
          canvasContainer["msRequestFullscreen"] ||
          (canvasContainer["webkitRequestFullscreen"]
            ? () =>
                canvasContainer["webkitRequestFullscreen"](
                  Element["ALLOW_KEYBOARD_INPUT"],
                )
            : null) ||
          (canvasContainer["webkitRequestFullScreen"]
            ? () =>
                canvasContainer["webkitRequestFullScreen"](
                  Element["ALLOW_KEYBOARD_INPUT"],
                )
            : null);
        canvasContainer.requestFullscreen();
      },
      exitFullscreen() {
        if (!Browser.isFullscreen) {
          return false;
        }
        var CFS =
          document["exitFullscreen"] ||
          document["cancelFullScreen"] ||
          document["mozCancelFullScreen"] ||
          document["msExitFullscreen"] ||
          document["webkitCancelFullScreen"] ||
          (() => {});
        CFS.apply(document, []);
        return true;
      },
      nextRAF: 0,
      fakeRequestAnimationFrame(func) {
        var now = Date.now();
        if (Browser.nextRAF === 0) {
          Browser.nextRAF = now + 1e3 / 60;
        } else {
          while (now + 2 >= Browser.nextRAF) {
            Browser.nextRAF += 1e3 / 60;
          }
        }
        var delay = Math.max(Browser.nextRAF - now, 0);
        setTimeout(func, delay);
      },
      requestAnimationFrame(func) {
        if (typeof requestAnimationFrame == "function") {
          requestAnimationFrame(func);
          return;
        }
        var RAF = Browser.fakeRequestAnimationFrame;
        RAF(func);
      },
      safeSetTimeout(func, timeout) {
        return safeSetTimeout(func, timeout);
      },
      safeRequestAnimationFrame(func) {
        runtimeKeepalivePush();
        return Browser.requestAnimationFrame(() => {
          runtimeKeepalivePop();
          callUserCallback(func);
        });
      },
      getMimetype(name) {
        return {
          jpg: "image/jpeg",
          jpeg: "image/jpeg",
          png: "image/png",
          bmp: "image/bmp",
          ogg: "audio/ogg",
          wav: "audio/wav",
          mp3: "audio/mpeg",
        }[name.substr(name.lastIndexOf(".") + 1)];
      },
      getUserMedia(func) {
        window.getUserMedia ||=
          navigator["getUserMedia"] || navigator["mozGetUserMedia"];
        window.getUserMedia(func);
      },
      getMovementX(event) {
        return (
          event["movementX"] ||
          event["mozMovementX"] ||
          event["webkitMovementX"] ||
          0
        );
      },
      getMovementY(event) {
        return (
          event["movementY"] ||
          event["mozMovementY"] ||
          event["webkitMovementY"] ||
          0
        );
      },
      getMouseWheelDelta(event) {
        var delta = 0;
        switch (event.type) {
          case "DOMMouseScroll":
            delta = event.detail / 3;
            break;
          case "mousewheel":
            delta = event.wheelDelta / 120;
            break;
          case "wheel":
            delta = event.deltaY;
            switch (event.deltaMode) {
              case 0:
                delta /= 100;
                break;
              case 1:
                delta /= 3;
                break;
              case 2:
                delta *= 80;
                break;
              default:
                throw "unrecognized mouse wheel delta mode: " + event.deltaMode;
            }
            break;
          default:
            throw "unrecognized mouse wheel event: " + event.type;
        }
        return delta;
      },
      mouseX: 0,
      mouseY: 0,
      mouseMovementX: 0,
      mouseMovementY: 0,
      touches: {},
      lastTouches: {},
      calculateMouseCoords(pageX, pageY) {
        var rect = Module["canvas"].getBoundingClientRect();
        var cw = Module["canvas"].width;
        var ch = Module["canvas"].height;
        var scrollX =
          typeof window.scrollX != "undefined"
            ? window.scrollX
            : window.pageXOffset;
        var scrollY =
          typeof window.scrollY != "undefined"
            ? window.scrollY
            : window.pageYOffset;
        var adjustedX = pageX - (scrollX + rect.left);
        var adjustedY = pageY - (scrollY + rect.top);
        adjustedX = adjustedX * (cw / rect.width);
        adjustedY = adjustedY * (ch / rect.height);
        return { x: adjustedX, y: adjustedY };
      },
      setMouseCoords(pageX, pageY) {
        const { x: x, y: y } = Browser.calculateMouseCoords(pageX, pageY);
        Browser.mouseMovementX = x - Browser.mouseX;
        Browser.mouseMovementY = y - Browser.mouseY;
        Browser.mouseX = x;
        Browser.mouseY = y;
      },
      calculateMouseEvent(event) {
        if (Browser.pointerLock) {
          if (event.type != "mousemove" && "mozMovementX" in event) {
            Browser.mouseMovementX = Browser.mouseMovementY = 0;
          } else {
            Browser.mouseMovementX = Browser.getMovementX(event);
            Browser.mouseMovementY = Browser.getMovementY(event);
          }
          if (typeof SDL != "undefined") {
            Browser.mouseX = SDL.mouseX + Browser.mouseMovementX;
            Browser.mouseY = SDL.mouseY + Browser.mouseMovementY;
          } else {
            Browser.mouseX += Browser.mouseMovementX;
            Browser.mouseY += Browser.mouseMovementY;
          }
        } else {
          if (
            event.type === "touchstart" ||
            event.type === "touchend" ||
            event.type === "touchmove"
          ) {
            var touch = event.touch;
            if (touch === undefined) {
              return;
            }
            var coords = Browser.calculateMouseCoords(touch.pageX, touch.pageY);
            if (event.type === "touchstart") {
              Browser.lastTouches[touch.identifier] = coords;
              Browser.touches[touch.identifier] = coords;
            } else if (
              event.type === "touchend" ||
              event.type === "touchmove"
            ) {
              var last = Browser.touches[touch.identifier];
              last ||= coords;
              Browser.lastTouches[touch.identifier] = last;
              Browser.touches[touch.identifier] = coords;
            }
            return;
          }
          Browser.setMouseCoords(event.pageX, event.pageY);
        }
      },
      resizeListeners: [],
      updateResizeListeners() {
        var canvas = Module["canvas"];
        Browser.resizeListeners.forEach((listener) =>
          listener(canvas.width, canvas.height),
        );
      },
      setCanvasSize(width, height, noUpdates) {
        var canvas = Module["canvas"];
        Browser.updateCanvasDimensions(canvas, width, height);
        if (!noUpdates) Browser.updateResizeListeners();
      },
      windowedWidth: 0,
      windowedHeight: 0,
      setFullscreenCanvasSize() {
        if (typeof SDL != "undefined") {
          var flags = GROWABLE_HEAP_U32()[SDL.screen >> 2];
          flags = flags | 8388608;
          GROWABLE_HEAP_I32()[SDL.screen >> 2] = flags;
        }
        Browser.updateCanvasDimensions(Module["canvas"]);
        Browser.updateResizeListeners();
      },
      setWindowedCanvasSize() {
        if (typeof SDL != "undefined") {
          var flags = GROWABLE_HEAP_U32()[SDL.screen >> 2];
          flags = flags & ~8388608;
          GROWABLE_HEAP_I32()[SDL.screen >> 2] = flags;
        }
        Browser.updateCanvasDimensions(Module["canvas"]);
        Browser.updateResizeListeners();
      },
      updateCanvasDimensions(canvas, wNative, hNative) {
        if (wNative && hNative) {
          canvas.widthNative = wNative;
          canvas.heightNative = hNative;
        } else {
          wNative = canvas.widthNative;
          hNative = canvas.heightNative;
        }
        var w = wNative;
        var h = hNative;
        if (Module["forcedAspectRatio"] && Module["forcedAspectRatio"] > 0) {
          if (w / h < Module["forcedAspectRatio"]) {
            w = Math.round(h * Module["forcedAspectRatio"]);
          } else {
            h = Math.round(w / Module["forcedAspectRatio"]);
          }
        }
        if (
          (document["fullscreenElement"] ||
            document["mozFullScreenElement"] ||
            document["msFullscreenElement"] ||
            document["webkitFullscreenElement"] ||
            document["webkitCurrentFullScreenElement"]) === canvas.parentNode &&
          typeof screen != "undefined"
        ) {
          var factor = Math.min(screen.width / w, screen.height / h);
          w = Math.round(w * factor);
          h = Math.round(h * factor);
        }
        if (Browser.resizeCanvas) {
          if (canvas.width != w) canvas.width = w;
          if (canvas.height != h) canvas.height = h;
          if (typeof canvas.style != "undefined") {
            canvas.style.removeProperty("width");
            canvas.style.removeProperty("height");
          }
        } else {
          if (canvas.width != wNative) canvas.width = wNative;
          if (canvas.height != hNative) canvas.height = hNative;
          if (typeof canvas.style != "undefined") {
            if (w != wNative || h != hNative) {
              canvas.style.setProperty("width", w + "px", "important");
              canvas.style.setProperty("height", h + "px", "important");
            } else {
              canvas.style.removeProperty("width");
              canvas.style.removeProperty("height");
            }
          }
        }
      },
    };
    var AL = {
      QUEUE_INTERVAL: 25,
      QUEUE_LOOKAHEAD: 0.1,
      DEVICE_NAME: "Emscripten OpenAL",
      CAPTURE_DEVICE_NAME: "Emscripten OpenAL capture",
      ALC_EXTENSIONS: { ALC_SOFT_pause_device: true, ALC_SOFT_HRTF: true },
      AL_EXTENSIONS: {
        AL_EXT_float32: true,
        AL_SOFT_loop_points: true,
        AL_SOFT_source_length: true,
        AL_EXT_source_distance_model: true,
        AL_SOFT_source_spatialize: true,
      },
      _alcErr: 0,
      alcErr: 0,
      deviceRefCounts: {},
      alcStringCache: {},
      paused: false,
      stringCache: {},
      contexts: {},
      currentCtx: null,
      buffers: {
        0: {
          id: 0,
          refCount: 0,
          audioBuf: null,
          frequency: 0,
          bytesPerSample: 2,
          channels: 1,
          length: 0,
        },
      },
      paramArray: [],
      _nextId: 1,
      newId: () => (AL.freeIds.length > 0 ? AL.freeIds.pop() : AL._nextId++),
      freeIds: [],
      scheduleContextAudio: (ctx) => {
        if (
          Browser.mainLoop.timingMode === 1 &&
          document["visibilityState"] != "visible"
        ) {
          return;
        }
        for (var i in ctx.sources) {
          AL.scheduleSourceAudio(ctx.sources[i]);
        }
      },
      scheduleSourceAudio: (src, lookahead) => {
        if (
          Browser.mainLoop.timingMode === 1 &&
          document["visibilityState"] != "visible"
        ) {
          return;
        }
        if (src.state !== 4114) {
          return;
        }
        var currentTime = AL.updateSourceTime(src);
        var startTime = src.bufStartTime;
        var startOffset = src.bufOffset;
        var bufCursor = src.bufsProcessed;
        for (var i = 0; i < src.audioQueue.length; i++) {
          var audioSrc = src.audioQueue[i];
          startTime = audioSrc._startTime + audioSrc._duration;
          startOffset = 0;
          bufCursor += audioSrc._skipCount + 1;
        }
        if (!lookahead) {
          lookahead = AL.QUEUE_LOOKAHEAD;
        }
        var lookaheadTime = currentTime + lookahead;
        var skipCount = 0;
        while (startTime < lookaheadTime) {
          if (bufCursor >= src.bufQueue.length) {
            if (src.looping) {
              bufCursor %= src.bufQueue.length;
            } else {
              break;
            }
          }
          var buf = src.bufQueue[bufCursor % src.bufQueue.length];
          if (buf.length === 0) {
            skipCount++;
            if (skipCount === src.bufQueue.length) {
              break;
            }
          } else {
            var audioSrc = src.context.audioCtx.createBufferSource();
            audioSrc.buffer = buf.audioBuf;
            audioSrc.playbackRate.value = src.playbackRate;
            if (buf.audioBuf._loopStart || buf.audioBuf._loopEnd) {
              audioSrc.loopStart = buf.audioBuf._loopStart;
              audioSrc.loopEnd = buf.audioBuf._loopEnd;
            }
            var duration = 0;
            if (src.type === 4136 && src.looping) {
              duration = Number.POSITIVE_INFINITY;
              audioSrc.loop = true;
              if (buf.audioBuf._loopStart) {
                audioSrc.loopStart = buf.audioBuf._loopStart;
              }
              if (buf.audioBuf._loopEnd) {
                audioSrc.loopEnd = buf.audioBuf._loopEnd;
              }
            } else {
              duration =
                (buf.audioBuf.duration - startOffset) / src.playbackRate;
            }
            audioSrc._startOffset = startOffset;
            audioSrc._duration = duration;
            audioSrc._skipCount = skipCount;
            skipCount = 0;
            audioSrc.connect(src.gain);
            if (typeof audioSrc.start != "undefined") {
              startTime = Math.max(startTime, src.context.audioCtx.currentTime);
              audioSrc.start(startTime, startOffset);
            } else if (typeof audioSrc.noteOn != "undefined") {
              startTime = Math.max(startTime, src.context.audioCtx.currentTime);
              audioSrc.noteOn(startTime);
            }
            audioSrc._startTime = startTime;
            src.audioQueue.push(audioSrc);
            startTime += duration;
          }
          startOffset = 0;
          bufCursor++;
        }
      },
      updateSourceTime: (src) => {
        var currentTime = src.context.audioCtx.currentTime;
        if (src.state !== 4114) {
          return currentTime;
        }
        if (!isFinite(src.bufStartTime)) {
          src.bufStartTime = currentTime - src.bufOffset / src.playbackRate;
          src.bufOffset = 0;
        }
        var nextStartTime = 0;
        while (src.audioQueue.length) {
          var audioSrc = src.audioQueue[0];
          src.bufsProcessed += audioSrc._skipCount;
          nextStartTime = audioSrc._startTime + audioSrc._duration;
          if (currentTime < nextStartTime) {
            break;
          }
          src.audioQueue.shift();
          src.bufStartTime = nextStartTime;
          src.bufOffset = 0;
          src.bufsProcessed++;
        }
        if (src.bufsProcessed >= src.bufQueue.length && !src.looping) {
          AL.setSourceState(src, 4116);
        } else if (src.type === 4136 && src.looping) {
          var buf = src.bufQueue[0];
          if (buf.length === 0) {
            src.bufOffset = 0;
          } else {
            var delta = (currentTime - src.bufStartTime) * src.playbackRate;
            var loopStart = buf.audioBuf._loopStart || 0;
            var loopEnd = buf.audioBuf._loopEnd || buf.audioBuf.duration;
            if (loopEnd <= loopStart) {
              loopEnd = buf.audioBuf.duration;
            }
            if (delta < loopEnd) {
              src.bufOffset = delta;
            } else {
              src.bufOffset =
                loopStart + ((delta - loopStart) % (loopEnd - loopStart));
            }
          }
        } else if (src.audioQueue[0]) {
          src.bufOffset =
            (currentTime - src.audioQueue[0]._startTime) * src.playbackRate;
        } else {
          if (src.type !== 4136 && src.looping) {
            var srcDuration = AL.sourceDuration(src) / src.playbackRate;
            if (srcDuration > 0) {
              src.bufStartTime +=
                Math.floor((currentTime - src.bufStartTime) / srcDuration) *
                srcDuration;
            }
          }
          for (var i = 0; i < src.bufQueue.length; i++) {
            if (src.bufsProcessed >= src.bufQueue.length) {
              if (src.looping) {
                src.bufsProcessed %= src.bufQueue.length;
              } else {
                AL.setSourceState(src, 4116);
                break;
              }
            }
            var buf = src.bufQueue[src.bufsProcessed];
            if (buf.length > 0) {
              nextStartTime =
                src.bufStartTime + buf.audioBuf.duration / src.playbackRate;
              if (currentTime < nextStartTime) {
                src.bufOffset =
                  (currentTime - src.bufStartTime) * src.playbackRate;
                break;
              }
              src.bufStartTime = nextStartTime;
            }
            src.bufOffset = 0;
            src.bufsProcessed++;
          }
        }
        return currentTime;
      },
      cancelPendingSourceAudio: (src) => {
        AL.updateSourceTime(src);
        for (var i = 1; i < src.audioQueue.length; i++) {
          var audioSrc = src.audioQueue[i];
          audioSrc.stop();
        }
        if (src.audioQueue.length > 1) {
          src.audioQueue.length = 1;
        }
      },
      stopSourceAudio: (src) => {
        for (var i = 0; i < src.audioQueue.length; i++) {
          src.audioQueue[i].stop();
        }
        src.audioQueue.length = 0;
      },
      setSourceState: (src, state) => {
        if (state === 4114) {
          if (src.state === 4114 || src.state == 4116) {
            src.bufsProcessed = 0;
            src.bufOffset = 0;
          } else {
          }
          AL.stopSourceAudio(src);
          src.state = 4114;
          src.bufStartTime = Number.NEGATIVE_INFINITY;
          AL.scheduleSourceAudio(src);
        } else if (state === 4115) {
          if (src.state === 4114) {
            AL.updateSourceTime(src);
            AL.stopSourceAudio(src);
            src.state = 4115;
          }
        } else if (state === 4116) {
          if (src.state !== 4113) {
            src.state = 4116;
            src.bufsProcessed = src.bufQueue.length;
            src.bufStartTime = Number.NEGATIVE_INFINITY;
            src.bufOffset = 0;
            AL.stopSourceAudio(src);
          }
        } else if (state === 4113) {
          if (src.state !== 4113) {
            src.state = 4113;
            src.bufsProcessed = 0;
            src.bufStartTime = Number.NEGATIVE_INFINITY;
            src.bufOffset = 0;
            AL.stopSourceAudio(src);
          }
        }
      },
      initSourcePanner: (src) => {
        if (src.type === 4144) {
          return;
        }
        var templateBuf = AL.buffers[0];
        for (var i = 0; i < src.bufQueue.length; i++) {
          if (src.bufQueue[i].id !== 0) {
            templateBuf = src.bufQueue[i];
            break;
          }
        }
        if (
          src.spatialize === 1 ||
          (src.spatialize === 2 && templateBuf.channels === 1)
        ) {
          if (src.panner) {
            return;
          }
          src.panner = src.context.audioCtx.createPanner();
          AL.updateSourceGlobal(src);
          AL.updateSourceSpace(src);
          src.panner.connect(src.context.gain);
          src.gain.disconnect();
          src.gain.connect(src.panner);
        } else {
          if (!src.panner) {
            return;
          }
          src.panner.disconnect();
          src.gain.disconnect();
          src.gain.connect(src.context.gain);
          src.panner = null;
        }
      },
      updateContextGlobal: (ctx) => {
        for (var i in ctx.sources) {
          AL.updateSourceGlobal(ctx.sources[i]);
        }
      },
      updateSourceGlobal: (src) => {
        var panner = src.panner;
        if (!panner) {
          return;
        }
        panner.refDistance = src.refDistance;
        panner.maxDistance = src.maxDistance;
        panner.rolloffFactor = src.rolloffFactor;
        panner.panningModel = src.context.hrtf ? "HRTF" : "equalpower";
        var distanceModel = src.context.sourceDistanceModel
          ? src.distanceModel
          : src.context.distanceModel;
        switch (distanceModel) {
          case 0:
            panner.distanceModel = "inverse";
            panner.refDistance = 340282e33;
            break;
          case 53249:
          case 53250:
            panner.distanceModel = "inverse";
            break;
          case 53251:
          case 53252:
            panner.distanceModel = "linear";
            break;
          case 53253:
          case 53254:
            panner.distanceModel = "exponential";
            break;
        }
      },
      updateListenerSpace: (ctx) => {
        var listener = ctx.audioCtx.listener;
        if (listener.positionX) {
          listener.positionX.value = ctx.listener.position[0];
          listener.positionY.value = ctx.listener.position[1];
          listener.positionZ.value = ctx.listener.position[2];
        } else {
          listener.setPosition(
            ctx.listener.position[0],
            ctx.listener.position[1],
            ctx.listener.position[2],
          );
        }
        if (listener.forwardX) {
          listener.forwardX.value = ctx.listener.direction[0];
          listener.forwardY.value = ctx.listener.direction[1];
          listener.forwardZ.value = ctx.listener.direction[2];
          listener.upX.value = ctx.listener.up[0];
          listener.upY.value = ctx.listener.up[1];
          listener.upZ.value = ctx.listener.up[2];
        } else {
          listener.setOrientation(
            ctx.listener.direction[0],
            ctx.listener.direction[1],
            ctx.listener.direction[2],
            ctx.listener.up[0],
            ctx.listener.up[1],
            ctx.listener.up[2],
          );
        }
        for (var i in ctx.sources) {
          AL.updateSourceSpace(ctx.sources[i]);
        }
      },
      updateSourceSpace: (src) => {
        if (!src.panner) {
          return;
        }
        var panner = src.panner;
        var posX = src.position[0];
        var posY = src.position[1];
        var posZ = src.position[2];
        var dirX = src.direction[0];
        var dirY = src.direction[1];
        var dirZ = src.direction[2];
        var listener = src.context.listener;
        var lPosX = listener.position[0];
        var lPosY = listener.position[1];
        var lPosZ = listener.position[2];
        if (src.relative) {
          var lBackX = -listener.direction[0];
          var lBackY = -listener.direction[1];
          var lBackZ = -listener.direction[2];
          var lUpX = listener.up[0];
          var lUpY = listener.up[1];
          var lUpZ = listener.up[2];
          var inverseMagnitude = (x, y, z) => {
            var length = Math.sqrt(x * x + y * y + z * z);
            if (length < Number.EPSILON) {
              return 0;
            }
            return 1 / length;
          };
          var invMag = inverseMagnitude(lBackX, lBackY, lBackZ);
          lBackX *= invMag;
          lBackY *= invMag;
          lBackZ *= invMag;
          invMag = inverseMagnitude(lUpX, lUpY, lUpZ);
          lUpX *= invMag;
          lUpY *= invMag;
          lUpZ *= invMag;
          var lRightX = lUpY * lBackZ - lUpZ * lBackY;
          var lRightY = lUpZ * lBackX - lUpX * lBackZ;
          var lRightZ = lUpX * lBackY - lUpY * lBackX;
          invMag = inverseMagnitude(lRightX, lRightY, lRightZ);
          lRightX *= invMag;
          lRightY *= invMag;
          lRightZ *= invMag;
          lUpX = lBackY * lRightZ - lBackZ * lRightY;
          lUpY = lBackZ * lRightX - lBackX * lRightZ;
          lUpZ = lBackX * lRightY - lBackY * lRightX;
          var oldX = dirX;
          var oldY = dirY;
          var oldZ = dirZ;
          dirX = oldX * lRightX + oldY * lUpX + oldZ * lBackX;
          dirY = oldX * lRightY + oldY * lUpY + oldZ * lBackY;
          dirZ = oldX * lRightZ + oldY * lUpZ + oldZ * lBackZ;
          oldX = posX;
          oldY = posY;
          oldZ = posZ;
          posX = oldX * lRightX + oldY * lUpX + oldZ * lBackX;
          posY = oldX * lRightY + oldY * lUpY + oldZ * lBackY;
          posZ = oldX * lRightZ + oldY * lUpZ + oldZ * lBackZ;
          posX += lPosX;
          posY += lPosY;
          posZ += lPosZ;
        }
        if (panner.positionX) {
          if (posX != panner.positionX.value) panner.positionX.value = posX;
          if (posY != panner.positionY.value) panner.positionY.value = posY;
          if (posZ != panner.positionZ.value) panner.positionZ.value = posZ;
        } else {
          panner.setPosition(posX, posY, posZ);
        }
        if (panner.orientationX) {
          if (dirX != panner.orientationX.value)
            panner.orientationX.value = dirX;
          if (dirY != panner.orientationY.value)
            panner.orientationY.value = dirY;
          if (dirZ != panner.orientationZ.value)
            panner.orientationZ.value = dirZ;
        } else {
          panner.setOrientation(dirX, dirY, dirZ);
        }
        var oldShift = src.dopplerShift;
        var velX = src.velocity[0];
        var velY = src.velocity[1];
        var velZ = src.velocity[2];
        var lVelX = listener.velocity[0];
        var lVelY = listener.velocity[1];
        var lVelZ = listener.velocity[2];
        if (
          (posX === lPosX && posY === lPosY && posZ === lPosZ) ||
          (velX === lVelX && velY === lVelY && velZ === lVelZ)
        ) {
          src.dopplerShift = 1;
        } else {
          var speedOfSound = src.context.speedOfSound;
          var dopplerFactor = src.context.dopplerFactor;
          var slX = lPosX - posX;
          var slY = lPosY - posY;
          var slZ = lPosZ - posZ;
          var magSl = Math.sqrt(slX * slX + slY * slY + slZ * slZ);
          var vls = (slX * lVelX + slY * lVelY + slZ * lVelZ) / magSl;
          var vss = (slX * velX + slY * velY + slZ * velZ) / magSl;
          vls = Math.min(vls, speedOfSound / dopplerFactor);
          vss = Math.min(vss, speedOfSound / dopplerFactor);
          src.dopplerShift =
            (speedOfSound - dopplerFactor * vls) /
            (speedOfSound - dopplerFactor * vss);
        }
        if (src.dopplerShift !== oldShift) {
          AL.updateSourceRate(src);
        }
      },
      updateSourceRate: (src) => {
        if (src.state === 4114) {
          AL.cancelPendingSourceAudio(src);
          var audioSrc = src.audioQueue[0];
          if (!audioSrc) {
            return;
          }
          var duration;
          if (src.type === 4136 && src.looping) {
            duration = Number.POSITIVE_INFINITY;
          } else {
            duration =
              (audioSrc.buffer.duration - audioSrc._startOffset) /
              src.playbackRate;
          }
          audioSrc._duration = duration;
          audioSrc.playbackRate.value = src.playbackRate;
          AL.scheduleSourceAudio(src);
        }
      },
      sourceDuration: (src) => {
        var length = 0;
        for (var i = 0; i < src.bufQueue.length; i++) {
          var audioBuf = src.bufQueue[i].audioBuf;
          length += audioBuf ? audioBuf.duration : 0;
        }
        return length;
      },
      sourceTell: (src) => {
        AL.updateSourceTime(src);
        var offset = 0;
        for (var i = 0; i < src.bufsProcessed; i++) {
          if (src.bufQueue[i].audioBuf) {
            offset += src.bufQueue[i].audioBuf.duration;
          }
        }
        offset += src.bufOffset;
        return offset;
      },
      sourceSeek: (src, offset) => {
        var playing = src.state == 4114;
        if (playing) {
          AL.setSourceState(src, 4113);
        }
        if (src.bufQueue[src.bufsProcessed].audioBuf !== null) {
          src.bufsProcessed = 0;
          while (offset > src.bufQueue[src.bufsProcessed].audioBuf.duration) {
            offset -= src.bufQueue[src.bufsProcessed].audiobuf.duration;
            src.bufsProcessed++;
          }
          src.bufOffset = offset;
        }
        if (playing) {
          AL.setSourceState(src, 4114);
        }
      },
      getGlobalParam: (funcname, param) => {
        if (!AL.currentCtx) {
          return null;
        }
        switch (param) {
          case 49152:
            return AL.currentCtx.dopplerFactor;
          case 49155:
            return AL.currentCtx.speedOfSound;
          case 53248:
            return AL.currentCtx.distanceModel;
          default:
            AL.currentCtx.err = 40962;
            return null;
        }
      },
      setGlobalParam: (funcname, param, value) => {
        if (!AL.currentCtx) {
          return;
        }
        switch (param) {
          case 49152:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.currentCtx.dopplerFactor = value;
            AL.updateListenerSpace(AL.currentCtx);
            break;
          case 49155:
            if (!Number.isFinite(value) || value <= 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.currentCtx.speedOfSound = value;
            AL.updateListenerSpace(AL.currentCtx);
            break;
          case 53248:
            switch (value) {
              case 0:
              case 53249:
              case 53250:
              case 53251:
              case 53252:
              case 53253:
              case 53254:
                AL.currentCtx.distanceModel = value;
                AL.updateContextGlobal(AL.currentCtx);
                break;
              default:
                AL.currentCtx.err = 40963;
                return;
            }
            break;
          default:
            AL.currentCtx.err = 40962;
            return;
        }
      },
      getListenerParam: (funcname, param) => {
        if (!AL.currentCtx) {
          return null;
        }
        switch (param) {
          case 4100:
            return AL.currentCtx.listener.position;
          case 4102:
            return AL.currentCtx.listener.velocity;
          case 4111:
            return AL.currentCtx.listener.direction.concat(
              AL.currentCtx.listener.up,
            );
          case 4106:
            return AL.currentCtx.gain.gain.value;
          default:
            AL.currentCtx.err = 40962;
            return null;
        }
      },
      setListenerParam: (funcname, param, value) => {
        if (!AL.currentCtx) {
          return;
        }
        if (value === null) {
          AL.currentCtx.err = 40962;
          return;
        }
        var listener = AL.currentCtx.listener;
        switch (param) {
          case 4100:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            listener.position[0] = value[0];
            listener.position[1] = value[1];
            listener.position[2] = value[2];
            AL.updateListenerSpace(AL.currentCtx);
            break;
          case 4102:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            listener.velocity[0] = value[0];
            listener.velocity[1] = value[1];
            listener.velocity[2] = value[2];
            AL.updateListenerSpace(AL.currentCtx);
            break;
          case 4106:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.currentCtx.gain.gain.value = value;
            break;
          case 4111:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2]) ||
              !Number.isFinite(value[3]) ||
              !Number.isFinite(value[4]) ||
              !Number.isFinite(value[5])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            listener.direction[0] = value[0];
            listener.direction[1] = value[1];
            listener.direction[2] = value[2];
            listener.up[0] = value[3];
            listener.up[1] = value[4];
            listener.up[2] = value[5];
            AL.updateListenerSpace(AL.currentCtx);
            break;
          default:
            AL.currentCtx.err = 40962;
            return;
        }
      },
      getBufferParam: (funcname, bufferId, param) => {
        if (!AL.currentCtx) {
          return;
        }
        var buf = AL.buffers[bufferId];
        if (!buf || bufferId === 0) {
          AL.currentCtx.err = 40961;
          return;
        }
        switch (param) {
          case 8193:
            return buf.frequency;
          case 8194:
            return buf.bytesPerSample * 8;
          case 8195:
            return buf.channels;
          case 8196:
            return buf.length * buf.bytesPerSample * buf.channels;
          case 8213:
            if (buf.length === 0) {
              return [0, 0];
            }
            return [
              (buf.audioBuf._loopStart || 0) * buf.frequency,
              (buf.audioBuf._loopEnd || buf.length) * buf.frequency,
            ];
          default:
            AL.currentCtx.err = 40962;
            return null;
        }
      },
      setBufferParam: (funcname, bufferId, param, value) => {
        if (!AL.currentCtx) {
          return;
        }
        var buf = AL.buffers[bufferId];
        if (!buf || bufferId === 0) {
          AL.currentCtx.err = 40961;
          return;
        }
        if (value === null) {
          AL.currentCtx.err = 40962;
          return;
        }
        switch (param) {
          case 8196:
            if (value !== 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            break;
          case 8213:
            if (
              value[0] < 0 ||
              value[0] > buf.length ||
              value[1] < 0 ||
              value[1] > buf.Length ||
              value[0] >= value[1]
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            if (buf.refCount > 0) {
              AL.currentCtx.err = 40964;
              return;
            }
            if (buf.audioBuf) {
              buf.audioBuf._loopStart = value[0] / buf.frequency;
              buf.audioBuf._loopEnd = value[1] / buf.frequency;
            }
            break;
          default:
            AL.currentCtx.err = 40962;
            return;
        }
      },
      getSourceParam: (funcname, sourceId, param) => {
        if (!AL.currentCtx) {
          return null;
        }
        var src = AL.currentCtx.sources[sourceId];
        if (!src) {
          AL.currentCtx.err = 40961;
          return null;
        }
        switch (param) {
          case 514:
            return src.relative;
          case 4097:
            return src.coneInnerAngle;
          case 4098:
            return src.coneOuterAngle;
          case 4099:
            return src.pitch;
          case 4100:
            return src.position;
          case 4101:
            return src.direction;
          case 4102:
            return src.velocity;
          case 4103:
            return src.looping;
          case 4105:
            if (src.type === 4136) {
              return src.bufQueue[0].id;
            }
            return 0;
          case 4106:
            return src.gain.gain.value;
          case 4109:
            return src.minGain;
          case 4110:
            return src.maxGain;
          case 4112:
            return src.state;
          case 4117:
            if (src.bufQueue.length === 1 && src.bufQueue[0].id === 0) {
              return 0;
            }
            return src.bufQueue.length;
          case 4118:
            if (
              (src.bufQueue.length === 1 && src.bufQueue[0].id === 0) ||
              src.looping
            ) {
              return 0;
            }
            return src.bufsProcessed;
          case 4128:
            return src.refDistance;
          case 4129:
            return src.rolloffFactor;
          case 4130:
            return src.coneOuterGain;
          case 4131:
            return src.maxDistance;
          case 4132:
            return AL.sourceTell(src);
          case 4133:
            var offset = AL.sourceTell(src);
            if (offset > 0) {
              offset *= src.bufQueue[0].frequency;
            }
            return offset;
          case 4134:
            var offset = AL.sourceTell(src);
            if (offset > 0) {
              offset *=
                src.bufQueue[0].frequency * src.bufQueue[0].bytesPerSample;
            }
            return offset;
          case 4135:
            return src.type;
          case 4628:
            return src.spatialize;
          case 8201:
            var length = 0;
            var bytesPerFrame = 0;
            for (var i = 0; i < src.bufQueue.length; i++) {
              length += src.bufQueue[i].length;
              if (src.bufQueue[i].id !== 0) {
                bytesPerFrame =
                  src.bufQueue[i].bytesPerSample * src.bufQueue[i].channels;
              }
            }
            return length * bytesPerFrame;
          case 8202:
            var length = 0;
            for (var i = 0; i < src.bufQueue.length; i++) {
              length += src.bufQueue[i].length;
            }
            return length;
          case 8203:
            return AL.sourceDuration(src);
          case 53248:
            return src.distanceModel;
          default:
            AL.currentCtx.err = 40962;
            return null;
        }
      },
      setSourceParam: (funcname, sourceId, param, value) => {
        if (!AL.currentCtx) {
          return;
        }
        var src = AL.currentCtx.sources[sourceId];
        if (!src) {
          AL.currentCtx.err = 40961;
          return;
        }
        if (value === null) {
          AL.currentCtx.err = 40962;
          return;
        }
        switch (param) {
          case 514:
            if (value === 1) {
              src.relative = true;
              AL.updateSourceSpace(src);
            } else if (value === 0) {
              src.relative = false;
              AL.updateSourceSpace(src);
            } else {
              AL.currentCtx.err = 40963;
              return;
            }
            break;
          case 4097:
            if (!Number.isFinite(value)) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.coneInnerAngle = value;
            if (src.panner) {
              src.panner.coneInnerAngle = value % 360;
            }
            break;
          case 4098:
            if (!Number.isFinite(value)) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.coneOuterAngle = value;
            if (src.panner) {
              src.panner.coneOuterAngle = value % 360;
            }
            break;
          case 4099:
            if (!Number.isFinite(value) || value <= 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            if (src.pitch === value) {
              break;
            }
            src.pitch = value;
            AL.updateSourceRate(src);
            break;
          case 4100:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.position[0] = value[0];
            src.position[1] = value[1];
            src.position[2] = value[2];
            AL.updateSourceSpace(src);
            break;
          case 4101:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.direction[0] = value[0];
            src.direction[1] = value[1];
            src.direction[2] = value[2];
            AL.updateSourceSpace(src);
            break;
          case 4102:
            if (
              !Number.isFinite(value[0]) ||
              !Number.isFinite(value[1]) ||
              !Number.isFinite(value[2])
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.velocity[0] = value[0];
            src.velocity[1] = value[1];
            src.velocity[2] = value[2];
            AL.updateSourceSpace(src);
            break;
          case 4103:
            if (value === 1) {
              src.looping = true;
              AL.updateSourceTime(src);
              if (src.type === 4136 && src.audioQueue.length > 0) {
                var audioSrc = src.audioQueue[0];
                audioSrc.loop = true;
                audioSrc._duration = Number.POSITIVE_INFINITY;
              }
            } else if (value === 0) {
              src.looping = false;
              var currentTime = AL.updateSourceTime(src);
              if (src.type === 4136 && src.audioQueue.length > 0) {
                var audioSrc = src.audioQueue[0];
                audioSrc.loop = false;
                audioSrc._duration =
                  src.bufQueue[0].audioBuf.duration / src.playbackRate;
                audioSrc._startTime =
                  currentTime - src.bufOffset / src.playbackRate;
              }
            } else {
              AL.currentCtx.err = 40963;
              return;
            }
            break;
          case 4105:
            if (src.state === 4114 || src.state === 4115) {
              AL.currentCtx.err = 40964;
              return;
            }
            if (value === 0) {
              for (var i in src.bufQueue) {
                src.bufQueue[i].refCount--;
              }
              src.bufQueue.length = 1;
              src.bufQueue[0] = AL.buffers[0];
              src.bufsProcessed = 0;
              src.type = 4144;
            } else {
              var buf = AL.buffers[value];
              if (!buf) {
                AL.currentCtx.err = 40963;
                return;
              }
              for (var i in src.bufQueue) {
                src.bufQueue[i].refCount--;
              }
              src.bufQueue.length = 0;
              buf.refCount++;
              src.bufQueue = [buf];
              src.bufsProcessed = 0;
              src.type = 4136;
            }
            AL.initSourcePanner(src);
            AL.scheduleSourceAudio(src);
            break;
          case 4106:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.gain.gain.value = value;
            break;
          case 4109:
            if (
              !Number.isFinite(value) ||
              value < 0 ||
              value > Math.min(src.maxGain, 1)
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.minGain = value;
            break;
          case 4110:
            if (
              !Number.isFinite(value) ||
              value < Math.max(0, src.minGain) ||
              value > 1
            ) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.maxGain = value;
            break;
          case 4128:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.refDistance = value;
            if (src.panner) {
              src.panner.refDistance = value;
            }
            break;
          case 4129:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.rolloffFactor = value;
            if (src.panner) {
              src.panner.rolloffFactor = value;
            }
            break;
          case 4130:
            if (!Number.isFinite(value) || value < 0 || value > 1) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.coneOuterGain = value;
            if (src.panner) {
              src.panner.coneOuterGain = value;
            }
            break;
          case 4131:
            if (!Number.isFinite(value) || value < 0) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.maxDistance = value;
            if (src.panner) {
              src.panner.maxDistance = value;
            }
            break;
          case 4132:
            if (value < 0 || value > AL.sourceDuration(src)) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.sourceSeek(src, value);
            break;
          case 4133:
            var srcLen = AL.sourceDuration(src);
            if (srcLen > 0) {
              var frequency;
              for (var bufId in src.bufQueue) {
                if (bufId) {
                  frequency = src.bufQueue[bufId].frequency;
                  break;
                }
              }
              value /= frequency;
            }
            if (value < 0 || value > srcLen) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.sourceSeek(src, value);
            break;
          case 4134:
            var srcLen = AL.sourceDuration(src);
            if (srcLen > 0) {
              var bytesPerSec;
              for (var bufId in src.bufQueue) {
                if (bufId) {
                  var buf = src.bufQueue[bufId];
                  bytesPerSec =
                    buf.frequency * buf.bytesPerSample * buf.channels;
                  break;
                }
              }
              value /= bytesPerSec;
            }
            if (value < 0 || value > srcLen) {
              AL.currentCtx.err = 40963;
              return;
            }
            AL.sourceSeek(src, value);
            break;
          case 4628:
            if (value !== 0 && value !== 1 && value !== 2) {
              AL.currentCtx.err = 40963;
              return;
            }
            src.spatialize = value;
            AL.initSourcePanner(src);
            break;
          case 8201:
          case 8202:
          case 8203:
            AL.currentCtx.err = 40964;
            break;
          case 53248:
            switch (value) {
              case 0:
              case 53249:
              case 53250:
              case 53251:
              case 53252:
              case 53253:
              case 53254:
                src.distanceModel = value;
                if (AL.currentCtx.sourceDistanceModel) {
                  AL.updateContextGlobal(AL.currentCtx);
                }
                break;
              default:
                AL.currentCtx.err = 40963;
                return;
            }
            break;
          default:
            AL.currentCtx.err = 40962;
            return;
        }
      },
      captures: {},
      sharedCaptureAudioCtx: null,
      requireValidCaptureDevice: (deviceId, funcname) => {
        if (deviceId === 0) {
          AL.alcErr = 40961;
          return null;
        }
        var c = AL.captures[deviceId];
        if (!c) {
          AL.alcErr = 40961;
          return null;
        }
        var err = c.mediaStreamError;
        if (err) {
          AL.alcErr = 40961;
          return null;
        }
        return c;
      },
    };
    function _alBufferData(bufferId, format, pData, size, freq) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(19, 1, bufferId, format, pData, size, freq);
      if (!AL.currentCtx) {
        return;
      }
      var buf = AL.buffers[bufferId];
      if (!buf) {
        AL.currentCtx.err = 40963;
        return;
      }
      if (freq <= 0) {
        AL.currentCtx.err = 40963;
        return;
      }
      var audioBuf = null;
      try {
        switch (format) {
          case 4352:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(1, size, freq);
              var channel0 = audioBuf.getChannelData(0);
              for (var i = 0; i < size; ++i) {
                channel0[i] = GROWABLE_HEAP_U8()[pData++] * 0.0078125 - 1;
              }
            }
            buf.bytesPerSample = 1;
            buf.channels = 1;
            buf.length = size;
            break;
          case 4353:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(
                1,
                size >> 1,
                freq,
              );
              var channel0 = audioBuf.getChannelData(0);
              pData >>= 1;
              for (var i = 0; i < size >> 1; ++i) {
                channel0[i] = GROWABLE_HEAP_I16()[pData++] * 30517578125e-15;
              }
            }
            buf.bytesPerSample = 2;
            buf.channels = 1;
            buf.length = size >> 1;
            break;
          case 4354:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(
                2,
                size >> 1,
                freq,
              );
              var channel0 = audioBuf.getChannelData(0);
              var channel1 = audioBuf.getChannelData(1);
              for (var i = 0; i < size >> 1; ++i) {
                channel0[i] = GROWABLE_HEAP_U8()[pData++] * 0.0078125 - 1;
                channel1[i] = GROWABLE_HEAP_U8()[pData++] * 0.0078125 - 1;
              }
            }
            buf.bytesPerSample = 1;
            buf.channels = 2;
            buf.length = size >> 1;
            break;
          case 4355:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(
                2,
                size >> 2,
                freq,
              );
              var channel0 = audioBuf.getChannelData(0);
              var channel1 = audioBuf.getChannelData(1);
              pData >>= 1;
              for (var i = 0; i < size >> 2; ++i) {
                channel0[i] = GROWABLE_HEAP_I16()[pData++] * 30517578125e-15;
                channel1[i] = GROWABLE_HEAP_I16()[pData++] * 30517578125e-15;
              }
            }
            buf.bytesPerSample = 2;
            buf.channels = 2;
            buf.length = size >> 2;
            break;
          case 65552:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(
                1,
                size >> 2,
                freq,
              );
              var channel0 = audioBuf.getChannelData(0);
              pData >>= 2;
              for (var i = 0; i < size >> 2; ++i) {
                channel0[i] = GROWABLE_HEAP_F32()[pData++];
              }
            }
            buf.bytesPerSample = 4;
            buf.channels = 1;
            buf.length = size >> 2;
            break;
          case 65553:
            if (size > 0) {
              audioBuf = AL.currentCtx.audioCtx.createBuffer(
                2,
                size >> 3,
                freq,
              );
              var channel0 = audioBuf.getChannelData(0);
              var channel1 = audioBuf.getChannelData(1);
              pData >>= 2;
              for (var i = 0; i < size >> 3; ++i) {
                channel0[i] = GROWABLE_HEAP_F32()[pData++];
                channel1[i] = GROWABLE_HEAP_F32()[pData++];
              }
            }
            buf.bytesPerSample = 4;
            buf.channels = 2;
            buf.length = size >> 3;
            break;
          default:
            AL.currentCtx.err = 40963;
            return;
        }
        buf.frequency = freq;
        buf.audioBuf = audioBuf;
      } catch (e) {
        AL.currentCtx.err = 40963;
        return;
      }
    }
    function _alDeleteBuffers(count, pBufferIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(20, 1, count, pBufferIds);
      if (!AL.currentCtx) {
        return;
      }
      for (var i = 0; i < count; ++i) {
        var bufId = GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2];
        if (bufId === 0) {
          continue;
        }
        if (!AL.buffers[bufId]) {
          AL.currentCtx.err = 40961;
          return;
        }
        if (AL.buffers[bufId].refCount) {
          AL.currentCtx.err = 40964;
          return;
        }
      }
      for (var i = 0; i < count; ++i) {
        var bufId = GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2];
        if (bufId === 0) {
          continue;
        }
        AL.deviceRefCounts[AL.buffers[bufId].deviceId]--;
        delete AL.buffers[bufId];
        AL.freeIds.push(bufId);
      }
    }
    function _alSourcei(sourceId, param, value) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(22, 1, sourceId, param, value);
      switch (param) {
        case 514:
        case 4097:
        case 4098:
        case 4103:
        case 4105:
        case 4128:
        case 4129:
        case 4131:
        case 4132:
        case 4133:
        case 4134:
        case 4628:
        case 8201:
        case 8202:
        case 53248:
          AL.setSourceParam("alSourcei", sourceId, param, value);
          break;
        default:
          AL.setSourceParam("alSourcei", sourceId, param, null);
          break;
      }
    }
    function _alDeleteSources(count, pSourceIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(21, 1, count, pSourceIds);
      if (!AL.currentCtx) {
        return;
      }
      for (var i = 0; i < count; ++i) {
        var srcId = GROWABLE_HEAP_I32()[(pSourceIds + i * 4) >> 2];
        if (!AL.currentCtx.sources[srcId]) {
          AL.currentCtx.err = 40961;
          return;
        }
      }
      for (var i = 0; i < count; ++i) {
        var srcId = GROWABLE_HEAP_I32()[(pSourceIds + i * 4) >> 2];
        AL.setSourceState(AL.currentCtx.sources[srcId], 4116);
        _alSourcei(srcId, 4105, 0);
        delete AL.currentCtx.sources[srcId];
        AL.freeIds.push(srcId);
      }
    }
    function _alGenBuffers(count, pBufferIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(23, 1, count, pBufferIds);
      if (!AL.currentCtx) {
        return;
      }
      for (var i = 0; i < count; ++i) {
        var buf = {
          deviceId: AL.currentCtx.deviceId,
          id: AL.newId(),
          refCount: 0,
          audioBuf: null,
          frequency: 0,
          bytesPerSample: 2,
          channels: 1,
          length: 0,
        };
        AL.deviceRefCounts[buf.deviceId]++;
        AL.buffers[buf.id] = buf;
        GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2] = buf.id;
      }
    }
    function _alGenSources(count, pSourceIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(24, 1, count, pSourceIds);
      if (!AL.currentCtx) {
        return;
      }
      for (var i = 0; i < count; ++i) {
        var gain = AL.currentCtx.audioCtx.createGain();
        gain.connect(AL.currentCtx.gain);
        var src = {
          context: AL.currentCtx,
          id: AL.newId(),
          type: 4144,
          state: 4113,
          bufQueue: [AL.buffers[0]],
          audioQueue: [],
          looping: false,
          pitch: 1,
          dopplerShift: 1,
          gain: gain,
          minGain: 0,
          maxGain: 1,
          panner: null,
          bufsProcessed: 0,
          bufStartTime: Number.NEGATIVE_INFINITY,
          bufOffset: 0,
          relative: false,
          refDistance: 1,
          maxDistance: 340282e33,
          rolloffFactor: 1,
          position: [0, 0, 0],
          velocity: [0, 0, 0],
          direction: [0, 0, 0],
          coneOuterGain: 0,
          coneInnerAngle: 360,
          coneOuterAngle: 360,
          distanceModel: 53250,
          spatialize: 2,
          get playbackRate() {
            return this.pitch * this.dopplerShift;
          },
        };
        AL.currentCtx.sources[src.id] = src;
        GROWABLE_HEAP_I32()[(pSourceIds + i * 4) >> 2] = src.id;
      }
    }
    function _alGetError() {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(25, 1);
      if (!AL.currentCtx) {
        return 40964;
      }
      var err = AL.currentCtx.err;
      AL.currentCtx.err = 0;
      return err;
    }
    function _alGetSourcei(sourceId, param, pValue) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(26, 1, sourceId, param, pValue);
      var val = AL.getSourceParam("alGetSourcei", sourceId, param);
      if (val === null) {
        return;
      }
      if (!pValue) {
        AL.currentCtx.err = 40963;
        return;
      }
      switch (param) {
        case 514:
        case 4097:
        case 4098:
        case 4103:
        case 4105:
        case 4112:
        case 4117:
        case 4118:
        case 4128:
        case 4129:
        case 4131:
        case 4132:
        case 4133:
        case 4134:
        case 4135:
        case 4628:
        case 8201:
        case 8202:
        case 53248:
          GROWABLE_HEAP_I32()[pValue >> 2] = val;
          break;
        default:
          AL.currentCtx.err = 40962;
          return;
      }
    }
    function _alSourcePlay(sourceId) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(27, 1, sourceId);
      if (!AL.currentCtx) {
        return;
      }
      var src = AL.currentCtx.sources[sourceId];
      if (!src) {
        AL.currentCtx.err = 40961;
        return;
      }
      AL.setSourceState(src, 4114);
    }
    function _alSourceQueueBuffers(sourceId, count, pBufferIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(28, 1, sourceId, count, pBufferIds);
      if (!AL.currentCtx) {
        return;
      }
      var src = AL.currentCtx.sources[sourceId];
      if (!src) {
        AL.currentCtx.err = 40961;
        return;
      }
      if (src.type === 4136) {
        AL.currentCtx.err = 40964;
        return;
      }
      if (count === 0) {
        return;
      }
      var templateBuf = AL.buffers[0];
      for (var i = 0; i < src.bufQueue.length; i++) {
        if (src.bufQueue[i].id !== 0) {
          templateBuf = src.bufQueue[i];
          break;
        }
      }
      for (var i = 0; i < count; ++i) {
        var bufId = GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2];
        var buf = AL.buffers[bufId];
        if (!buf) {
          AL.currentCtx.err = 40961;
          return;
        }
        if (
          templateBuf.id !== 0 &&
          (buf.frequency !== templateBuf.frequency ||
            buf.bytesPerSample !== templateBuf.bytesPerSample ||
            buf.channels !== templateBuf.channels)
        ) {
          AL.currentCtx.err = 40964;
        }
      }
      if (src.bufQueue.length === 1 && src.bufQueue[0].id === 0) {
        src.bufQueue.length = 0;
      }
      src.type = 4137;
      for (var i = 0; i < count; ++i) {
        var bufId = GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2];
        var buf = AL.buffers[bufId];
        buf.refCount++;
        src.bufQueue.push(buf);
      }
      if (src.looping) {
        AL.cancelPendingSourceAudio(src);
      }
      AL.initSourcePanner(src);
      AL.scheduleSourceAudio(src);
    }
    function _alSourceStop(sourceId) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(29, 1, sourceId);
      if (!AL.currentCtx) {
        return;
      }
      var src = AL.currentCtx.sources[sourceId];
      if (!src) {
        AL.currentCtx.err = 40961;
        return;
      }
      AL.setSourceState(src, 4116);
    }
    function _alSourceUnqueueBuffers(sourceId, count, pBufferIds) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(30, 1, sourceId, count, pBufferIds);
      if (!AL.currentCtx) {
        return;
      }
      var src = AL.currentCtx.sources[sourceId];
      if (!src) {
        AL.currentCtx.err = 40961;
        return;
      }
      if (
        count >
        (src.bufQueue.length === 1 && src.bufQueue[0].id === 0
          ? 0
          : src.bufsProcessed)
      ) {
        AL.currentCtx.err = 40963;
        return;
      }
      if (count === 0) {
        return;
      }
      for (var i = 0; i < count; i++) {
        var buf = src.bufQueue.shift();
        buf.refCount--;
        GROWABLE_HEAP_I32()[(pBufferIds + i * 4) >> 2] = buf.id;
        src.bufsProcessed--;
      }
      if (src.bufQueue.length === 0) {
        src.bufQueue.push(AL.buffers[0]);
      }
      AL.initSourcePanner(src);
      AL.scheduleSourceAudio(src);
    }
    function _alcCloseDevice(deviceId) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(31, 1, deviceId);
      if (
        !(deviceId in AL.deviceRefCounts) ||
        AL.deviceRefCounts[deviceId] > 0
      ) {
        return 0;
      }
      delete AL.deviceRefCounts[deviceId];
      AL.freeIds.push(deviceId);
      return 1;
    }
    var listenOnce = (object, event, func) => {
      object.addEventListener(event, func, { once: true });
    };
    var autoResumeAudioContext = (ctx, elements) => {
      if (!elements) {
        elements = [document, document.getElementById("canvas")];
      }
      ["keydown", "mousedown", "touchstart"].forEach((event) => {
        elements.forEach((element) => {
          if (element) {
            listenOnce(element, event, () => {
              if (ctx.state === "suspended") ctx.resume();
            });
          }
        });
      });
    };
    function _alcCreateContext(deviceId, pAttrList) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(32, 1, deviceId, pAttrList);
      if (!(deviceId in AL.deviceRefCounts)) {
        AL.alcErr = 40961;
        return 0;
      }
      var options = null;
      var attrs = [];
      var hrtf = null;
      pAttrList >>= 2;
      if (pAttrList) {
        var attr = 0;
        var val = 0;
        while (true) {
          attr = GROWABLE_HEAP_I32()[pAttrList++];
          attrs.push(attr);
          if (attr === 0) {
            break;
          }
          val = GROWABLE_HEAP_I32()[pAttrList++];
          attrs.push(val);
          switch (attr) {
            case 4103:
              if (!options) {
                options = {};
              }
              options.sampleRate = val;
              break;
            case 4112:
            case 4113:
              break;
            case 6546:
              switch (val) {
                case 0:
                  hrtf = false;
                  break;
                case 1:
                  hrtf = true;
                  break;
                case 2:
                  break;
                default:
                  AL.alcErr = 40964;
                  return 0;
              }
              break;
            case 6550:
              if (val !== 0) {
                AL.alcErr = 40964;
                return 0;
              }
              break;
            default:
              AL.alcErr = 40964;
              return 0;
          }
        }
      }
      var AudioContext = window.AudioContext || window.webkitAudioContext;
      var ac = null;
      try {
        if (options) {
          ac = new AudioContext(options);
        } else {
          ac = new AudioContext();
        }
      } catch (e) {
        if (e.name === "NotSupportedError") {
          AL.alcErr = 40964;
        } else {
          AL.alcErr = 40961;
        }
        return 0;
      }
      autoResumeAudioContext(ac);
      if (typeof ac.createGain == "undefined") {
        ac.createGain = ac.createGainNode;
      }
      var gain = ac.createGain();
      gain.connect(ac.destination);
      var ctx = {
        deviceId: deviceId,
        id: AL.newId(),
        attrs: attrs,
        audioCtx: ac,
        listener: {
          position: [0, 0, 0],
          velocity: [0, 0, 0],
          direction: [0, 0, 0],
          up: [0, 0, 0],
        },
        sources: [],
        interval: setInterval(
          () => AL.scheduleContextAudio(ctx),
          AL.QUEUE_INTERVAL,
        ),
        gain: gain,
        distanceModel: 53250,
        speedOfSound: 343.3,
        dopplerFactor: 1,
        sourceDistanceModel: false,
        hrtf: hrtf || false,
        _err: 0,
        get err() {
          return this._err;
        },
        set err(val) {
          if (this._err === 0 || val === 0) {
            this._err = val;
          }
        },
      };
      AL.deviceRefCounts[deviceId]++;
      AL.contexts[ctx.id] = ctx;
      if (hrtf !== null) {
        for (var ctxId in AL.contexts) {
          var c = AL.contexts[ctxId];
          if (c.deviceId === deviceId) {
            c.hrtf = hrtf;
            AL.updateContextGlobal(c);
          }
        }
      }
      return ctx.id;
    }
    function _alcDestroyContext(contextId) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(33, 1, contextId);
      var ctx = AL.contexts[contextId];
      if (AL.currentCtx === ctx) {
        AL.alcErr = 40962;
        return;
      }
      if (AL.contexts[contextId].interval) {
        clearInterval(AL.contexts[contextId].interval);
      }
      AL.deviceRefCounts[ctx.deviceId]--;
      delete AL.contexts[contextId];
      AL.freeIds.push(contextId);
    }
    function _alcMakeContextCurrent(contextId) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(34, 1, contextId);
      if (contextId === 0) {
        AL.currentCtx = null;
      } else {
        AL.currentCtx = AL.contexts[contextId];
      }
      return 1;
    }
    function _alcOpenDevice(pDeviceName) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(35, 1, pDeviceName);
      if (pDeviceName) {
        var name = UTF8ToString(pDeviceName);
        if (name !== AL.DEVICE_NAME) {
          return 0;
        }
      }
      if (
        typeof AudioContext != "undefined" ||
        typeof webkitAudioContext != "undefined"
      ) {
        var deviceId = AL.newId();
        AL.deviceRefCounts[deviceId] = 0;
        return deviceId;
      }
      return 0;
    }
    var readEmAsmArgsArray = [];
    var readEmAsmArgs = (sigPtr, buf) => {
      readEmAsmArgsArray.length = 0;
      var ch;
      while ((ch = GROWABLE_HEAP_U8()[sigPtr++])) {
        var wide = ch != 105;
        wide &= ch != 112;
        buf += wide && buf % 8 ? 4 : 0;
        readEmAsmArgsArray.push(
          ch == 112
            ? GROWABLE_HEAP_U32()[buf >> 2]
            : ch == 106
              ? HEAP64[buf >> 3]
              : ch == 105
                ? GROWABLE_HEAP_I32()[buf >> 2]
                : GROWABLE_HEAP_F64()[buf >> 3],
        );
        buf += wide ? 8 : 4;
      }
      return readEmAsmArgsArray;
    };
    var runMainThreadEmAsm = (code, sigPtr, argbuf, sync) => {
      var args = readEmAsmArgs(sigPtr, argbuf);
      if (ENVIRONMENT_IS_PTHREAD) {
        return proxyToMainThread.apply(null, [-1 - code, sync].concat(args));
      }
      return ASM_CONSTS[code].apply(null, args);
    };
    var _emscripten_asm_const_int_sync_on_main_thread = (
      code,
      sigPtr,
      argbuf,
    ) => runMainThreadEmAsm(code, sigPtr, argbuf, 1);
    var _emscripten_check_blocking_allowed = () => {};
    var _emscripten_date_now = () => Date.now();
    var _emscripten_err = (str) => err(UTF8ToString(str));
    var _emscripten_exit_with_live_runtime = () => {
      runtimeKeepalivePush();
      throw "unwind";
    };
    var getHeapMax = () => 2147483648;
    var _emscripten_get_heap_max = () => getHeapMax();
    function _glActiveTexture(x0) {
      GLctx.activeTexture(x0);
    }
    var _emscripten_glActiveTexture = _glActiveTexture;
    var _glAttachShader = (program, shader) => {
      GLctx.attachShader(GL.programs[program], GL.shaders[shader]);
    };
    var _emscripten_glAttachShader = _glAttachShader;
    var _glBindAttribLocation = (program, index, name) => {
      GLctx.bindAttribLocation(GL.programs[program], index, UTF8ToString(name));
    };
    var _emscripten_glBindAttribLocation = _glBindAttribLocation;
    var _glBindBuffer = (target, buffer) => {
      if (target == 35051) {
        GLctx.currentPixelPackBufferBinding = buffer;
      } else if (target == 35052) {
        GLctx.currentPixelUnpackBufferBinding = buffer;
      }
      GLctx.bindBuffer(target, GL.buffers[buffer]);
    };
    var _emscripten_glBindBuffer = _glBindBuffer;
    var _glBindBufferBase = (target, index, buffer) => {
      GLctx.bindBufferBase(target, index, GL.buffers[buffer]);
    };
    var _emscripten_glBindBufferBase = _glBindBufferBase;
    var _glBindFramebuffer = (target, framebuffer) => {
      GLctx.bindFramebuffer(
        target,
        framebuffer
          ? GL.framebuffers[framebuffer]
          : GL.currentContext.defaultFbo,
      );
    };
    var _emscripten_glBindFramebuffer = _glBindFramebuffer;
    var _glBindRenderbuffer = (target, renderbuffer) => {
      GLctx.bindRenderbuffer(target, GL.renderbuffers[renderbuffer]);
    };
    var _emscripten_glBindRenderbuffer = _glBindRenderbuffer;
    var _glBindTexture = (target, texture) => {
      GLctx.bindTexture(target, GL.textures[texture]);
    };
    var _emscripten_glBindTexture = _glBindTexture;
    var _glBindVertexArray = (vao) => {
      GLctx.bindVertexArray(GL.vaos[vao]);
    };
    var _emscripten_glBindVertexArray = _glBindVertexArray;
    function _glBlendColor(x0, x1, x2, x3) {
      GLctx.blendColor(x0, x1, x2, x3);
    }
    var _emscripten_glBlendColor = _glBlendColor;
    function _glBlendEquationSeparate(x0, x1) {
      GLctx.blendEquationSeparate(x0, x1);
    }
    var _emscripten_glBlendEquationSeparate = _glBlendEquationSeparate;
    function _glBlendFuncSeparate(x0, x1, x2, x3) {
      GLctx.blendFuncSeparate(x0, x1, x2, x3);
    }
    var _emscripten_glBlendFuncSeparate = _glBlendFuncSeparate;
    function _glBlitFramebuffer(x0, x1, x2, x3, x4, x5, x6, x7, x8, x9) {
      GLctx.blitFramebuffer(x0, x1, x2, x3, x4, x5, x6, x7, x8, x9);
    }
    var _emscripten_glBlitFramebuffer = _glBlitFramebuffer;
    var _glBufferData = (target, size, data, usage) => {
      if (GL.currentContext.version >= 2) {
        if (data && size) {
          GLctx.bufferData(target, GROWABLE_HEAP_U8(), usage, data, size);
        } else {
          GLctx.bufferData(target, size, usage);
        }
      } else {
        GLctx.bufferData(
          target,
          data ? GROWABLE_HEAP_U8().subarray(data, data + size) : size,
          usage,
        );
      }
    };
    var _emscripten_glBufferData = _glBufferData;
    function _glClear(x0) {
      GLctx.clear(x0);
    }
    var _emscripten_glClear = _glClear;
    function _glClearColor(x0, x1, x2, x3) {
      GLctx.clearColor(x0, x1, x2, x3);
    }
    var _emscripten_glClearColor = _glClearColor;
    function _glClearDepthf(x0) {
      GLctx.clearDepth(x0);
    }
    var _emscripten_glClearDepthf = _glClearDepthf;
    var _glColorMask = (red, green, blue, alpha) => {
      GLctx.colorMask(!!red, !!green, !!blue, !!alpha);
    };
    var _emscripten_glColorMask = _glColorMask;
    var _glCompileShader = (shader) => {
      GLctx.compileShader(GL.shaders[shader]);
    };
    var _emscripten_glCompileShader = _glCompileShader;
    var _glCreateProgram = () => {
      var id = GL.getNewId(GL.programs);
      var program = GLctx.createProgram();
      program.name = id;
      program.maxUniformLength =
        program.maxAttributeLength =
        program.maxUniformBlockNameLength =
          0;
      program.uniformIdCounter = 1;
      GL.programs[id] = program;
      return id;
    };
    var _emscripten_glCreateProgram = _glCreateProgram;
    var _glCreateShader = (shaderType) => {
      var id = GL.getNewId(GL.shaders);
      GL.shaders[id] = GLctx.createShader(shaderType);
      return id;
    };
    var _emscripten_glCreateShader = _glCreateShader;
    var _glDeleteBuffers = (n, buffers) => {
      for (var i = 0; i < n; i++) {
        var id = GROWABLE_HEAP_I32()[(buffers + i * 4) >> 2];
        var buffer = GL.buffers[id];
        if (!buffer) continue;
        GLctx.deleteBuffer(buffer);
        buffer.name = 0;
        GL.buffers[id] = null;
        if (id == GLctx.currentPixelPackBufferBinding)
          GLctx.currentPixelPackBufferBinding = 0;
        if (id == GLctx.currentPixelUnpackBufferBinding)
          GLctx.currentPixelUnpackBufferBinding = 0;
      }
    };
    var _emscripten_glDeleteBuffers = _glDeleteBuffers;
    var _glDeleteFramebuffers = (n, framebuffers) => {
      for (var i = 0; i < n; ++i) {
        var id = GROWABLE_HEAP_I32()[(framebuffers + i * 4) >> 2];
        var framebuffer = GL.framebuffers[id];
        if (!framebuffer) continue;
        GLctx.deleteFramebuffer(framebuffer);
        framebuffer.name = 0;
        GL.framebuffers[id] = null;
      }
    };
    var _emscripten_glDeleteFramebuffers = _glDeleteFramebuffers;
    var _glDeleteProgram = (id) => {
      if (!id) return;
      var program = GL.programs[id];
      if (!program) {
        GL.recordError(1281);
        return;
      }
      GLctx.deleteProgram(program);
      program.name = 0;
      GL.programs[id] = null;
    };
    var _emscripten_glDeleteProgram = _glDeleteProgram;
    var _glDeleteRenderbuffers = (n, renderbuffers) => {
      for (var i = 0; i < n; i++) {
        var id = GROWABLE_HEAP_I32()[(renderbuffers + i * 4) >> 2];
        var renderbuffer = GL.renderbuffers[id];
        if (!renderbuffer) continue;
        GLctx.deleteRenderbuffer(renderbuffer);
        renderbuffer.name = 0;
        GL.renderbuffers[id] = null;
      }
    };
    var _emscripten_glDeleteRenderbuffers = _glDeleteRenderbuffers;
    var _glDeleteShader = (id) => {
      if (!id) return;
      var shader = GL.shaders[id];
      if (!shader) {
        GL.recordError(1281);
        return;
      }
      GLctx.deleteShader(shader);
      GL.shaders[id] = null;
    };
    var _emscripten_glDeleteShader = _glDeleteShader;
    var _glDeleteTextures = (n, textures) => {
      for (var i = 0; i < n; i++) {
        var id = GROWABLE_HEAP_I32()[(textures + i * 4) >> 2];
        var texture = GL.textures[id];
        if (!texture) continue;
        GLctx.deleteTexture(texture);
        texture.name = 0;
        GL.textures[id] = null;
      }
    };
    var _emscripten_glDeleteTextures = _glDeleteTextures;
    var _glDeleteVertexArrays = (n, vaos) => {
      for (var i = 0; i < n; i++) {
        var id = GROWABLE_HEAP_I32()[(vaos + i * 4) >> 2];
        GLctx.deleteVertexArray(GL.vaos[id]);
        GL.vaos[id] = null;
      }
    };
    var _emscripten_glDeleteVertexArrays = _glDeleteVertexArrays;
    function _glDepthFunc(x0) {
      GLctx.depthFunc(x0);
    }
    var _emscripten_glDepthFunc = _glDepthFunc;
    var _glDepthMask = (flag) => {
      GLctx.depthMask(!!flag);
    };
    var _emscripten_glDepthMask = _glDepthMask;
    function _glDisable(x0) {
      GLctx.disable(x0);
    }
    var _emscripten_glDisable = _glDisable;
    var _glDrawArrays = (mode, first, count) => {
      GLctx.drawArrays(mode, first, count);
    };
    var _emscripten_glDrawArrays = _glDrawArrays;
    var tempFixedLengthArray = [];
    var _glDrawBuffers = (n, bufs) => {
      var bufArray = tempFixedLengthArray[n];
      for (var i = 0; i < n; i++) {
        bufArray[i] = GROWABLE_HEAP_I32()[(bufs + i * 4) >> 2];
      }
      GLctx.drawBuffers(bufArray);
    };
    var _emscripten_glDrawBuffers = _glDrawBuffers;
    function _glEnable(x0) {
      GLctx.enable(x0);
    }
    var _emscripten_glEnable = _glEnable;
    var _glEnableVertexAttribArray = (index) => {
      GLctx.enableVertexAttribArray(index);
    };
    var _emscripten_glEnableVertexAttribArray = _glEnableVertexAttribArray;
    var _glFramebufferRenderbuffer = (
      target,
      attachment,
      renderbuffertarget,
      renderbuffer,
    ) => {
      GLctx.framebufferRenderbuffer(
        target,
        attachment,
        renderbuffertarget,
        GL.renderbuffers[renderbuffer],
      );
    };
    var _emscripten_glFramebufferRenderbuffer = _glFramebufferRenderbuffer;
    var _glFramebufferTexture2D = (
      target,
      attachment,
      textarget,
      texture,
      level,
    ) => {
      GLctx.framebufferTexture2D(
        target,
        attachment,
        textarget,
        GL.textures[texture],
        level,
      );
    };
    var _emscripten_glFramebufferTexture2D = _glFramebufferTexture2D;
    var __glGenObject = (n, buffers, createFunction, objectTable) => {
      for (var i = 0; i < n; i++) {
        var buffer = GLctx[createFunction]();
        var id = buffer && GL.getNewId(objectTable);
        if (buffer) {
          buffer.name = id;
          objectTable[id] = buffer;
        } else {
          GL.recordError(1282);
        }
        GROWABLE_HEAP_I32()[(buffers + i * 4) >> 2] = id;
      }
    };
    var _glGenBuffers = (n, buffers) => {
      __glGenObject(n, buffers, "createBuffer", GL.buffers);
    };
    var _emscripten_glGenBuffers = _glGenBuffers;
    var _glGenFramebuffers = (n, ids) => {
      __glGenObject(n, ids, "createFramebuffer", GL.framebuffers);
    };
    var _emscripten_glGenFramebuffers = _glGenFramebuffers;
    var _glGenRenderbuffers = (n, renderbuffers) => {
      __glGenObject(n, renderbuffers, "createRenderbuffer", GL.renderbuffers);
    };
    var _emscripten_glGenRenderbuffers = _glGenRenderbuffers;
    var _glGenTextures = (n, textures) => {
      __glGenObject(n, textures, "createTexture", GL.textures);
    };
    var _emscripten_glGenTextures = _glGenTextures;
    function _glGenVertexArrays(n, arrays) {
      __glGenObject(n, arrays, "createVertexArray", GL.vaos);
    }
    var _emscripten_glGenVertexArrays = _glGenVertexArrays;
    var writeI53ToI64 = (ptr, num) => {
      GROWABLE_HEAP_U32()[ptr >> 2] = num;
      var lower = GROWABLE_HEAP_U32()[ptr >> 2];
      GROWABLE_HEAP_U32()[(ptr + 4) >> 2] = (num - lower) / 4294967296;
    };
    var emscriptenWebGLGet = (name_, p, type) => {
      if (!p) {
        GL.recordError(1281);
        return;
      }
      var ret = undefined;
      switch (name_) {
        case 36346:
          ret = 1;
          break;
        case 36344:
          if (type != 0 && type != 1) {
            GL.recordError(1280);
          }
          return;
        case 34814:
        case 36345:
          ret = 0;
          break;
        case 34466:
          var formats = GLctx.getParameter(34467);
          ret = formats ? formats.length : 0;
          break;
        case 33309:
          if (GL.currentContext.version < 2) {
            GL.recordError(1282);
            return;
          }
          var exts = GLctx.getSupportedExtensions() || [];
          ret = 2 * exts.length;
          break;
        case 33307:
        case 33308:
          if (GL.currentContext.version < 2) {
            GL.recordError(1280);
            return;
          }
          ret = name_ == 33307 ? 3 : 0;
          break;
      }
      if (ret === undefined) {
        var result = GLctx.getParameter(name_);
        switch (typeof result) {
          case "number":
            ret = result;
            break;
          case "boolean":
            ret = result ? 1 : 0;
            break;
          case "string":
            GL.recordError(1280);
            return;
          case "object":
            if (result === null) {
              switch (name_) {
                case 34964:
                case 35725:
                case 34965:
                case 36006:
                case 36007:
                case 32873:
                case 34229:
                case 36662:
                case 36663:
                case 35053:
                case 35055:
                case 36010:
                case 35097:
                case 35869:
                case 32874:
                case 36389:
                case 35983:
                case 35368:
                case 34068: {
                  ret = 0;
                  break;
                }
                default: {
                  GL.recordError(1280);
                  return;
                }
              }
            } else if (
              result instanceof Float32Array ||
              result instanceof Uint32Array ||
              result instanceof Int32Array ||
              result instanceof Array
            ) {
              for (var i = 0; i < result.length; ++i) {
                switch (type) {
                  case 0:
                    GROWABLE_HEAP_I32()[(p + i * 4) >> 2] = result[i];
                    break;
                  case 2:
                    GROWABLE_HEAP_F32()[(p + i * 4) >> 2] = result[i];
                    break;
                  case 4:
                    GROWABLE_HEAP_I8()[(p + i) >> 0] = result[i] ? 1 : 0;
                    break;
                }
              }
              return;
            } else {
              try {
                ret = result.name | 0;
              } catch (e) {
                GL.recordError(1280);
                err(
                  `GL_INVALID_ENUM in glGet${type}v: Unknown object returned from WebGL getParameter(${name_})! (error: ${e})`,
                );
                return;
              }
            }
            break;
          default:
            GL.recordError(1280);
            err(
              `GL_INVALID_ENUM in glGet${type}v: Native code calling glGet${type}v(${name_}) and it returns ${result} of type ${typeof result}!`,
            );
            return;
        }
      }
      switch (type) {
        case 1:
          writeI53ToI64(p, ret);
          break;
        case 0:
          GROWABLE_HEAP_I32()[p >> 2] = ret;
          break;
        case 2:
          GROWABLE_HEAP_F32()[p >> 2] = ret;
          break;
        case 4:
          GROWABLE_HEAP_I8()[p >> 0] = ret ? 1 : 0;
          break;
      }
    };
    var _glGetIntegerv = (name_, p) => emscriptenWebGLGet(name_, p, 0);
    var _emscripten_glGetIntegerv = _glGetIntegerv;
    var _glGetProgramInfoLog = (program, maxLength, length, infoLog) => {
      var log = GLctx.getProgramInfoLog(GL.programs[program]);
      if (log === null) log = "(unknown error)";
      var numBytesWrittenExclNull =
        maxLength > 0 && infoLog ? stringToUTF8(log, infoLog, maxLength) : 0;
      if (length) GROWABLE_HEAP_I32()[length >> 2] = numBytesWrittenExclNull;
    };
    var _emscripten_glGetProgramInfoLog = _glGetProgramInfoLog;
    var _glGetProgramiv = (program, pname, p) => {
      if (!p) {
        GL.recordError(1281);
        return;
      }
      if (program >= GL.counter) {
        GL.recordError(1281);
        return;
      }
      program = GL.programs[program];
      if (pname == 35716) {
        var log = GLctx.getProgramInfoLog(program);
        if (log === null) log = "(unknown error)";
        GROWABLE_HEAP_I32()[p >> 2] = log.length + 1;
      } else if (pname == 35719) {
        if (!program.maxUniformLength) {
          for (var i = 0; i < GLctx.getProgramParameter(program, 35718); ++i) {
            program.maxUniformLength = Math.max(
              program.maxUniformLength,
              GLctx.getActiveUniform(program, i).name.length + 1,
            );
          }
        }
        GROWABLE_HEAP_I32()[p >> 2] = program.maxUniformLength;
      } else if (pname == 35722) {
        if (!program.maxAttributeLength) {
          for (var i = 0; i < GLctx.getProgramParameter(program, 35721); ++i) {
            program.maxAttributeLength = Math.max(
              program.maxAttributeLength,
              GLctx.getActiveAttrib(program, i).name.length + 1,
            );
          }
        }
        GROWABLE_HEAP_I32()[p >> 2] = program.maxAttributeLength;
      } else if (pname == 35381) {
        if (!program.maxUniformBlockNameLength) {
          for (var i = 0; i < GLctx.getProgramParameter(program, 35382); ++i) {
            program.maxUniformBlockNameLength = Math.max(
              program.maxUniformBlockNameLength,
              GLctx.getActiveUniformBlockName(program, i).length + 1,
            );
          }
        }
        GROWABLE_HEAP_I32()[p >> 2] = program.maxUniformBlockNameLength;
      } else {
        GROWABLE_HEAP_I32()[p >> 2] = GLctx.getProgramParameter(program, pname);
      }
    };
    var _emscripten_glGetProgramiv = _glGetProgramiv;
    var _glGetShaderInfoLog = (shader, maxLength, length, infoLog) => {
      var log = GLctx.getShaderInfoLog(GL.shaders[shader]);
      if (log === null) log = "(unknown error)";
      var numBytesWrittenExclNull =
        maxLength > 0 && infoLog ? stringToUTF8(log, infoLog, maxLength) : 0;
      if (length) GROWABLE_HEAP_I32()[length >> 2] = numBytesWrittenExclNull;
    };
    var _emscripten_glGetShaderInfoLog = _glGetShaderInfoLog;
    var _glGetShaderiv = (shader, pname, p) => {
      if (!p) {
        GL.recordError(1281);
        return;
      }
      if (pname == 35716) {
        var log = GLctx.getShaderInfoLog(GL.shaders[shader]);
        if (log === null) log = "(unknown error)";
        var logLength = log ? log.length + 1 : 0;
        GROWABLE_HEAP_I32()[p >> 2] = logLength;
      } else if (pname == 35720) {
        var source = GLctx.getShaderSource(GL.shaders[shader]);
        var sourceLength = source ? source.length + 1 : 0;
        GROWABLE_HEAP_I32()[p >> 2] = sourceLength;
      } else {
        GROWABLE_HEAP_I32()[p >> 2] = GLctx.getShaderParameter(
          GL.shaders[shader],
          pname,
        );
      }
    };
    var _emscripten_glGetShaderiv = _glGetShaderiv;
    var _glGetStringi = (name, index) => {
      if (GL.currentContext.version < 2) {
        GL.recordError(1282);
        return 0;
      }
      var stringiCache = GL.stringiCache[name];
      if (stringiCache) {
        if (index < 0 || index >= stringiCache.length) {
          GL.recordError(1281);
          return 0;
        }
        return stringiCache[index];
      }
      switch (name) {
        case 7939:
          var exts = GL.getExtensions().map((e) => stringToNewUTF8(e));
          stringiCache = GL.stringiCache[name] = exts;
          if (index < 0 || index >= stringiCache.length) {
            GL.recordError(1281);
            return 0;
          }
          return stringiCache[index];
        default:
          GL.recordError(1280);
          return 0;
      }
    };
    var _emscripten_glGetStringi = _glGetStringi;
    var _glGetUniformBlockIndex = (program, uniformBlockName) =>
      GLctx.getUniformBlockIndex(
        GL.programs[program],
        UTF8ToString(uniformBlockName),
      );
    var _emscripten_glGetUniformBlockIndex = _glGetUniformBlockIndex;
    var jstoi_q = (str) => parseInt(str);
    var webglGetLeftBracePos = (name) =>
      name.slice(-1) == "]" && name.lastIndexOf("[");
    var webglPrepareUniformLocationsBeforeFirstUse = (program) => {
      var uniformLocsById = program.uniformLocsById,
        uniformSizeAndIdsByName = program.uniformSizeAndIdsByName,
        i,
        j;
      if (!uniformLocsById) {
        program.uniformLocsById = uniformLocsById = {};
        program.uniformArrayNamesById = {};
        for (i = 0; i < GLctx.getProgramParameter(program, 35718); ++i) {
          var u = GLctx.getActiveUniform(program, i);
          var nm = u.name;
          var sz = u.size;
          var lb = webglGetLeftBracePos(nm);
          var arrayName = lb > 0 ? nm.slice(0, lb) : nm;
          var id = program.uniformIdCounter;
          program.uniformIdCounter += sz;
          uniformSizeAndIdsByName[arrayName] = [sz, id];
          for (j = 0; j < sz; ++j) {
            uniformLocsById[id] = j;
            program.uniformArrayNamesById[id++] = arrayName;
          }
        }
      }
    };
    var _glGetUniformLocation = (program, name) => {
      name = UTF8ToString(name);
      if ((program = GL.programs[program])) {
        webglPrepareUniformLocationsBeforeFirstUse(program);
        var uniformLocsById = program.uniformLocsById;
        var arrayIndex = 0;
        var uniformBaseName = name;
        var leftBrace = webglGetLeftBracePos(name);
        if (leftBrace > 0) {
          arrayIndex = jstoi_q(name.slice(leftBrace + 1)) >>> 0;
          uniformBaseName = name.slice(0, leftBrace);
        }
        var sizeAndId = program.uniformSizeAndIdsByName[uniformBaseName];
        if (sizeAndId && arrayIndex < sizeAndId[0]) {
          arrayIndex += sizeAndId[1];
          if (
            (uniformLocsById[arrayIndex] =
              uniformLocsById[arrayIndex] ||
              GLctx.getUniformLocation(program, name))
          ) {
            return arrayIndex;
          }
        }
      } else {
        GL.recordError(1281);
      }
      return -1;
    };
    var _emscripten_glGetUniformLocation = _glGetUniformLocation;
    var _glLinkProgram = (program) => {
      program = GL.programs[program];
      GLctx.linkProgram(program);
      program.uniformLocsById = 0;
      program.uniformSizeAndIdsByName = {};
    };
    var _emscripten_glLinkProgram = _glLinkProgram;
    var computeUnpackAlignedImageSize = (
      width,
      height,
      sizePerPixel,
      alignment,
    ) => {
      function roundedToNextMultipleOf(x, y) {
        return (x + y - 1) & -y;
      }
      var plainRowSize = width * sizePerPixel;
      var alignedRowSize = roundedToNextMultipleOf(plainRowSize, alignment);
      return height * alignedRowSize;
    };
    var colorChannelsInGlTextureFormat = (format) => {
      var colorChannels = {
        5: 3,
        6: 4,
        8: 2,
        29502: 3,
        29504: 4,
        26917: 2,
        26918: 2,
        29846: 3,
        29847: 4,
      };
      return colorChannels[format - 6402] || 1;
    };
    var heapObjectForWebGLType = (type) => {
      type -= 5120;
      if (type == 0) return GROWABLE_HEAP_I8();
      if (type == 1) return GROWABLE_HEAP_U8();
      if (type == 2) return GROWABLE_HEAP_I16();
      if (type == 4) return GROWABLE_HEAP_I32();
      if (type == 6) return GROWABLE_HEAP_F32();
      if (
        type == 5 ||
        type == 28922 ||
        type == 28520 ||
        type == 30779 ||
        type == 30782
      )
        return GROWABLE_HEAP_U32();
      return GROWABLE_HEAP_U16();
    };
    var heapAccessShiftForWebGLHeap = (heap) =>
      31 - Math.clz32(heap.BYTES_PER_ELEMENT);
    var emscriptenWebGLGetTexPixelData = (
      type,
      format,
      width,
      height,
      pixels,
      internalFormat,
    ) => {
      var heap = heapObjectForWebGLType(type);
      var shift = heapAccessShiftForWebGLHeap(heap);
      var byteSize = 1 << shift;
      var sizePerPixel = colorChannelsInGlTextureFormat(format) * byteSize;
      var bytes = computeUnpackAlignedImageSize(
        width,
        height,
        sizePerPixel,
        GL.unpackAlignment,
      );
      return heap.subarray(pixels >> shift, (pixels + bytes) >> shift);
    };
    var _glReadPixels = (x, y, width, height, format, type, pixels) => {
      if (GL.currentContext.version >= 2) {
        if (GLctx.currentPixelPackBufferBinding) {
          GLctx.readPixels(x, y, width, height, format, type, pixels);
        } else {
          var heap = heapObjectForWebGLType(type);
          GLctx.readPixels(
            x,
            y,
            width,
            height,
            format,
            type,
            heap,
            pixels >> heapAccessShiftForWebGLHeap(heap),
          );
        }
        return;
      }
      var pixelData = emscriptenWebGLGetTexPixelData(
        type,
        format,
        width,
        height,
        pixels,
        format,
      );
      if (!pixelData) {
        GL.recordError(1280);
        return;
      }
      GLctx.readPixels(x, y, width, height, format, type, pixelData);
    };
    var _emscripten_glReadPixels = _glReadPixels;
    function _glRenderbufferStorage(x0, x1, x2, x3) {
      GLctx.renderbufferStorage(x0, x1, x2, x3);
    }
    var _emscripten_glRenderbufferStorage = _glRenderbufferStorage;
    function _glRenderbufferStorageMultisample(x0, x1, x2, x3, x4) {
      GLctx.renderbufferStorageMultisample(x0, x1, x2, x3, x4);
    }
    var _emscripten_glRenderbufferStorageMultisample =
      _glRenderbufferStorageMultisample;
    function _glScissor(x0, x1, x2, x3) {
      GLctx.scissor(x0, x1, x2, x3);
    }
    var _emscripten_glScissor = _glScissor;
    var _glShaderSource = (shader, count, string, length) => {
      var source = GL.getSource(shader, count, string, length);
      GLctx.shaderSource(GL.shaders[shader], source);
    };
    var _emscripten_glShaderSource = _glShaderSource;
    var _glTexImage2D = (
      target,
      level,
      internalFormat,
      width,
      height,
      border,
      format,
      type,
      pixels,
    ) => {
      if (GL.currentContext.version >= 2) {
        if (GLctx.currentPixelUnpackBufferBinding) {
          GLctx.texImage2D(
            target,
            level,
            internalFormat,
            width,
            height,
            border,
            format,
            type,
            pixels,
          );
        } else if (pixels) {
          var heap = heapObjectForWebGLType(type);
          GLctx.texImage2D(
            target,
            level,
            internalFormat,
            width,
            height,
            border,
            format,
            type,
            heap,
            pixels >> heapAccessShiftForWebGLHeap(heap),
          );
        } else {
          GLctx.texImage2D(
            target,
            level,
            internalFormat,
            width,
            height,
            border,
            format,
            type,
            null,
          );
        }
        return;
      }
      GLctx.texImage2D(
        target,
        level,
        internalFormat,
        width,
        height,
        border,
        format,
        type,
        pixels
          ? emscriptenWebGLGetTexPixelData(
              type,
              format,
              width,
              height,
              pixels,
              internalFormat,
            )
          : null,
      );
    };
    var _emscripten_glTexImage2D = _glTexImage2D;
    function _glTexParameteri(x0, x1, x2) {
      GLctx.texParameteri(x0, x1, x2);
    }
    var _emscripten_glTexParameteri = _glTexParameteri;
    function _glTexStorage2D(x0, x1, x2, x3, x4) {
      GLctx.texStorage2D(x0, x1, x2, x3, x4);
    }
    var _emscripten_glTexStorage2D = _glTexStorage2D;
    var _glTexSubImage2D = (
      target,
      level,
      xoffset,
      yoffset,
      width,
      height,
      format,
      type,
      pixels,
    ) => {
      if (GL.currentContext.version >= 2) {
        if (GLctx.currentPixelUnpackBufferBinding) {
          GLctx.texSubImage2D(
            target,
            level,
            xoffset,
            yoffset,
            width,
            height,
            format,
            type,
            pixels,
          );
        } else if (pixels) {
          var heap = heapObjectForWebGLType(type);
          GLctx.texSubImage2D(
            target,
            level,
            xoffset,
            yoffset,
            width,
            height,
            format,
            type,
            heap,
            pixels >> heapAccessShiftForWebGLHeap(heap),
          );
        } else {
          GLctx.texSubImage2D(
            target,
            level,
            xoffset,
            yoffset,
            width,
            height,
            format,
            type,
            null,
          );
        }
        return;
      }
      var pixelData = null;
      if (pixels)
        pixelData = emscriptenWebGLGetTexPixelData(
          type,
          format,
          width,
          height,
          pixels,
          0,
        );
      GLctx.texSubImage2D(
        target,
        level,
        xoffset,
        yoffset,
        width,
        height,
        format,
        type,
        pixelData,
      );
    };
    var _emscripten_glTexSubImage2D = _glTexSubImage2D;
    var webglGetUniformLocation = (location) => {
      var p = GLctx.currentProgram;
      if (p) {
        var webglLoc = p.uniformLocsById[location];
        if (typeof webglLoc == "number") {
          p.uniformLocsById[location] = webglLoc = GLctx.getUniformLocation(
            p,
            p.uniformArrayNamesById[location] +
              (webglLoc > 0 ? `[${webglLoc}]` : ""),
          );
        }
        return webglLoc;
      } else {
        GL.recordError(1282);
      }
    };
    var _glUniform1i = (location, v0) => {
      GLctx.uniform1i(webglGetUniformLocation(location), v0);
    };
    var _emscripten_glUniform1i = _glUniform1i;
    var _glUniform2f = (location, v0, v1) => {
      GLctx.uniform2f(webglGetUniformLocation(location), v0, v1);
    };
    var _emscripten_glUniform2f = _glUniform2f;
    var _glUniformBlockBinding = (
      program,
      uniformBlockIndex,
      uniformBlockBinding,
    ) => {
      program = GL.programs[program];
      GLctx.uniformBlockBinding(
        program,
        uniformBlockIndex,
        uniformBlockBinding,
      );
    };
    var _emscripten_glUniformBlockBinding = _glUniformBlockBinding;
    var _glUseProgram = (program) => {
      program = GL.programs[program];
      GLctx.useProgram(program);
      GLctx.currentProgram = program;
    };
    var _emscripten_glUseProgram = _glUseProgram;
    var _glVertexAttribIPointer = (index, size, type, stride, ptr) => {
      GLctx.vertexAttribIPointer(index, size, type, stride, ptr);
    };
    var _emscripten_glVertexAttribIPointer = _glVertexAttribIPointer;
    var _glVertexAttribPointer = (
      index,
      size,
      type,
      normalized,
      stride,
      ptr,
    ) => {
      GLctx.vertexAttribPointer(index, size, type, !!normalized, stride, ptr);
    };
    var _emscripten_glVertexAttribPointer = _glVertexAttribPointer;
    function _glViewport(x0, x1, x2, x3) {
      GLctx.viewport(x0, x1, x2, x3);
    }
    var _emscripten_glViewport = _glViewport;
    var _emscripten_num_logical_cores = () => navigator["hardwareConcurrency"];
    var growMemory = (size) => {
      var b = wasmMemory.buffer;
      var pages = (size - b.byteLength + 65535) / 65536;
      try {
        wasmMemory.grow(pages);
        updateMemoryViews();
        return 1;
      } catch (e) {}
    };
    var _emscripten_resize_heap = (requestedSize) => {
      var oldSize = GROWABLE_HEAP_U8().length;
      requestedSize >>>= 0;
      if (requestedSize <= oldSize) {
        return false;
      }
      var maxHeapSize = getHeapMax();
      if (requestedSize > maxHeapSize) {
        return false;
      }
      var alignUp = (x, multiple) =>
        x + ((multiple - (x % multiple)) % multiple);
      for (var cutDown = 1; cutDown <= 4; cutDown *= 2) {
        var overGrownHeapSize = oldSize * (1 + 0.2 / cutDown);
        overGrownHeapSize = Math.min(
          overGrownHeapSize,
          requestedSize + 100663296,
        );
        var newSize = Math.min(
          maxHeapSize,
          alignUp(Math.max(requestedSize, overGrownHeapSize), 65536),
        );
        var replacement = growMemory(newSize);
        if (replacement) {
          return true;
        }
      }
      return false;
    };
    var JSEvents = {
      inEventHandler: 0,
      removeAllEventListeners() {
        for (var i = JSEvents.eventHandlers.length - 1; i >= 0; --i) {
          JSEvents._removeHandler(i);
        }
        JSEvents.eventHandlers = [];
        JSEvents.deferredCalls = [];
      },
      registerRemoveEventListeners() {
        if (!JSEvents.removeEventListenersRegistered) {
          __ATEXIT__.push(JSEvents.removeAllEventListeners);
          JSEvents.removeEventListenersRegistered = true;
        }
      },
      deferredCalls: [],
      deferCall(targetFunction, precedence, argsList) {
        function arraysHaveEqualContent(arrA, arrB) {
          if (arrA.length != arrB.length) return false;
          for (var i in arrA) {
            if (arrA[i] != arrB[i]) return false;
          }
          return true;
        }
        for (var i in JSEvents.deferredCalls) {
          var call = JSEvents.deferredCalls[i];
          if (
            call.targetFunction == targetFunction &&
            arraysHaveEqualContent(call.argsList, argsList)
          ) {
            return;
          }
        }
        JSEvents.deferredCalls.push({
          targetFunction: targetFunction,
          precedence: precedence,
          argsList: argsList,
        });
        JSEvents.deferredCalls.sort((x, y) => x.precedence < y.precedence);
      },
      removeDeferredCalls(targetFunction) {
        for (var i = 0; i < JSEvents.deferredCalls.length; ++i) {
          if (JSEvents.deferredCalls[i].targetFunction == targetFunction) {
            JSEvents.deferredCalls.splice(i, 1);
            --i;
          }
        }
      },
      canPerformEventHandlerRequests() {
        if (navigator.userActivation) {
          return navigator.userActivation.isActive;
        }
        return (
          JSEvents.inEventHandler &&
          JSEvents.currentEventHandler.allowsDeferredCalls
        );
      },
      runDeferredCalls() {
        if (!JSEvents.canPerformEventHandlerRequests()) {
          return;
        }
        for (var i = 0; i < JSEvents.deferredCalls.length; ++i) {
          var call = JSEvents.deferredCalls[i];
          JSEvents.deferredCalls.splice(i, 1);
          --i;
          call.targetFunction.apply(null, call.argsList);
        }
      },
      eventHandlers: [],
      removeAllHandlersOnTarget: (target, eventTypeString) => {
        for (var i = 0; i < JSEvents.eventHandlers.length; ++i) {
          if (
            JSEvents.eventHandlers[i].target == target &&
            (!eventTypeString ||
              eventTypeString == JSEvents.eventHandlers[i].eventTypeString)
          ) {
            JSEvents._removeHandler(i--);
          }
        }
      },
      _removeHandler(i) {
        var h = JSEvents.eventHandlers[i];
        h.target.removeEventListener(
          h.eventTypeString,
          h.eventListenerFunc,
          h.useCapture,
        );
        JSEvents.eventHandlers.splice(i, 1);
      },
      registerOrRemoveHandler(eventHandler) {
        if (!eventHandler.target) {
          return -4;
        }
        var jsEventHandler = function jsEventHandler(event) {
          ++JSEvents.inEventHandler;
          JSEvents.currentEventHandler = eventHandler;
          JSEvents.runDeferredCalls();
          eventHandler.handlerFunc(event);
          JSEvents.runDeferredCalls();
          --JSEvents.inEventHandler;
        };
        if (eventHandler.callbackfunc) {
          eventHandler.eventListenerFunc = jsEventHandler;
          eventHandler.target.addEventListener(
            eventHandler.eventTypeString,
            jsEventHandler,
            eventHandler.useCapture,
          );
          JSEvents.eventHandlers.push(eventHandler);
          JSEvents.registerRemoveEventListeners();
        } else {
          for (var i = 0; i < JSEvents.eventHandlers.length; ++i) {
            if (
              JSEvents.eventHandlers[i].target == eventHandler.target &&
              JSEvents.eventHandlers[i].eventTypeString ==
                eventHandler.eventTypeString
            ) {
              JSEvents._removeHandler(i--);
            }
          }
        }
        return 0;
      },
      getTargetThreadForEventCallback(targetThread) {
        switch (targetThread) {
          case 1:
            return 0;
          case 2:
            return PThread.currentProxiedOperationCallerThread;
          default:
            return targetThread;
        }
      },
      getNodeNameForTarget(target) {
        if (!target) return "";
        if (target == window) return "#window";
        if (target == screen) return "#screen";
        return target?.nodeName || "";
      },
      fullscreenEnabled() {
        return document.fullscreenEnabled || document.webkitFullscreenEnabled;
      },
    };
    var maybeCStringToJsString = (cString) =>
      cString > 2 ? UTF8ToString(cString) : cString;
    var specialHTMLTargets = [
      0,
      typeof document != "undefined" ? document : 0,
      typeof window != "undefined" ? window : 0,
    ];
    var findEventTarget = (target) => {
      target = maybeCStringToJsString(target);
      var domElement =
        specialHTMLTargets[target] ||
        (typeof document != "undefined"
          ? document.querySelector(target)
          : undefined);
      return domElement;
    };
    var registerKeyEventCallback = (
      target,
      userData,
      useCapture,
      callbackfunc,
      eventTypeId,
      eventTypeString,
      targetThread,
    ) => {
      targetThread = JSEvents.getTargetThreadForEventCallback(targetThread);
      if (!JSEvents.keyEvent) JSEvents.keyEvent = _malloc(176);
      var keyEventHandlerFunc = (e) => {
        var keyEventData = targetThread ? _malloc(176) : JSEvents.keyEvent;
        GROWABLE_HEAP_F64()[keyEventData >> 3] = e.timeStamp;
        var idx = keyEventData >> 2;
        GROWABLE_HEAP_I32()[idx + 2] = e.location;
        GROWABLE_HEAP_I32()[idx + 3] = e.ctrlKey;
        GROWABLE_HEAP_I32()[idx + 4] = e.shiftKey;
        GROWABLE_HEAP_I32()[idx + 5] = e.altKey;
        GROWABLE_HEAP_I32()[idx + 6] = e.metaKey;
        GROWABLE_HEAP_I32()[idx + 7] = e.repeat;
        GROWABLE_HEAP_I32()[idx + 8] = e.charCode;
        GROWABLE_HEAP_I32()[idx + 9] = e.keyCode;
        GROWABLE_HEAP_I32()[idx + 10] = e.which;
        stringToUTF8(e.key || "", keyEventData + 44, 32);
        stringToUTF8(e.code || "", keyEventData + 76, 32);
        stringToUTF8(e.char || "", keyEventData + 108, 32);
        stringToUTF8(e.locale || "", keyEventData + 140, 32);
        if (targetThread)
          __emscripten_run_callback_on_thread(
            targetThread,
            callbackfunc,
            eventTypeId,
            keyEventData,
            userData,
          );
        else if (
          getWasmTableEntry(callbackfunc)(eventTypeId, keyEventData, userData)
        )
          e.preventDefault();
      };
      var eventHandler = {
        target: findEventTarget(target),
        eventTypeString: eventTypeString,
        callbackfunc: callbackfunc,
        handlerFunc: keyEventHandlerFunc,
        useCapture: useCapture,
      };
      return JSEvents.registerOrRemoveHandler(eventHandler);
    };
    function _emscripten_set_keydown_callback_on_thread(
      target,
      userData,
      useCapture,
      callbackfunc,
      targetThread,
    ) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(
          36,
          1,
          target,
          userData,
          useCapture,
          callbackfunc,
          targetThread,
        );
      return registerKeyEventCallback(
        target,
        userData,
        useCapture,
        callbackfunc,
        2,
        "keydown",
        targetThread,
      );
    }
    function _emscripten_set_keyup_callback_on_thread(
      target,
      userData,
      useCapture,
      callbackfunc,
      targetThread,
    ) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(
          37,
          1,
          target,
          userData,
          useCapture,
          callbackfunc,
          targetThread,
        );
      return registerKeyEventCallback(
        target,
        userData,
        useCapture,
        callbackfunc,
        3,
        "keyup",
        targetThread,
      );
    }
    var _emscripten_supports_offscreencanvas = () => 0;
    var _emscripten_webgl_do_commit_frame = () => {
      if (!GL.currentContext || !GL.currentContext.GLctx) {
        return -3;
      }
      if (GL.currentContext.defaultFbo) {
        GL.blitOffscreenFramebuffer(GL.currentContext);
        return 0;
      }
      if (!GL.currentContext.attributes.explicitSwapControl) {
        return -3;
      }
      return 0;
    };
    function _emscripten_webgl_create_context_proxied(target, attributes) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(38, 1, target, attributes);
      return _emscripten_webgl_do_create_context(target, attributes);
    }
    var emscripten_webgl_power_preferences = [
      "default",
      "low-power",
      "high-performance",
    ];
    var findCanvasEventTarget = (target) => findEventTarget(target);
    var _emscripten_webgl_do_create_context = (target, attributes) => {
      var a = attributes >> 2;
      var powerPreference = GROWABLE_HEAP_I32()[a + (24 >> 2)];
      var contextAttributes = {
        alpha: !!GROWABLE_HEAP_I32()[a + (0 >> 2)],
        depth: !!GROWABLE_HEAP_I32()[a + (4 >> 2)],
        stencil: !!GROWABLE_HEAP_I32()[a + (8 >> 2)],
        antialias: !!GROWABLE_HEAP_I32()[a + (12 >> 2)],
        premultipliedAlpha: !!GROWABLE_HEAP_I32()[a + (16 >> 2)],
        preserveDrawingBuffer: !!GROWABLE_HEAP_I32()[a + (20 >> 2)],
        powerPreference: emscripten_webgl_power_preferences[powerPreference],
        failIfMajorPerformanceCaveat: !!GROWABLE_HEAP_I32()[a + (28 >> 2)],
        majorVersion: GROWABLE_HEAP_I32()[a + (32 >> 2)],
        minorVersion: GROWABLE_HEAP_I32()[a + (36 >> 2)],
        enableExtensionsByDefault: GROWABLE_HEAP_I32()[a + (40 >> 2)],
        explicitSwapControl: GROWABLE_HEAP_I32()[a + (44 >> 2)],
        proxyContextToMainThread: GROWABLE_HEAP_I32()[a + (48 >> 2)],
        renderViaOffscreenBackBuffer: GROWABLE_HEAP_I32()[a + (52 >> 2)],
      };
      var canvas = findCanvasEventTarget(target);
      if (ENVIRONMENT_IS_PTHREAD) {
        if (
          contextAttributes.proxyContextToMainThread === 2 ||
          (!canvas && contextAttributes.proxyContextToMainThread === 1)
        ) {
          if (typeof OffscreenCanvas == "undefined") {
            GROWABLE_HEAP_I32()[(attributes + 52) >> 2] = 1;
            GROWABLE_HEAP_I32()[(attributes + 20) >> 2] = 1;
          }
          return _emscripten_webgl_create_context_proxied(target, attributes);
        }
      }
      if (!canvas) {
        return 0;
      }
      if (
        contextAttributes.explicitSwapControl &&
        !contextAttributes.renderViaOffscreenBackBuffer
      ) {
        contextAttributes.renderViaOffscreenBackBuffer = true;
      }
      var contextHandle = GL.createContext(canvas, contextAttributes);
      return contextHandle;
    };
    var _emscripten_webgl_init_context_attributes = (attributes) => {
      var a = attributes >> 2;
      for (var i = 0; i < 56 >> 2; ++i) {
        GROWABLE_HEAP_I32()[a + i] = 0;
      }
      GROWABLE_HEAP_I32()[a + (0 >> 2)] =
        GROWABLE_HEAP_I32()[a + (4 >> 2)] =
        GROWABLE_HEAP_I32()[a + (12 >> 2)] =
        GROWABLE_HEAP_I32()[a + (16 >> 2)] =
        GROWABLE_HEAP_I32()[a + (32 >> 2)] =
        GROWABLE_HEAP_I32()[a + (40 >> 2)] =
          1;
      if (ENVIRONMENT_IS_WORKER)
        GROWABLE_HEAP_I32()[(attributes + 48) >> 2] = 1;
    };
    var _emscripten_webgl_make_context_current_calling_thread = (
      contextHandle,
    ) => {
      var success = GL.makeContextCurrent(contextHandle);
      if (success) GL.currentContextIsProxied = false;
      return success ? 0 : -5;
    };
    var ENV = {};
    var getExecutableName = () => thisProgram || "./this.program";
    var getEnvStrings = () => {
      if (!getEnvStrings.strings) {
        var lang =
          (
            (typeof navigator == "object" &&
              navigator.languages &&
              navigator.languages[0]) ||
            "C"
          ).replace("-", "_") + ".UTF-8";
        var env = {
          USER: "web_user",
          LOGNAME: "web_user",
          PATH: "/",
          PWD: "/",
          HOME: "/home/web_user",
          LANG: lang,
          _: getExecutableName(),
        };
        for (var x in ENV) {
          if (ENV[x] === undefined) delete env[x];
          else env[x] = ENV[x];
        }
        var strings = [];
        for (var x in env) {
          strings.push(`${x}=${env[x]}`);
        }
        getEnvStrings.strings = strings;
      }
      return getEnvStrings.strings;
    };
    var stringToAscii = (str, buffer) => {
      for (var i = 0; i < str.length; ++i) {
        GROWABLE_HEAP_I8()[buffer++ >> 0] = str.charCodeAt(i);
      }
      GROWABLE_HEAP_I8()[buffer >> 0] = 0;
    };
    var _environ_get = function (__environ, environ_buf) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(39, 1, __environ, environ_buf);
      var bufSize = 0;
      getEnvStrings().forEach((string, i) => {
        var ptr = environ_buf + bufSize;
        GROWABLE_HEAP_U32()[(__environ + i * 4) >> 2] = ptr;
        stringToAscii(string, ptr);
        bufSize += string.length + 1;
      });
      return 0;
    };
    var _environ_sizes_get = function (penviron_count, penviron_buf_size) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(40, 1, penviron_count, penviron_buf_size);
      var strings = getEnvStrings();
      GROWABLE_HEAP_U32()[penviron_count >> 2] = strings.length;
      var bufSize = 0;
      strings.forEach((string) => (bufSize += string.length + 1));
      GROWABLE_HEAP_U32()[penviron_buf_size >> 2] = bufSize;
      return 0;
    };
    function _fd_close(fd) {
      if (ENVIRONMENT_IS_PTHREAD) return proxyToMainThread(41, 1, fd);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        FS.close(stream);
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return e.errno;
      }
    }
    var doReadv = (stream, iov, iovcnt, offset) => {
      var ret = 0;
      for (var i = 0; i < iovcnt; i++) {
        var ptr = GROWABLE_HEAP_U32()[iov >> 2];
        var len = GROWABLE_HEAP_U32()[(iov + 4) >> 2];
        iov += 8;
        var curr = FS.read(stream, GROWABLE_HEAP_I8(), ptr, len, offset);
        if (curr < 0) return -1;
        ret += curr;
        if (curr < len) break;
        if (typeof offset !== "undefined") {
          offset += curr;
        }
      }
      return ret;
    };
    function _fd_read(fd, iov, iovcnt, pnum) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(42, 1, fd, iov, iovcnt, pnum);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        var num = doReadv(stream, iov, iovcnt);
        GROWABLE_HEAP_U32()[pnum >> 2] = num;
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return e.errno;
      }
    }
    function _fd_seek(fd, offset, whence, newOffset) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(43, 1, fd, offset, whence, newOffset);
      offset = bigintToI53Checked(offset);
      try {
        if (isNaN(offset)) return 61;
        var stream = SYSCALLS.getStreamFromFD(fd);
        FS.llseek(stream, offset, whence);
        HEAP64[newOffset >> 3] = BigInt(stream.position);
        if (stream.getdents && offset === 0 && whence === 0)
          stream.getdents = null;
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return e.errno;
      }
    }
    var doWritev = (stream, iov, iovcnt, offset) => {
      var ret = 0;
      for (var i = 0; i < iovcnt; i++) {
        var ptr = GROWABLE_HEAP_U32()[iov >> 2];
        var len = GROWABLE_HEAP_U32()[(iov + 4) >> 2];
        iov += 8;
        var curr = FS.write(stream, GROWABLE_HEAP_I8(), ptr, len, offset);
        if (curr < 0) return -1;
        ret += curr;
        if (typeof offset !== "undefined") {
          offset += curr;
        }
      }
      return ret;
    };
    function _fd_write(fd, iov, iovcnt, pnum) {
      if (ENVIRONMENT_IS_PTHREAD)
        return proxyToMainThread(44, 1, fd, iov, iovcnt, pnum);
      try {
        var stream = SYSCALLS.getStreamFromFD(fd);
        var num = doWritev(stream, iov, iovcnt);
        GROWABLE_HEAP_U32()[pnum >> 2] = num;
        return 0;
      } catch (e) {
        if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
        return e.errno;
      }
    }
    var _llvm_eh_typeid_for = (type) => type;
    var arraySum = (array, index) => {
      var sum = 0;
      for (var i = 0; i <= index; sum += array[i++]) {}
      return sum;
    };
    var MONTH_DAYS_LEAP = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var MONTH_DAYS_REGULAR = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var addDays = (date, days) => {
      var newDate = new Date(date.getTime());
      while (days > 0) {
        var leap = isLeapYear(newDate.getFullYear());
        var currentMonth = newDate.getMonth();
        var daysInCurrentMonth = (leap ? MONTH_DAYS_LEAP : MONTH_DAYS_REGULAR)[
          currentMonth
        ];
        if (days > daysInCurrentMonth - newDate.getDate()) {
          days -= daysInCurrentMonth - newDate.getDate() + 1;
          newDate.setDate(1);
          if (currentMonth < 11) {
            newDate.setMonth(currentMonth + 1);
          } else {
            newDate.setMonth(0);
            newDate.setFullYear(newDate.getFullYear() + 1);
          }
        } else {
          newDate.setDate(newDate.getDate() + days);
          return newDate;
        }
      }
      return newDate;
    };
    var writeArrayToMemory = (array, buffer) => {
      GROWABLE_HEAP_I8().set(array, buffer);
    };
    var _strftime = (s, maxsize, format, tm) => {
      var tm_zone = GROWABLE_HEAP_U32()[(tm + 40) >> 2];
      var date = {
        tm_sec: GROWABLE_HEAP_I32()[tm >> 2],
        tm_min: GROWABLE_HEAP_I32()[(tm + 4) >> 2],
        tm_hour: GROWABLE_HEAP_I32()[(tm + 8) >> 2],
        tm_mday: GROWABLE_HEAP_I32()[(tm + 12) >> 2],
        tm_mon: GROWABLE_HEAP_I32()[(tm + 16) >> 2],
        tm_year: GROWABLE_HEAP_I32()[(tm + 20) >> 2],
        tm_wday: GROWABLE_HEAP_I32()[(tm + 24) >> 2],
        tm_yday: GROWABLE_HEAP_I32()[(tm + 28) >> 2],
        tm_isdst: GROWABLE_HEAP_I32()[(tm + 32) >> 2],
        tm_gmtoff: GROWABLE_HEAP_I32()[(tm + 36) >> 2],
        tm_zone: tm_zone ? UTF8ToString(tm_zone) : "",
      };
      var pattern = UTF8ToString(format);
      var EXPANSION_RULES_1 = {
        "%c": "%a %b %d %H:%M:%S %Y",
        "%D": "%m/%d/%y",
        "%F": "%Y-%m-%d",
        "%h": "%b",
        "%r": "%I:%M:%S %p",
        "%R": "%H:%M",
        "%T": "%H:%M:%S",
        "%x": "%m/%d/%y",
        "%X": "%H:%M:%S",
        "%Ec": "%c",
        "%EC": "%C",
        "%Ex": "%m/%d/%y",
        "%EX": "%H:%M:%S",
        "%Ey": "%y",
        "%EY": "%Y",
        "%Od": "%d",
        "%Oe": "%e",
        "%OH": "%H",
        "%OI": "%I",
        "%Om": "%m",
        "%OM": "%M",
        "%OS": "%S",
        "%Ou": "%u",
        "%OU": "%U",
        "%OV": "%V",
        "%Ow": "%w",
        "%OW": "%W",
        "%Oy": "%y",
      };
      for (var rule in EXPANSION_RULES_1) {
        pattern = pattern.replace(
          new RegExp(rule, "g"),
          EXPANSION_RULES_1[rule],
        );
      }
      var WEEKDAYS = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
      ];
      var MONTHS = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ];
      function leadingSomething(value, digits, character) {
        var str = typeof value == "number" ? value.toString() : value || "";
        while (str.length < digits) {
          str = character[0] + str;
        }
        return str;
      }
      function leadingNulls(value, digits) {
        return leadingSomething(value, digits, "0");
      }
      function compareByDay(date1, date2) {
        function sgn(value) {
          return value < 0 ? -1 : value > 0 ? 1 : 0;
        }
        var compare;
        if ((compare = sgn(date1.getFullYear() - date2.getFullYear())) === 0) {
          if ((compare = sgn(date1.getMonth() - date2.getMonth())) === 0) {
            compare = sgn(date1.getDate() - date2.getDate());
          }
        }
        return compare;
      }
      function getFirstWeekStartDate(janFourth) {
        switch (janFourth.getDay()) {
          case 0:
            return new Date(janFourth.getFullYear() - 1, 11, 29);
          case 1:
            return janFourth;
          case 2:
            return new Date(janFourth.getFullYear(), 0, 3);
          case 3:
            return new Date(janFourth.getFullYear(), 0, 2);
          case 4:
            return new Date(janFourth.getFullYear(), 0, 1);
          case 5:
            return new Date(janFourth.getFullYear() - 1, 11, 31);
          case 6:
            return new Date(janFourth.getFullYear() - 1, 11, 30);
        }
      }
      function getWeekBasedYear(date) {
        var thisDate = addDays(
          new Date(date.tm_year + 1900, 0, 1),
          date.tm_yday,
        );
        var janFourthThisYear = new Date(thisDate.getFullYear(), 0, 4);
        var janFourthNextYear = new Date(thisDate.getFullYear() + 1, 0, 4);
        var firstWeekStartThisYear = getFirstWeekStartDate(janFourthThisYear);
        var firstWeekStartNextYear = getFirstWeekStartDate(janFourthNextYear);
        if (compareByDay(firstWeekStartThisYear, thisDate) <= 0) {
          if (compareByDay(firstWeekStartNextYear, thisDate) <= 0) {
            return thisDate.getFullYear() + 1;
          }
          return thisDate.getFullYear();
        }
        return thisDate.getFullYear() - 1;
      }
      var EXPANSION_RULES_2 = {
        "%a": (date) => WEEKDAYS[date.tm_wday].substring(0, 3),
        "%A": (date) => WEEKDAYS[date.tm_wday],
        "%b": (date) => MONTHS[date.tm_mon].substring(0, 3),
        "%B": (date) => MONTHS[date.tm_mon],
        "%C": (date) => {
          var year = date.tm_year + 1900;
          return leadingNulls((year / 100) | 0, 2);
        },
        "%d": (date) => leadingNulls(date.tm_mday, 2),
        "%e": (date) => leadingSomething(date.tm_mday, 2, " "),
        "%g": (date) => getWeekBasedYear(date).toString().substring(2),
        "%G": (date) => getWeekBasedYear(date),
        "%H": (date) => leadingNulls(date.tm_hour, 2),
        "%I": (date) => {
          var twelveHour = date.tm_hour;
          if (twelveHour == 0) twelveHour = 12;
          else if (twelveHour > 12) twelveHour -= 12;
          return leadingNulls(twelveHour, 2);
        },
        "%j": (date) =>
          leadingNulls(
            date.tm_mday +
              arraySum(
                isLeapYear(date.tm_year + 1900)
                  ? MONTH_DAYS_LEAP
                  : MONTH_DAYS_REGULAR,
                date.tm_mon - 1,
              ),
            3,
          ),
        "%m": (date) => leadingNulls(date.tm_mon + 1, 2),
        "%M": (date) => leadingNulls(date.tm_min, 2),
        "%n": () => "\n",
        "%p": (date) => {
          if (date.tm_hour >= 0 && date.tm_hour < 12) {
            return "AM";
          }
          return "PM";
        },
        "%S": (date) => leadingNulls(date.tm_sec, 2),
        "%t": () => "\t",
        "%u": (date) => date.tm_wday || 7,
        "%U": (date) => {
          var days = date.tm_yday + 7 - date.tm_wday;
          return leadingNulls(Math.floor(days / 7), 2);
        },
        "%V": (date) => {
          var val = Math.floor(
            (date.tm_yday + 7 - ((date.tm_wday + 6) % 7)) / 7,
          );
          if ((date.tm_wday + 371 - date.tm_yday - 2) % 7 <= 2) {
            val++;
          }
          if (!val) {
            val = 52;
            var dec31 = (date.tm_wday + 7 - date.tm_yday - 1) % 7;
            if (
              dec31 == 4 ||
              (dec31 == 5 && isLeapYear((date.tm_year % 400) - 1))
            ) {
              val++;
            }
          } else if (val == 53) {
            var jan1 = (date.tm_wday + 371 - date.tm_yday) % 7;
            if (jan1 != 4 && (jan1 != 3 || !isLeapYear(date.tm_year))) val = 1;
          }
          return leadingNulls(val, 2);
        },
        "%w": (date) => date.tm_wday,
        "%W": (date) => {
          var days = date.tm_yday + 7 - ((date.tm_wday + 6) % 7);
          return leadingNulls(Math.floor(days / 7), 2);
        },
        "%y": (date) => (date.tm_year + 1900).toString().substring(2),
        "%Y": (date) => date.tm_year + 1900,
        "%z": (date) => {
          var off = date.tm_gmtoff;
          var ahead = off >= 0;
          off = Math.abs(off) / 60;
          off = (off / 60) * 100 + (off % 60);
          return (ahead ? "+" : "-") + String("0000" + off).slice(-4);
        },
        "%Z": (date) => date.tm_zone,
        "%%": () => "%",
      };
      pattern = pattern.replace(/%%/g, "\0\0");
      for (var rule in EXPANSION_RULES_2) {
        if (pattern.includes(rule)) {
          pattern = pattern.replace(
            new RegExp(rule, "g"),
            EXPANSION_RULES_2[rule](date),
          );
        }
      }
      pattern = pattern.replace(/\0\0/g, "%");
      var bytes = intArrayFromString(pattern, false);
      if (bytes.length > maxsize) {
        return 0;
      }
      writeArrayToMemory(bytes, s);
      return bytes.length - 1;
    };
    var _strftime_l = (s, maxsize, format, tm, loc) =>
      _strftime(s, maxsize, format, tm);
    var stringToUTF8OnStack = (str) => {
      var size = lengthBytesUTF8(str) + 1;
      var ret = stackAlloc(size);
      stringToUTF8(str, ret, size);
      return ret;
    };
    var uleb128Encode = (n, target) => {
      if (n < 128) {
        target.push(n);
      } else {
        target.push(n % 128 | 128, n >> 7);
      }
    };
    var sigToWasmTypes = (sig) => {
      var typeNames = {
        i: "i32",
        j: "i64",
        f: "f32",
        d: "f64",
        e: "externref",
        p: "i32",
      };
      var type = {
        parameters: [],
        results: sig[0] == "v" ? [] : [typeNames[sig[0]]],
      };
      for (var i = 1; i < sig.length; ++i) {
        type.parameters.push(typeNames[sig[i]]);
      }
      return type;
    };
    var generateFuncType = (sig, target) => {
      var sigRet = sig.slice(0, 1);
      var sigParam = sig.slice(1);
      var typeCodes = { i: 127, p: 127, j: 126, f: 125, d: 124, e: 111 };
      target.push(96);
      uleb128Encode(sigParam.length, target);
      for (var i = 0; i < sigParam.length; ++i) {
        target.push(typeCodes[sigParam[i]]);
      }
      if (sigRet == "v") {
        target.push(0);
      } else {
        target.push(1, typeCodes[sigRet]);
      }
    };
    var convertJsFunctionToWasm = (func, sig) => {
      if (typeof WebAssembly.Function == "function") {
        return new WebAssembly.Function(sigToWasmTypes(sig), func);
      }
      var typeSectionBody = [1];
      generateFuncType(sig, typeSectionBody);
      var bytes = [0, 97, 115, 109, 1, 0, 0, 0, 1];
      uleb128Encode(typeSectionBody.length, bytes);
      bytes.push.apply(bytes, typeSectionBody);
      bytes.push(2, 7, 1, 1, 101, 1, 102, 0, 0, 7, 5, 1, 1, 102, 0, 0);
      var module = new WebAssembly.Module(new Uint8Array(bytes));
      var instance = new WebAssembly.Instance(module, { e: { f: func } });
      var wrappedFunc = instance.exports["f"];
      return wrappedFunc;
    };
    var updateTableMap = (offset, count) => {
      if (functionsInTableMap) {
        for (var i = offset; i < offset + count; i++) {
          var item = getWasmTableEntry(i);
          if (item) {
            functionsInTableMap.set(item, i);
          }
        }
      }
    };
    var functionsInTableMap;
    var getFunctionAddress = (func) => {
      if (!functionsInTableMap) {
        functionsInTableMap = new WeakMap();
        updateTableMap(0, wasmTable.length);
      }
      return functionsInTableMap.get(func) || 0;
    };
    var freeTableIndexes = [];
    var getEmptyTableSlot = () => {
      if (freeTableIndexes.length) {
        return freeTableIndexes.pop();
      }
      try {
        wasmTable.grow(1);
      } catch (err) {
        if (!(err instanceof RangeError)) {
          throw err;
        }
        throw "Unable to grow wasm table. Set ALLOW_TABLE_GROWTH.";
      }
      return wasmTable.length - 1;
    };
    var setWasmTableEntry = (idx, func) => {
      wasmTable.set(idx, func);
      wasmTableMirror[idx] = wasmTable.get(idx);
    };
    var addFunction = (func, sig) => {
      var rtn = getFunctionAddress(func);
      if (rtn) {
        return rtn;
      }
      var ret = getEmptyTableSlot();
      try {
        setWasmTableEntry(ret, func);
      } catch (err) {
        if (!(err instanceof TypeError)) {
          throw err;
        }
        var wrapped = convertJsFunctionToWasm(func, sig);
        setWasmTableEntry(ret, wrapped);
      }
      functionsInTableMap.set(func, ret);
      return ret;
    };
    var removeFunction = (index) => {
      functionsInTableMap.delete(getWasmTableEntry(index));
      setWasmTableEntry(index, null);
      freeTableIndexes.push(index);
    };
    var getCFunc = (ident) => {
      var func = Module["_" + ident];
      return func;
    };
    var ccall = (ident, returnType, argTypes, args, opts) => {
      var toC = {
        string: (str) => {
          var ret = 0;
          if (str !== null && str !== undefined && str !== 0) {
            ret = stringToUTF8OnStack(str);
          }
          return ret;
        },
        array: (arr) => {
          var ret = stackAlloc(arr.length);
          writeArrayToMemory(arr, ret);
          return ret;
        },
      };
      function convertReturnValue(ret) {
        if (returnType === "string") {
          return UTF8ToString(ret);
        }
        if (returnType === "boolean") return Boolean(ret);
        return ret;
      }
      var func = getCFunc(ident);
      var cArgs = [];
      var stack = 0;
      if (args) {
        for (var i = 0; i < args.length; i++) {
          var converter = toC[argTypes[i]];
          if (converter) {
            if (stack === 0) stack = stackSave();
            cArgs[i] = converter(args[i]);
          } else {
            cArgs[i] = args[i];
          }
        }
      }
      var ret = func.apply(null, cArgs);
      function onDone(ret) {
        if (stack !== 0) stackRestore(stack);
        return convertReturnValue(ret);
      }
      ret = onDone(ret);
      return ret;
    };
    PThread.init();
    var FSNode = function (parent, name, mode, rdev) {
      if (!parent) {
        parent = this;
      }
      this.parent = parent;
      this.mount = parent.mount;
      this.mounted = null;
      this.id = FS.nextInode++;
      this.name = name;
      this.mode = mode;
      this.node_ops = {};
      this.stream_ops = {};
      this.rdev = rdev;
    };
    var readMode = 292 | 73;
    var writeMode = 146;
    Object.defineProperties(FSNode.prototype, {
      read: {
        get: function () {
          return (this.mode & readMode) === readMode;
        },
        set: function (val) {
          val ? (this.mode |= readMode) : (this.mode &= ~readMode);
        },
      },
      write: {
        get: function () {
          return (this.mode & writeMode) === writeMode;
        },
        set: function (val) {
          val ? (this.mode |= writeMode) : (this.mode &= ~writeMode);
        },
      },
      isFolder: {
        get: function () {
          return FS.isDir(this.mode);
        },
      },
      isDevice: {
        get: function () {
          return FS.isChrdev(this.mode);
        },
      },
    });
    FS.FSNode = FSNode;
    FS.createPreloadedFile = FS_createPreloadedFile;
    FS.staticInit();
    Module["FS_createPath"] = FS.createPath;
    Module["FS_createDataFile"] = FS.createDataFile;
    Module["FS_createPreloadedFile"] = FS.createPreloadedFile;
    Module["FS_unlink"] = FS.unlink;
    Module["FS_createLazyFile"] = FS.createLazyFile;
    Module["FS_createDevice"] = FS.createDevice;
    embind_init_charCodes();
    BindingError = Module["BindingError"] = class BindingError extends Error {
      constructor(message) {
        super(message);
        this.name = "BindingError";
      }
    };
    InternalError = Module["InternalError"] = class InternalError extends (
      Error
    ) {
      constructor(message) {
        super(message);
        this.name = "InternalError";
      }
    };
    handleAllocatorInit();
    init_emval();
    UnboundTypeError = Module["UnboundTypeError"] = extendError(
      Error,
      "UnboundTypeError",
    );
    var GLctx;
    Module["requestFullscreen"] = Browser.requestFullscreen;
    Module["requestAnimationFrame"] = Browser.requestAnimationFrame;
    Module["setCanvasSize"] = Browser.setCanvasSize;
    Module["pauseMainLoop"] = Browser.mainLoop.pause;
    Module["resumeMainLoop"] = Browser.mainLoop.resume;
    Module["getUserMedia"] = Browser.getUserMedia;
    Module["createContext"] = Browser.createContext;
    var preloadedImages = {};
    var preloadedAudios = {};
    for (var i = 0; i < 32; ++i) tempFixedLengthArray.push(new Array(i));
    var proxiedFunctionTable = [
      _proc_exit,
      exitOnMainThread,
      pthreadCreateProxied,
      ___syscall_fcntl64,
      ___syscall_fstat64,
      ___syscall_fstatfs64,
      ___syscall_statfs64,
      ___syscall_getcwd,
      ___syscall_getdents64,
      ___syscall_ioctl,
      ___syscall_lstat64,
      ___syscall_mkdirat,
      ___syscall_newfstatat,
      ___syscall_openat,
      ___syscall_readlinkat,
      ___syscall_renameat,
      ___syscall_rmdir,
      ___syscall_stat64,
      ___syscall_unlinkat,
      _alBufferData,
      _alDeleteBuffers,
      _alDeleteSources,
      _alSourcei,
      _alGenBuffers,
      _alGenSources,
      _alGetError,
      _alGetSourcei,
      _alSourcePlay,
      _alSourceQueueBuffers,
      _alSourceStop,
      _alSourceUnqueueBuffers,
      _alcCloseDevice,
      _alcCreateContext,
      _alcDestroyContext,
      _alcMakeContextCurrent,
      _alcOpenDevice,
      _emscripten_set_keydown_callback_on_thread,
      _emscripten_set_keyup_callback_on_thread,
      _emscripten_webgl_create_context_proxied,
      _environ_get,
      _environ_sizes_get,
      _fd_close,
      _fd_read,
      _fd_seek,
      _fd_write,
    ];
    var wasmImports = {
      Tb: RegisterExternFunction,
      Qb: WasmCreateFunction,
      Sb: WasmCreateModule,
      la: WasmDeleteFunction,
      gc: ___assert_fail,
      p: ___cxa_begin_catch,
      qc: ___cxa_current_primary_exception,
      s: ___cxa_end_catch,
      b: ___cxa_find_matching_catch_2,
      i: ___cxa_find_matching_catch_3,
      G: ___cxa_find_matching_catch_4,
      cc: ___cxa_find_matching_catch_5,
      ma: ___cxa_rethrow,
      pc: ___cxa_rethrow_primary_exception,
      m: ___cxa_throw,
      rc: ___cxa_uncaught_exceptions,
      Fc: ___emscripten_init_main_thread_js,
      sa: ___emscripten_thread_cleanup,
      zc: ___pthread_create_js,
      d: ___resumeException,
      ya: ___syscall_fcntl64,
      yc: ___syscall_fstatfs64,
      nc: ___syscall_getcwd,
      sc: ___syscall_getdents64,
      Lc: ___syscall_ioctl,
      kc: ___syscall_mkdirat,
      ua: ___syscall_openat,
      mc: ___syscall_readlinkat,
      hc: ___syscall_renameat,
      ic: ___syscall_rmdir,
      lc: ___syscall_stat64,
      jc: ___syscall_unlinkat,
      ha: __embind_register_bigint,
      Db: __embind_register_bool,
      Cb: __embind_register_emval,
      ga: __embind_register_float,
      O: __embind_register_function,
      D: __embind_register_integer,
      v: __embind_register_memory_view,
      fa: __embind_register_std_string,
      P: __embind_register_std_wstring,
      Eb: __embind_register_void,
      Kc: __emscripten_get_now_is_monotonic,
      vc: __emscripten_notify_mailbox_postmessage,
      zb: __emscripten_proxied_gl_context_activated_from_main_browser_thread,
      Ac: __emscripten_receive_on_main_thread_js,
      Ec: __emscripten_thread_mailbox_await,
      Jc: __emscripten_thread_set_strongref,
      Rb: __emval_decref,
      Pb: __emval_incref,
      Bc: __gmtime_js,
      Cc: __localtime_js,
      uc: __tzset_js,
      Q: _abort,
      Wb: _alBufferData,
      Zb: _alDeleteBuffers,
      Ib: _alDeleteSources,
      _b: _alGenBuffers,
      Kb: _alGenSources,
      Jb: _alGetError,
      ia: _alGetSourcei,
      Hb: _alSourcePlay,
      Vb: _alSourceQueueBuffers,
      Fb: _alSourceStop,
      Xb: _alSourceUnqueueBuffers,
      Yb: _alSourcei,
      Lb: _alcCloseDevice,
      Ob: _alcCreateContext,
      Nb: _alcDestroyContext,
      ja: _alcMakeContextCurrent,
      Mb: _alcOpenDevice,
      I: _emscripten_asm_const_int_sync_on_main_thread,
      ta: _emscripten_check_blocking_allowed,
      va: _emscripten_date_now,
      Bb: _emscripten_err,
      Ic: _emscripten_exit_with_live_runtime,
      wc: _emscripten_get_heap_max,
      B: _emscripten_get_now,
      ca: _emscripten_glActiveTexture,
      ba: _emscripten_glAttachShader,
      aa: _emscripten_glBindAttribLocation,
      $: _emscripten_glBindBuffer,
      Ea: _emscripten_glBindBufferBase,
      _: _emscripten_glBindFramebuffer,
      Z: _emscripten_glBindRenderbuffer,
      Y: _emscripten_glBindTexture,
      Ha: _emscripten_glBindVertexArray,
      X: _emscripten_glBlendColor,
      W: _emscripten_glBlendEquationSeparate,
      V: _emscripten_glBlendFuncSeparate,
      Ja: _emscripten_glBlitFramebuffer,
      U: _emscripten_glBufferData,
      T: _emscripten_glClear,
      S: _emscripten_glClearColor,
      R: _emscripten_glClearDepthf,
      xb: _emscripten_glColorMask,
      wb: _emscripten_glCompileShader,
      vb: _emscripten_glCreateProgram,
      ub: _emscripten_glCreateShader,
      tb: _emscripten_glDeleteBuffers,
      sb: _emscripten_glDeleteFramebuffers,
      rb: _emscripten_glDeleteProgram,
      qb: _emscripten_glDeleteRenderbuffers,
      pb: _emscripten_glDeleteShader,
      ob: _emscripten_glDeleteTextures,
      Ga: _emscripten_glDeleteVertexArrays,
      nb: _emscripten_glDepthFunc,
      mb: _emscripten_glDepthMask,
      lb: _emscripten_glDisable,
      kb: _emscripten_glDrawArrays,
      Ka: _emscripten_glDrawBuffers,
      jb: _emscripten_glEnable,
      ib: _emscripten_glEnableVertexAttribArray,
      hb: _emscripten_glFramebufferRenderbuffer,
      gb: _emscripten_glFramebufferTexture2D,
      fb: _emscripten_glGenBuffers,
      eb: _emscripten_glGenFramebuffers,
      db: _emscripten_glGenRenderbuffers,
      cb: _emscripten_glGenTextures,
      Fa: _emscripten_glGenVertexArrays,
      bb: _emscripten_glGetIntegerv,
      $a: _emscripten_glGetProgramInfoLog,
      ab: _emscripten_glGetProgramiv,
      Za: _emscripten_glGetShaderInfoLog,
      _a: _emscripten_glGetShaderiv,
      Ca: _emscripten_glGetStringi,
      Ba: _emscripten_glGetUniformBlockIndex,
      Ya: _emscripten_glGetUniformLocation,
      Xa: _emscripten_glLinkProgram,
      Wa: _emscripten_glReadPixels,
      Va: _emscripten_glRenderbufferStorage,
      Ia: _emscripten_glRenderbufferStorageMultisample,
      Ua: _emscripten_glScissor,
      Ta: _emscripten_glShaderSource,
      Sa: _emscripten_glTexImage2D,
      Ra: _emscripten_glTexParameteri,
      za: _emscripten_glTexStorage2D,
      Qa: _emscripten_glTexSubImage2D,
      Pa: _emscripten_glUniform1i,
      Oa: _emscripten_glUniform2f,
      Aa: _emscripten_glUniformBlockBinding,
      Na: _emscripten_glUseProgram,
      Da: _emscripten_glVertexAttribIPointer,
      Ma: _emscripten_glVertexAttribPointer,
      La: _emscripten_glViewport,
      xc: _emscripten_num_logical_cores,
      tc: _emscripten_resize_heap,
      Nc: _emscripten_set_keydown_callback_on_thread,
      Mc: _emscripten_set_keyup_callback_on_thread,
      Ab: _emscripten_supports_offscreencanvas,
      yb: _emscripten_webgl_do_commit_frame,
      ea: _emscripten_webgl_do_create_context,
      Gb: _emscripten_webgl_init_context_attributes,
      da: _emscripten_webgl_make_context_current_calling_thread,
      Gc: _environ_get,
      Hc: _environ_sizes_get,
      ka: _exit,
      N: _fd_close,
      xa: _fd_read,
      Dc: _fd_seek,
      wa: _fd_write,
      pa: invoke_diii,
      fc: invoke_fii,
      qa: invoke_fiii,
      q: invoke_i,
      f: invoke_ii,
      c: invoke_iii,
      ec: invoke_iiif,
      h: invoke_iiii,
      o: invoke_iiiii,
      x: invoke_iiiiii,
      u: invoke_iiiiiii,
      C: invoke_iiiiiiii,
      na: invoke_iiiiiiiii,
      L: invoke_iiiiiiiiiiii,
      J: invoke_iiij,
      dc: invoke_iiijj,
      ra: invoke_j,
      H: invoke_ji,
      z: invoke_jii,
      M: invoke_jiiii,
      w: invoke_jiij,
      k: invoke_v,
      $b: invoke_vf,
      bc: invoke_vffff,
      j: invoke_vi,
      ac: invoke_viff,
      e: invoke_vii,
      oa: invoke_viif,
      g: invoke_viii,
      l: invoke_viiii,
      n: invoke_viiiii,
      r: invoke_viiiiii,
      y: invoke_viiiiiii,
      E: invoke_viiiiiiiiii,
      K: invoke_viiiiiiiiiiiiiii,
      A: invoke_viij,
      F: invoke_viji,
      t: _llvm_eh_typeid_for,
      a: wasmMemory || Module["wasmMemory"],
      Ub: _strftime,
      oc: _strftime_l,
    };
    var wasmExports = createWasm();
    var ___wasm_call_ctors = () => (___wasm_call_ctors = wasmExports["Oc"])();
    var _main = (Module["_main"] = (a0, a1) =>
      (_main = Module["_main"] = wasmExports["Qc"])(a0, a1));
    var _initVm = (Module["_initVm"] = () =>
      (_initVm = Module["_initVm"] = wasmExports["Rc"])());
    var ___cxa_free_exception = (a0) =>
      (___cxa_free_exception = wasmExports["__cxa_free_exception"])(a0);
    var _EmptyBlockHandler = (Module["_EmptyBlockHandler"] = (a0) =>
      (_EmptyBlockHandler = Module["_EmptyBlockHandler"] = wasmExports["Sc"])(
        a0,
      ));
    var _MemoryUtils_GetByteProxy = (Module["_MemoryUtils_GetByteProxy"] = (
      a0,
      a1,
    ) =>
      (_MemoryUtils_GetByteProxy = Module["_MemoryUtils_GetByteProxy"] =
        wasmExports["Tc"])(a0, a1));
    var _MemoryUtils_GetHalfProxy = (Module["_MemoryUtils_GetHalfProxy"] = (
      a0,
      a1,
    ) =>
      (_MemoryUtils_GetHalfProxy = Module["_MemoryUtils_GetHalfProxy"] =
        wasmExports["Uc"])(a0, a1));
    var _MemoryUtils_GetWordProxy = (Module["_MemoryUtils_GetWordProxy"] = (
      a0,
      a1,
    ) =>
      (_MemoryUtils_GetWordProxy = Module["_MemoryUtils_GetWordProxy"] =
        wasmExports["Vc"])(a0, a1));
    var _MemoryUtils_GetDoubleProxy = (Module["_MemoryUtils_GetDoubleProxy"] = (
      a0,
      a1,
    ) =>
      (_MemoryUtils_GetDoubleProxy = Module["_MemoryUtils_GetDoubleProxy"] =
        wasmExports["Wc"])(a0, a1));
    var _MemoryUtils_SetByteProxy = (Module["_MemoryUtils_SetByteProxy"] = (
      a0,
      a1,
      a2,
    ) =>
      (_MemoryUtils_SetByteProxy = Module["_MemoryUtils_SetByteProxy"] =
        wasmExports["Xc"])(a0, a1, a2));
    var _MemoryUtils_SetHalfProxy = (Module["_MemoryUtils_SetHalfProxy"] = (
      a0,
      a1,
      a2,
    ) =>
      (_MemoryUtils_SetHalfProxy = Module["_MemoryUtils_SetHalfProxy"] =
        wasmExports["Yc"])(a0, a1, a2));
    var _MemoryUtils_SetWordProxy = (Module["_MemoryUtils_SetWordProxy"] = (
      a0,
      a1,
      a2,
    ) =>
      (_MemoryUtils_SetWordProxy = Module["_MemoryUtils_SetWordProxy"] =
        wasmExports["Zc"])(a0, a1, a2));
    var _MemoryUtils_SetDoubleProxy = (Module["_MemoryUtils_SetDoubleProxy"] = (
      a0,
      a1,
      a2,
    ) =>
      (_MemoryUtils_SetDoubleProxy = Module["_MemoryUtils_SetDoubleProxy"] =
        wasmExports["_c"])(a0, a1, a2));
    var _LWL_Proxy = (Module["_LWL_Proxy"] = (a0, a1, a2) =>
      (_LWL_Proxy = Module["_LWL_Proxy"] = wasmExports["$c"])(a0, a1, a2));
    var _LWR_Proxy = (Module["_LWR_Proxy"] = (a0, a1, a2) =>
      (_LWR_Proxy = Module["_LWR_Proxy"] = wasmExports["ad"])(a0, a1, a2));
    var _LDL_Proxy = (Module["_LDL_Proxy"] = (a0, a1, a2) =>
      (_LDL_Proxy = Module["_LDL_Proxy"] = wasmExports["bd"])(a0, a1, a2));
    var _LDR_Proxy = (Module["_LDR_Proxy"] = (a0, a1, a2) =>
      (_LDR_Proxy = Module["_LDR_Proxy"] = wasmExports["cd"])(a0, a1, a2));
    var _SWL_Proxy = (Module["_SWL_Proxy"] = (a0, a1, a2) =>
      (_SWL_Proxy = Module["_SWL_Proxy"] = wasmExports["dd"])(a0, a1, a2));
    var _SWR_Proxy = (Module["_SWR_Proxy"] = (a0, a1, a2) =>
      (_SWR_Proxy = Module["_SWR_Proxy"] = wasmExports["ed"])(a0, a1, a2));
    var _SDL_Proxy = (Module["_SDL_Proxy"] = (a0, a1, a2) =>
      (_SDL_Proxy = Module["_SDL_Proxy"] = wasmExports["fd"])(a0, a1, a2));
    var _SDR_Proxy = (Module["_SDR_Proxy"] = (a0, a1, a2) =>
      (_SDR_Proxy = Module["_SDR_Proxy"] = wasmExports["gd"])(a0, a1, a2));
    var _free = (a0) => (_free = wasmExports["hd"])(a0);
    var _malloc = (a0) => (_malloc = wasmExports["id"])(a0);
    var _pthread_self = (Module["_pthread_self"] = () =>
      (_pthread_self = Module["_pthread_self"] = wasmExports["jd"])());
    var __emscripten_tls_init = (Module["__emscripten_tls_init"] = () =>
      (__emscripten_tls_init = Module["__emscripten_tls_init"] =
        wasmExports["kd"])());
    var ___getTypeName = (a0) => (___getTypeName = wasmExports["ld"])(a0);
    var __embind_initialize_bindings = (Module["__embind_initialize_bindings"] =
      () =>
        (__embind_initialize_bindings = Module["__embind_initialize_bindings"] =
          wasmExports["md"])());
    var _emscripten_webgl_commit_frame = () =>
      (_emscripten_webgl_commit_frame =
        wasmExports["emscripten_webgl_commit_frame"])();
    var __emscripten_run_callback_on_thread = (a0, a1, a2, a3, a4) =>
      (__emscripten_run_callback_on_thread = wasmExports["nd"])(
        a0,
        a1,
        a2,
        a3,
        a4,
      );
    var ___errno_location = () => (___errno_location = wasmExports["od"])();
    var __emscripten_thread_init = (Module["__emscripten_thread_init"] = (
      a0,
      a1,
      a2,
      a3,
      a4,
      a5,
    ) =>
      (__emscripten_thread_init = Module["__emscripten_thread_init"] =
        wasmExports["pd"])(a0, a1, a2, a3, a4, a5));
    var __emscripten_thread_crashed = (Module["__emscripten_thread_crashed"] =
      () =>
        (__emscripten_thread_crashed = Module["__emscripten_thread_crashed"] =
          wasmExports["qd"])());
    var _emscripten_main_thread_process_queued_calls = () =>
      (_emscripten_main_thread_process_queued_calls =
        wasmExports["emscripten_main_thread_process_queued_calls"])();
    var _emscripten_main_runtime_thread_id = () =>
      (_emscripten_main_runtime_thread_id =
        wasmExports["emscripten_main_runtime_thread_id"])();
    var __emscripten_run_on_main_thread_js = (a0, a1, a2, a3) =>
      (__emscripten_run_on_main_thread_js = wasmExports["rd"])(a0, a1, a2, a3);
    var __emscripten_thread_free_data = (a0) =>
      (__emscripten_thread_free_data = wasmExports["sd"])(a0);
    var __emscripten_thread_exit = (Module["__emscripten_thread_exit"] = (a0) =>
      (__emscripten_thread_exit = Module["__emscripten_thread_exit"] =
        wasmExports["td"])(a0));
    var __emscripten_check_mailbox = () =>
      (__emscripten_check_mailbox = wasmExports["ud"])();
    var _setThrew = (a0, a1) => (_setThrew = wasmExports["vd"])(a0, a1);
    var setTempRet0 = (a0) => (setTempRet0 = wasmExports["wd"])(a0);
    var _emscripten_stack_set_limits = (a0, a1) =>
      (_emscripten_stack_set_limits = wasmExports["xd"])(a0, a1);
    var stackSave = () => (stackSave = wasmExports["yd"])();
    var stackRestore = (a0) => (stackRestore = wasmExports["zd"])(a0);
    var stackAlloc = (a0) => (stackAlloc = wasmExports["Ad"])(a0);
    var ___cxa_decrement_exception_refcount = (a0) =>
      (___cxa_decrement_exception_refcount = wasmExports["Bd"])(a0);
    var ___cxa_increment_exception_refcount = (a0) =>
      (___cxa_increment_exception_refcount = wasmExports["Cd"])(a0);
    var ___cxa_can_catch = (a0, a1, a2) =>
      (___cxa_can_catch = wasmExports["Dd"])(a0, a1, a2);
    var ___cxa_is_pointer_type = (a0) =>
      (___cxa_is_pointer_type = wasmExports["Ed"])(a0);
    var ___start_em_js = (Module["___start_em_js"] = 232134);
    var ___stop_em_js = (Module["___stop_em_js"] = 233371);
    function invoke_iii(index, a1, a2) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_v(index) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)();
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viii(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiii(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_ii(index, a1) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_vii(index, a1, a2) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_vi(index, a1) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_i(index) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)();
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiii(index, a1, a2, a3, a4) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiiiii(index, a1, a2, a3, a4, a5, a6) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiiiiiii(index, a1, a2, a3, a4, a5, a6, a7) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6, a7);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiiii(index, a1, a2, a3, a4) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_ji(index, a1) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
        return 0n;
      }
    }
    function invoke_iiij(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiiii(index, a1, a2, a3, a4, a5) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4, a5);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_jiij(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
        return 0n;
      }
    }
    function invoke_iiiiii(index, a1, a2, a3, a4, a5) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4, a5);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viij(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_jii(index, a1, a2) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
        return 0n;
      }
    }
    function invoke_viif(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_fii(index, a1, a2) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiif(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viji(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiiiiiiii(index, a1, a2, a3, a4, a5, a6, a7, a8) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6, a7, a8);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiiiiii(index, a1, a2, a3, a4, a5, a6) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiijj(index, a1, a2, a3, a4) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiiiiiiiii(
      index,
      a1,
      a2,
      a3,
      a4,
      a5,
      a6,
      a7,
      a8,
      a9,
      a10,
    ) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6, a7, a8, a9, a10);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_vffff(index, a1, a2, a3, a4) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viff(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_vf(index, a1) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiiiiii(index, a1, a2, a3, a4, a5, a6, a7) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(a1, a2, a3, a4, a5, a6, a7);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_j(index) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)();
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
        return 0n;
      }
    }
    function invoke_jiiii(index, a1, a2, a3, a4) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3, a4);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
        return 0n;
      }
    }
    function invoke_fiii(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_diii(index, a1, a2, a3) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(a1, a2, a3);
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_iiiiiiiiiiii(
      index,
      a1,
      a2,
      a3,
      a4,
      a5,
      a6,
      a7,
      a8,
      a9,
      a10,
      a11,
    ) {
      var sp = stackSave();
      try {
        return getWasmTableEntry(index)(
          a1,
          a2,
          a3,
          a4,
          a5,
          a6,
          a7,
          a8,
          a9,
          a10,
          a11,
        );
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    function invoke_viiiiiiiiiiiiiii(
      index,
      a1,
      a2,
      a3,
      a4,
      a5,
      a6,
      a7,
      a8,
      a9,
      a10,
      a11,
      a12,
      a13,
      a14,
      a15,
    ) {
      var sp = stackSave();
      try {
        getWasmTableEntry(index)(
          a1,
          a2,
          a3,
          a4,
          a5,
          a6,
          a7,
          a8,
          a9,
          a10,
          a11,
          a12,
          a13,
          a14,
          a15,
        );
      } catch (e) {
        stackRestore(sp);
        if (e !== e + 0) throw e;
        _setThrew(1, 0);
      }
    }
    Module["addRunDependency"] = addRunDependency;
    Module["removeRunDependency"] = removeRunDependency;
    Module["FS_createPath"] = FS.createPath;
    Module["FS_createLazyFile"] = FS.createLazyFile;
    Module["FS_createDevice"] = FS.createDevice;
    Module["wasmMemory"] = wasmMemory;
    Module["keepRuntimeAlive"] = keepRuntimeAlive;
    Module["ccall"] = ccall;
    Module["ExitStatus"] = ExitStatus;
    Module["FS_createPreloadedFile"] = FS.createPreloadedFile;
    Module["FS"] = FS;
    Module["FS_createDataFile"] = FS.createDataFile;
    Module["FS_unlink"] = FS.unlink;
    Module["PThread"] = PThread;
    var calledRun;
    dependenciesFulfilled = function runCaller() {
      if (!calledRun) run();
      if (!calledRun) dependenciesFulfilled = runCaller;
    };
    function callMain(args = []) {
      var entryFunction = _main;
      args.unshift(thisProgram);
      var argc = args.length;
      var argv = stackAlloc((argc + 1) * 4);
      var argv_ptr = argv;
      args.forEach((arg) => {
        GROWABLE_HEAP_U32()[argv_ptr >> 2] = stringToUTF8OnStack(arg);
        argv_ptr += 4;
      });
      GROWABLE_HEAP_U32()[argv_ptr >> 2] = 0;
      try {
        var ret = entryFunction(argc, argv);
        exitJS(ret, true);
        return ret;
      } catch (e) {
        return handleException(e);
      }
    }
    function run(args = arguments_) {
      if (runDependencies > 0) {
        return;
      }
      if (ENVIRONMENT_IS_PTHREAD) {
        readyPromiseResolve(Module);
        initRuntime();
        startWorker(Module);
        return;
      }
      preRun();
      if (runDependencies > 0) {
        return;
      }
      function doRun() {
        if (calledRun) return;
        calledRun = true;
        Module["calledRun"] = true;
        if (ABORT) return;
        initRuntime();
        preMain();
        readyPromiseResolve(Module);
        if (Module["onRuntimeInitialized"]) Module["onRuntimeInitialized"]();
        if (shouldRunNow) callMain(args);
        postRun();
      }
      if (Module["setStatus"]) {
        Module["setStatus"]("Running...");
        setTimeout(function () {
          setTimeout(function () {
            Module["setStatus"]("");
          }, 1);
          doRun();
        }, 1);
      } else {
        doRun();
      }
    }
    if (Module["preInit"]) {
      if (typeof Module["preInit"] == "function")
        Module["preInit"] = [Module["preInit"]];
      while (Module["preInit"].length > 0) {
        Module["preInit"].pop()();
      }
    }
    var shouldRunNow = true;
    if (Module["noInitialRun"]) shouldRunNow = false;
    run();

    return moduleArg.ready;
  };
})();
