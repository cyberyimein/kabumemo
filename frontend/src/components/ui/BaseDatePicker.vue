<template>
  <div
    ref="root"
    class="base-date-picker"
    :class="{
      disabled,
      'is-open': isOpen,
    }"
  >
    <button
      ref="trigger"
      type="button"
      class="date-trigger"
      :disabled="disabled"
      :aria-expanded="isOpen"
      :aria-haspopup="true"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span class="date-value" :class="{ placeholder: !selectedDate }">
        {{ selectedDate ? displayLabel : placeholderLabel }}
      </span>
      <span class="date-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20" focusable="false">
          <path
            d="M6 2.5v2m8-2v2M3.5 6.75h13M4.25 4.5h11.5a1.25 1.25 0 0 1 1.25 1.25v9.5A2.75 2.75 0 0 1 14.25 18H5.75A2.75 2.75 0 0 1 3 15.25v-9.5A1.25 1.25 0 0 1 4.25 4.5Zm2.5 6h1.5m2 0h1.5m-5 3h1.5m2 0h1.5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </button>

    <transition name="fade-scale">
      <div
        v-if="isOpen"
        ref="panel"
        class="date-dropdown"
        role="dialog"
        tabindex="-1"
        @keydown.stop="onPanelKeydown"
      >
        <header class="date-header">
          <button type="button" class="nav-btn" @click="goToPreviousMonth" aria-label="Previous month">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10.5 3.5 5.5 8l5 4.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <div class="date-header-center">
            <div class="month-label" aria-live="polite">{{ monthLabel }}</div>
            <div class="month-year-controls">
              <select
                v-model.number="monthSelectProxy"
                class="month-year-select month-select"
                :aria-label="monthAriaLabel"
              >
                <option v-for="option in monthOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <select
                v-model.number="yearSelectProxy"
                class="month-year-select year-select"
                :aria-label="yearAriaLabel"
              >
                <option v-for="year in yearOptions" :key="year" :value="year">
                  {{ year }}
                </option>
              </select>
            </div>
          </div>
          <button type="button" class="nav-btn" @click="goToNextMonth" aria-label="Next month">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M5.5 3.5 10.5 8l-5 4.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </header>

        <div class="weekday-row">
          <span v-for="(day, index) in weekdayNames" :key="index">{{ day }}</span>
        </div>

        <div class="date-grid" role="grid">
          <button
            v-for="(cell, index) in calendarCells"
            :key="cell.iso"
            type="button"
            class="date-cell"
            :class="{
              'is-outside': !cell.isCurrentMonth,
              'is-today': cell.isToday,
              'is-selected': cell.isSelected,
              'is-active': index === activeIndex,
            }"
            @click="selectCell(cell, index)"
          >
            {{ cell.label }}
          </button>
        </div>

        <footer class="date-footer">
          <button type="button" class="ghost-button" @click="selectToday">
            {{ todayLabel }}
          </button>
        </footer>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

type CalendarCell = {
  date: Date;
  label: number;
  iso: string;
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
};

const props = withDefaults(
  defineProps<{
    modelValue: string | null;
    placeholder?: string;
    disabled?: boolean;
  }>(),
  {
    placeholder: "",
    disabled: false,
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | null): void;
}>();

const { locale, t } = useI18n();

const root = ref<HTMLDivElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const panel = ref<HTMLDivElement | null>(null);
const isOpen = ref(false);
const viewYear = ref(new Date().getFullYear());
const viewMonth = ref(new Date().getMonth());
const activeIndex = ref(-1);

const placeholderLabel = computed(() => props.placeholder || t("common.select"));
const todayLabel = computed(() => t("common.actions.today", "Today"));
const monthAriaLabel = computed(() => t("common.labels.month", "Month"));
const yearAriaLabel = computed(() => t("common.labels.year", "Year"));

