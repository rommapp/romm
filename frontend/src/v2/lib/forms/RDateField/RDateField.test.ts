import { enableAutoUnmount, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import RDateField from "./RDateField.vue";

// Runs in a timezone west of UTC on purpose: the picker emits UTC midnight,
// so any local-time getter left in the calendar reads back as the previous
// day and every cell in the grid shifts by one. See rommapp/romm#4321.
process.env.TZ = "America/New_York";

// The calendar teleports to <body>, so a wrapper left mounted by a failing
// assertion would leak its panel into the next test's queries.
enableAutoUnmount(afterEach);

async function openPicker() {
  const wrapper = mount(RDateField, {
    props: { modelValue: Date.UTC(2024, 2, 15) },
    attachTo: document.body,
  });
  await wrapper.get("input").trigger("click");
  await wrapper.vm.$nextTick();
  return wrapper;
}

function dayCell(day: number) {
  return document.querySelector<HTMLButtonElement>(
    `.r-date-cal__day[data-day-key="2024-2-${day}"]`,
  );
}

function focusedKey() {
  return document
    .querySelector('.r-date-cal__day[tabindex="0"]')
    ?.getAttribute("data-day-key");
}

describe("RDateField", () => {
  beforeAll(() => {
    // Guard the guard: without a west-of-UTC offset these tests pass either way.
    expect(new Date().getTimezoneOffset()).toBeGreaterThan(0);
  });

  it("shows the selected day, not the one before it", () => {
    const wrapper = mount(RDateField, {
      props: { modelValue: Date.UTC(2024, 2, 15) },
    });
    expect(wrapper.get("input").element.value).toBe("Mar 15, 2024");
  });

  it("does not let displayFormat move the label off UTC", () => {
    const wrapper = mount(RDateField, {
      props: {
        modelValue: Date.UTC(2024, 2, 15),
        displayFormat: { dateStyle: "medium", timeZone: "America/New_York" },
      },
    });
    expect(wrapper.get("input").element.value).toBe("Mar 15, 2024");
  });

  it("opens on the month of the selected value", async () => {
    await openPicker();
    expect(document.querySelector(".r-date-cal__title")?.textContent).toContain(
      "March",
    );
    expect(dayCell(15)?.classList).toContain("r-date-cal__day--selected");
  });

  it("lines the grid up under the weekday header", async () => {
    await openPicker();
    const headers = Array.from(
      document.querySelectorAll(".r-date-cal__weekday"),
      (n) => n.textContent?.trim(),
    );
    expect(headers[0]).toBe("Mon");

    // firstDayOfWeek defaults to Monday and March 2024 opens on a Friday, so
    // the grid leads with Mon 26 Feb.
    const first = document.querySelector(".r-date-cal__day");
    expect(first?.getAttribute("data-day-key")).toBe("2024-1-26");
  });

  it("emits the day that was clicked", async () => {
    const wrapper = await openPicker();
    const cell = dayCell(22);
    expect(cell?.textContent?.trim()).toBe("22");

    cell?.click();
    await wrapper.vm.$nextTick();

    const picked = wrapper.emitted("update:modelValue")?.[0]?.[0] as Date;
    expect(picked.getTime()).toBe(Date.UTC(2024, 2, 22));
  });

  it("walks one day per arrow key", async () => {
    const wrapper = await openPicker();
    expect(focusedKey()).toBe("2024-2-15");

    const panel = document.querySelector(".r-date-cal") as HTMLElement;
    for (const key of ["ArrowRight", "ArrowDown"]) {
      panel.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
      await wrapper.vm.$nextTick();
    }
    expect(focusedKey()).toBe("2024-2-23");
  });

  it("keeps the label and the emitted value on the same day", async () => {
    const wrapper = await openPicker();
    dayCell(1)?.click();
    await wrapper.vm.$nextTick();

    const picked = wrapper.emitted("update:modelValue")?.[0]?.[0] as Date;
    await wrapper.setProps({ modelValue: picked });
    expect(wrapper.get("input").element.value).toBe("Mar 1, 2024");
  });
});
