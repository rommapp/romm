/* eslint-disable @typescript-eslint/no-explicit-any */
import { isEqual } from "lodash";

interface DBSnapshot {
  timestamp: Date;
  stores: {
    [storeName: string]: {
      [key: string]: any;
    };
  };
}

export interface Change {
  timestamp: Date;
  store: string;
  key: string;
  type: "added" | "modified" | "deleted";
  oldValue?: any;
  newValue?: any;
}

type EventType = "change" | "error";
type EventsListener = (changes: Change[]) => void;
type ErrorsListener = (error: Error) => void;

export interface DiffMonitor {
  start: () => void;
  stop: () => void;
  getChanges: () => Change[];
  clearChanges: () => void;
  forceCheck: () => Promise<void>;
  setInterval: (ms: number) => void;
  on: (event: EventType, listener: EventsListener | ErrorsListener) => void;
  off: (event: EventType, listener: EventsListener | ErrorsListener) => void;
}

export default async function createIndexedDBDiffMonitor({
  dbName,
  storeName,
  intervalMs = 1000,
}: {
  dbName: string;
  storeName?: string;
  intervalMs?: number;
}): Promise<DiffMonitor> {
  let lastSnapshot: DBSnapshot | null = null;
  let changes: Change[] = [];
  let intervalId: number | null = null;
  let isRunning = false;

  // Event handling
  const eventListeners: {
    change: EventsListener[];
    error: ErrorsListener[];
  } = {
    change: [],
    error: [],
  };

  // Helper to get all data from a store
  async function getAllFromStore(
    store: IDBObjectStore,
  ): Promise<{ [key: string]: any }> {
    return new Promise((resolve, reject) => {
      const data: { [key: string]: any } = {};
      const request = store.openCursor();

      request.onerror = () => reject(request.error);
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result;
        if (cursor) {
          data[cursor.key.toString()] = cursor.value;
          cursor.continue();
        } else {
          resolve(data);
        }
      };
    });
  }

  // Take a snapshot of the entire database
  async function takeSnapshot(): Promise<DBSnapshot> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(dbName);

      request.onerror = () => reject(request.error);
      request.onsuccess = async () => {
        const db = request.result;
        const snapshot: DBSnapshot = {
          timestamp: new Date(),
          stores: {},
        };

        try {
          for (const sn of Array.from(db.objectStoreNames)) {
            const tx = db.transaction(sn, "readonly");
            const store = tx.objectStore(sn);
            snapshot.stores[sn] = await getAllFromStore(store);
          }

          db.close();
          resolve(snapshot);
        } catch (error) {
          reject(error);
        }
      };
      request.onupgradeneeded = () => {
        if (!storeName) return;

        const db = request.result;
        if (!db.objectStoreNames.contains(storeName)) {
          db.createObjectStore(storeName);
        }
      };
    });
  }

  // Compare two snapshots and detect changes
  function compareSnapshots(
    oldSnapshot: DBSnapshot,
    newSnapshot: DBSnapshot,
  ): Change[] {
    const newChanges: Change[] = [];

    // Check all stores in new snapshot
    for (const [storeName, newStoreData] of Object.entries(
      newSnapshot.stores,
    )) {
      const oldStoreData = oldSnapshot.stores[storeName] || {};

      // Check for added or modified keys
      for (const [key, newValue] of Object.entries(newStoreData)) {
        const oldValue = oldStoreData[key];
        if (
          // The store is empty or the key is new
          oldValue === undefined ||
          // The save timestamp has changed
          (oldValue.timestamp &&
            oldValue.timestamp.getTime() !== newValue.timestamp.getTime()) ||
          // The state array length has changed
          (oldValue.length && oldValue.length !== newValue.length) ||
          // The state array content has changed
          (oldValue.length && !isEqual(oldValue, newValue))
        ) {
          newChanges.push({
            timestamp: newSnapshot.timestamp,
            store: storeName,
            key,
            type: "added",
            oldValue,
            newValue,
          });
        }
      }

      // Check for deleted keys
      for (const key of Object.keys(oldStoreData)) {
        if (!(key in newStoreData)) {
          newChanges.push({
            timestamp: newSnapshot.timestamp,
            store: storeName,
            key,
            type: "deleted",
            oldValue: oldStoreData[key],
          });
        }
      }
    }

    return newChanges;
  }

  // Check for changes
  async function checkForChanges(): Promise<void> {
    try {
      const newSnapshot = await takeSnapshot();

      if (lastSnapshot) {
        const newChanges = compareSnapshots(lastSnapshot, newSnapshot);
        if (newChanges.length > 0) {
          changes.push(...newChanges);
          // Notify change listeners
          eventListeners.change.forEach((listener) => listener(newChanges));
        }
      }

      lastSnapshot = newSnapshot;
    } catch (error) {
      const err =
        error instanceof Error
          ? error
          : new Error("Unknown error during change detection");
      // Notify error listeners
      eventListeners.error.forEach((listener) => listener(err));
    }
  }

  return {
    start: () => {
      if (!isRunning) {
        isRunning = true;
        // Take initial snapshot
        checkForChanges();
        // Start periodic checking
        intervalId = window.setInterval(checkForChanges, intervalMs);
      }
    },

    stop: () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
      isRunning = false;
      lastSnapshot = null;
    },

    getChanges: () => [...changes],

    clearChanges: () => {
      changes = [];
    },

    forceCheck: checkForChanges,

    setInterval: (ms: number) => {
      intervalMs = ms;
      if (isRunning && intervalId !== null) {
        clearInterval(intervalId);
        intervalId = window.setInterval(checkForChanges, intervalMs);
      }
    },

    on: (event: EventType, listener: EventsListener | ErrorsListener) => {
      if (event === "change" || event === "error") {
        eventListeners[event].push(listener as any);
      }
    },

    off: (event: EventType, listener: EventsListener | ErrorsListener) => {
      if (event === "change" || event === "error") {
        const index = eventListeners[event].indexOf(listener as any);
        if (index > -1) {
          eventListeners[event].splice(index, 1);
        }
      }
    },
  };
}