const selectedDate = computed(() => parseDate(props.modelValue));
const displayLabel = computed(() => {
  if (!selectedDate.value) return "";
  return new Intl.DateTimeFormat(locale.value, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(selectedDate.value);
});

const monthLabel = computed(() =>
  new Intl.DateTimeFormat(locale.value, {
    year: "numeric",
    month: "long",
  }).format(new Date(viewYear.value, viewMonth.value, 1))
);

const weekdayNames = computed(() => {
  const normalizedLocale = locale.value.toLowerCase();
  if (normalizedLocale.startsWith("zh")) {
    return ["日", "一", "二", "三", "四", "五", "六"];
  }
  const formatter = new Intl.DateTimeFormat(locale.value, { weekday: "short" });
  const base = new Date(Date.UTC(2021, 5, 6)); // Sunday
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(base);
    date.setUTCDate(base.getUTCDate() + index);
    const label = formatter.format(date);
    return label.length > 3 ? label.slice(0, 3) : label;
  });
});

const calendarCells = computed<CalendarCell[]>(() => {
  const firstOfMonth = new Date(viewYear.value, viewMonth.value, 1);
  const startDay = firstOfMonth.getDay();
  const startDate = new Date(viewYear.value, viewMonth.value, 1 - startDay);
  const cells: CalendarCell[] = [];
  const today = new Date();
  const selected = selectedDate.value;
  for (let i = 0; i < 42; i += 1) {
    const current = new Date(startDate);
    current.setDate(startDate.getDate() + i);
    cells.push({
      date: current,
      label: current.getDate(),
      iso: formatDateValue(current),
      isCurrentMonth:
        current.getMonth() === viewMonth.value && current.getFullYear() === viewYear.value,
      isToday: isSameDate(current, today),
      isSelected: selected ? isSameDate(current, selected) : false,
    });
  }
  if (cells.slice(-7).every((cell) => !cell.isCurrentMonth)) {
    cells.splice(-7, 7);
  }
  return cells;
});

const monthOptions = computed(() => {
  const formatter = new Intl.DateTimeFormat(locale.value, { month: "long" });
  return Array.from({ length: 12 }, (_, index) => ({
    value: index,
    label: formatter.format(new Date(2020, index, 1)),
  }));
});

const yearOptions = computed(() => {
  const minYear = 1900;
  const currentYear = new Date().getFullYear();
  const candidates = [currentYear, viewYear.value];
  if (selectedDate.value) {
    candidates.push(selectedDate.value.getFullYear());
  }
  const maxYear = Math.max(...candidates) + 40;
  return Array.from({ length: maxYear - minYear + 1 }, (_, index) => minYear + index);
});

const monthSelectProxy = computed({
  get: () => viewMonth.value,
  set: (value) => {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) return;
    viewMonth.value = parsed;
    activeIndex.value = findInitialActiveIndex();
  },
});

const yearSelectProxy = computed({
  get: () => viewYear.value,
  set: (value) => {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) return;
    viewYear.value = parsed;
    activeIndex.value = findInitialActiveIndex();
  },
});

watch([viewYear, viewMonth], () => {
  if (!isOpen.value) return;
  nextTick(() => {
    activeIndex.value = findInitialActiveIndex();
  });
});

watch(
  () => props.modelValue,
  (value) => {
    const parsed = parseDate(value);
    if (parsed) {
      viewYear.value = parsed.getFullYear();
      viewMonth.value = parsed.getMonth();
    }
  },
  { immediate: true }
);

function toggle() {
  if (props.disabled) return;
  setOpen(!isOpen.value);
}

function setOpen(value: boolean) {
  if (isOpen.value === value) return;
  if (value && props.disabled) return;
  if (value) {
    alignViewToSelected();
    isOpen.value = true;
    nextTick(() => {
      activeIndex.value = findInitialActiveIndex();
      panel.value?.focus({ preventScroll: true });
    });
  } else {
    isOpen.value = false;
    activeIndex.value = -1;
    nextTick(() => trigger.value?.focus());
  }
}

function alignViewToSelected() {
  const base = selectedDate.value ?? new Date();
  viewYear.value = base.getFullYear();
  viewMonth.value = base.getMonth();
}

function findInitialActiveIndex() {
  const selectedIndex = calendarCells.value.findIndex((cell) => cell.isSelected);
  if (selectedIndex >= 0) {
    return selectedIndex;
  }
  const firstCurrent = calendarCells.value.findIndex((cell) => cell.isCurrentMonth);
  return firstCurrent >= 0 ? firstCurrent : 0;
}

function selectCell(cell: CalendarCell, index: number) {
  emit("update:modelValue", cell.iso);
  activeIndex.value = index;
  setOpen(false);
}

