import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RTable from "./RTable.vue";

const columns = [{ key: "name", label: "Name" }];
const items = [
  { id: 1, name: "Chrono Trigger" },
  { id: 2, name: "Earthbound" },
];

function mountTable() {
  return mount(RTable, { props: { columns, items, itemKey: "id" } });
}

function enteringRows(wrapper: ReturnType<typeof mountTable>) {
  return wrapper.findAll(".r-table__row--enter");
}

describe("RTable entrance", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );

  // Re-sorting re-inserts rows, which would replay the animation if the class
  // stayed on.
  it("drops the entrance class once the animation has played", async () => {
    const wrapper = mountTable();
    expect(enteringRows(wrapper)).toHaveLength(2);

    await vi.advanceTimersByTimeAsync(699);
    expect(enteringRows(wrapper)).toHaveLength(2);

    await vi.advanceTimersByTimeAsync(1);
    expect(enteringRows(wrapper)).toHaveLength(0);
  });

  it("does not restart the entrance when the rows change mid-animation", async () => {
    const wrapper = mountTable();
    await vi.advanceTimersByTimeAsync(400);

    await wrapper.setProps({ items: [...items].reverse() });
    await vi.advanceTimersByTimeAsync(300);

    expect(enteringRows(wrapper)).toHaveLength(0);
  });
});