function selectToday() {
  const today = new Date();
  viewYear.value = today.getFullYear();
  viewMonth.value = today.getMonth();
  emit("update:modelValue", formatDateValue(today));
  setOpen(false);
}

function goToPreviousMonth() {
  if (viewMonth.value === 0) {
    viewMonth.value = 11;
    viewYear.value -= 1;
  } else {
    viewMonth.value -= 1;
  }
  activeIndex.value = findInitialActiveIndex();
}

function goToNextMonth() {
  if (viewMonth.value === 11) {
    viewMonth.value = 0;
    viewYear.value += 1;
  } else {
    viewMonth.value += 1;
  }
  activeIndex.value = findInitialActiveIndex();
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) return;
  if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
    event.preventDefault();
    setOpen(true);
  }
}

function onPanelKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "ArrowRight":
      event.preventDefault();
      moveActive(1);
      break;
    case "ArrowLeft":
      event.preventDefault();
      moveActive(-1);
      break;
    case "ArrowUp":
      event.preventDefault();
      moveActive(-7);
      break;
    case "ArrowDown":
      event.preventDefault();
      moveActive(7);
      break;
    case "Home":
      event.preventDefault();
      moveActiveToRowStart();
      break;
    case "End":
      event.preventDefault();
      moveActiveToRowEnd();
      break;
    case "PageUp":
      event.preventDefault();
      goToPreviousMonth();
      break;
    case "PageDown":
      event.preventDefault();
      goToNextMonth();
      break;
    case "Enter":
    case " ":
      event.preventDefault();
      if (activeIndex.value >= 0) {
        const cell = calendarCells.value[activeIndex.value];
        if (cell) selectCell(cell, activeIndex.value);
      }
      break;
    case "Escape":
      setOpen(false);
      break;
    case "Tab":
      setOpen(false);
      break;
    default:
      break;
  }
}

function moveActive(step: number) {
  if (!calendarCells.value.length) return;
  const currentIndex = activeIndex.value >= 0 ? activeIndex.value : findInitialActiveIndex();
  const nextIndex = clampIndex(currentIndex + step);
  activeIndex.value = nextIndex;
  const cell = calendarCells.value[nextIndex];
  if (!cell) return;
  if (!cell.isCurrentMonth) {
    if (cell.date < new Date(viewYear.value, viewMonth.value, 1)) {
      goToPreviousMonth();
      nextTick(() => {
        const target = calendarCells.value.findIndex((item) => item.iso === formatDateValue(cell.date));
        if (target >= 0) {
          activeIndex.value = target;
        }
      });
    } else if (
      cell.date >
      new Date(viewYear.value, viewMonth.value + 1, 0)
    ) {
      goToNextMonth();
      nextTick(() => {
        const target = calendarCells.value.findIndex((item) => item.iso === formatDateValue(cell.date));
        if (target >= 0) {
          activeIndex.value = target;
        }
      });
    }
  }
}

function moveActiveToRowStart() {
  if (!calendarCells.value.length || activeIndex.value < 0) return;
  const rowStart = Math.floor(activeIndex.value / 7) * 7;
  activeIndex.value = rowStart;
}

function moveActiveToRowEnd() {
  if (!calendarCells.value.length || activeIndex.value < 0) return;
  const rowEnd = Math.floor(activeIndex.value / 7) * 7 + 6;
  activeIndex.value = clampIndex(rowEnd);
}

function clampIndex(target: number) {
  if (target < 0) return 0;
  if (target >= calendarCells.value.length) return calendarCells.value.length - 1;
  return target;
}

function onClickOutside(event: MouseEvent | TouchEvent) {
  if (!root.value) return;
  if (!root.value.contains(event.target as Node)) {
    setOpen(false);
  }
}

onMounted(() => {
  document.addEventListener("mousedown", onClickOutside);
  document.addEventListener("touchstart", onClickOutside, { passive: true });
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onClickOutside);
  document.removeEventListener("touchstart", onClickOutside);
});

function parseDate(value: string | null): Date | null {
  if (!value) return null;
  const parts = value.split("-").map((part) => Number.parseInt(part, 10));
  if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
  const [year, month, day] = parts;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null;
  }
  return date;
}

function formatDateValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isSameDate(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
</script>

<style scoped>
.base-date-picker {
  position: relative;
  width: 100%;
}

.base-date-picker.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.date-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 0.85rem;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(199, 210, 220, 0.85);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition), transform var(--transition);
}

.date-trigger:hover {
  border-color: rgba(15, 167, 201, 0.5);
}

.base-date-picker.is-open .date-trigger,
.date-trigger:focus-visible {
  border-color: var(--focus-ring);
  box-shadow: 0 0 0 3px rgba(11, 61, 145, 0.18);
  outline: none;
}

.date-value {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: inherit;
}

.date-value.placeholder {
  color: var(--text-faint);
}

.date-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.75rem;
  color: var(--text-dim);
}

.date-icon svg {
  width: 1.1rem;
  height: 1.1rem;
}

.date-dropdown {
  position: absolute;
  z-index: 40;
  top: calc(100% + 0.4rem);
  left: 0;
  right: auto;
  border-radius: var(--radius-md);
  border: 1px solid rgba(199, 210, 220, 0.85);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  box-shadow: var(--shadow-raised);
  padding: 0.7rem;
  outline: none;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  width: max(100%, clamp(14.4rem, 36vw, 19.2rem));
  max-width: min(22.5rem, calc(100vw - 2.5rem));
  font-size: 0.8rem;
}

.date-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
}

.date-header-center {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
}

.month-label {
  font-weight: 600;
  color: var(--accent);
  font-size: 0.88rem;
}

.month-year-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  width: 100%;
}

.month-year-select {
  flex: 1 1 8.5rem;
  min-width: 6rem;
  max-width: 9.5rem;
  padding: 0.38rem 1.6rem 0.38rem 0.6rem;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(199, 210, 220, 0.85);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  background-color: var(--panel);
  color: var(--text);
  font-size: 0.78rem;
  line-height: 1.15;
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition), color var(--transition);
  appearance: none;
  -moz-appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='currentColor' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.55rem center;
  background-size: 0.75rem;
}

.month-year-select:hover {
  border-color: rgba(15, 167, 201, 0.5);
  color: var(--accent);
}

.month-year-select:focus-visible {
  border-color: var(--focus-ring);
  box-shadow: 0 0 0 3px rgba(11, 61, 145, 0.18);
  outline: none;
}

.month-select {
  flex: 1 1 9.2rem;
}

.year-select {
  flex: 0 0 6rem;
}

:deep(.month-year-select::-ms-expand) {
  display: none;
}

.nav-btn {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(199, 210, 220, 0.85);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  color: var(--text-dim);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color var(--transition), color var(--transition), transform var(--transition);
}

.nav-btn:hover {
  border-color: rgba(15, 167, 201, 0.5);
  color: var(--accent);
  transform: translateY(-1px);
}

.nav-btn svg {
  width: 0.9rem;
  height: 0.9rem;
}

.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.3rem;
  text-align: center;
  font-size: 0.68rem;
  letter-spacing: 0.4px;
  color: var(--text-faint);
  text-transform: uppercase;
}

.date-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.3rem;
}

.date-cell {
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text);
  font-size: 0.82rem;
  padding: 0.5rem 0;
  cursor: pointer;
  position: relative;
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.date-cell:hover,
.date-cell.is-active {
  background: rgba(15, 167, 201, 0.15);
  color: var(--accent);
}

.date-cell.is-outside {
  color: var(--text-faint);
}

.date-cell.is-today {
  box-shadow: inset 0 0 0 1px rgba(15, 167, 201, 0.35);
  border-radius: var(--radius-sm);
}

.date-cell.is-selected {
  background: linear-gradient(180deg, rgba(15, 167, 201, 0.2), rgba(15, 167, 201, 0.35));
  color: var(--accent);
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgba(15, 167, 201, 0.4);
}

.date-footer {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
}

.date-footer .ghost-button {
  flex: 1 1 auto;
  border: 1px solid var(--divider);
  background: transparent;
  color: var(--text-dim);
  padding: 0.38rem;
  border-radius: var(--radius-sm);
  font-size: 0.74rem;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition), background var(--transition);
}

.date-footer .ghost-button:hover {
  color: var(--accent);
  border-color: rgba(15, 167, 201, 0.45);
  background: rgba(15, 167, 201, 0.1);
}

.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: opacity 120ms ease, transform 120ms ease;
}

.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
