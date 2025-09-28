<template>
  <div
    ref="root"
    class="base-select"
    :class="{
      disabled,
      'is-open': isOpen,
      'has-value': Boolean(selectedOption),
    }"
  >
    <button
      type="button"
      class="select-trigger"
      :id="id"
      :aria-haspopup="true"
      :aria-expanded="isOpen"
      :aria-controls="dropdownId"
      :disabled="disabled"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span class="select-value">
        <span v-if="selectedOption">{{ selectedOption.label }}</span>
        <span v-else class="placeholder">{{ placeholder }}</span>
      </span>
      <span class="select-icon" aria-hidden="true">
        <svg viewBox="0 0 16 16" focusable="false">
          <path
            d="M3.5 6.25a.75.75 0 0 1 1.06 0L8 9.69l3.44-3.44a.75.75 0 0 1 1.06 1.06l-3.97 3.97a.75.75 0 0 1-1.06 0L3.5 7.31a.75.75 0 0 1 0-1.06Z"
            fill="currentColor"
          />
        </svg>
      </span>
    </button>

    <transition name="fade-scale">
      <ul
        v-if="isOpen"
        :id="dropdownId"
        class="select-dropdown"
        role="listbox"
        :aria-activedescendant="activeDescendantId"
        tabindex="-1"
        @keydown.prevent.stop="onDropdownKeydown"
      >
        <li
          v-for="(option, index) in options"
          :id="getOptionId(index)"
          :key="option.value"
          class="select-option"
          :class="{
            disabled: option.disabled,
            active: index === highlightedIndex,
            selected: option.value === modelValue,
          }"
          role="option"
          :aria-selected="option.value === modelValue"
          @pointerdown.prevent="onOptionPointerDown(option, index)"
          @mouseenter="highlightedIndex = index"
        >
          <span class="option-label">{{ option.label }}</span>
          <svg
            v-if="option.value === modelValue"
            class="option-check"
            viewBox="0 0 16 16"
            aria-hidden="true"
          >
            <path
              d="M6.5 11.14 3.36 8a.75.75 0 1 1 1.06-1.06L6.5 9.02l5.08-5.08a.75.75 0 1 1 1.06 1.06l-5.61 5.61a.75.75 0 0 1-1.06 0Z"
              fill="currentColor"
            />
          </svg>
        </li>
        <li v-if="!options.length" class="select-option empty" aria-disabled="true">
          {{ emptyLabel }}
        </li>
      </ul>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

interface SelectOption {
  label: string;
  value: string | number;
  disabled?: boolean;
}

const props = withDefaults(
  defineProps<{
    id?: string;
    modelValue: string | number | null;
    options: SelectOption[];
    placeholder?: string;
    disabled?: boolean;
    emptyLabel?: string;
  }>(),
  {
    placeholder: "",
    disabled: false,
    emptyLabel: "No options",
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number | null): void;
  (e: "open-change", open: boolean): void;
}>();

const root = ref<HTMLDivElement | null>(null);
const isOpen = ref(false);
const highlightedIndex = ref(-1);
const dropdownId = `dropdown-${Math.random().toString(36).slice(2, 9)}`;

const selectedOption = computed(() =>
  props.options.find((option) => option.value === props.modelValue)
);

const activeDescendantId = computed(() =>
  highlightedIndex.value >= 0 ? getOptionId(highlightedIndex.value) : undefined
);

function toggle() {
  if (props.disabled) return;
  setOpen(!isOpen.value);
}

function setOpen(value: boolean) {
  if (isOpen.value === value) return;
  isOpen.value = value;
  emit("open-change", value);
  if (value) {
    focusSelectedOrFirst();
    setTimeout(() => {
      const dropdown = root.value?.querySelector<HTMLUListElement>(".select-dropdown");
      dropdown?.focus({ preventScroll: true });
    }, 0);
  }
}

function focusSelectedOrFirst() {
  const selectedIndex = props.options.findIndex(
    (option) => option.value === props.modelValue && !option.disabled
  );
  if (selectedIndex !== -1) {
    highlightedIndex.value = selectedIndex;
    return;
  }
  const firstEnabled = props.options.findIndex((option) => !option.disabled);
  highlightedIndex.value = firstEnabled;
}

function selectOption(option: SelectOption) {
  if (option.disabled) return;
  if (option.value !== props.modelValue) {
    emit("update:modelValue", option.value);
  }
  setOpen(false);
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) return;
  switch (event.key) {
    case "ArrowDown":
    case "ArrowUp":
    case " ":
    case "Enter":
      event.preventDefault();
      setOpen(true);
      break;
    case "Escape":
      setOpen(false);
      break;
    default:
      break;
  }
}

function onDropdownKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "ArrowDown":
      highlightNext();
      break;
    case "ArrowUp":
      highlightPrevious();
      break;
    case "Home":
      highlightFirst();
      break;
    case "End":
      highlightLast();
      break;
    case "Enter":
    case " ":
      if (highlightedIndex.value >= 0) {
        const option = props.options[highlightedIndex.value];
        if (option) selectOption(option);
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

function highlightNext() {
  if (!props.options.length) return;
  let index = highlightedIndex.value;
  for (let i = 0; i < props.options.length; i += 1) {
    index = (index + 1) % props.options.length;
    if (!props.options[index].disabled) {
      highlightedIndex.value = index;
      scrollOptionIntoView(index);
      return;
    }
  }
}

function highlightPrevious() {
  if (!props.options.length) return;
  let index = highlightedIndex.value;
  for (let i = 0; i < props.options.length; i += 1) {
    index = (index - 1 + props.options.length) % props.options.length;
    if (!props.options[index].disabled) {
      highlightedIndex.value = index;
      scrollOptionIntoView(index);
      return;
    }
  }
}

function highlightFirst() {
  const firstEnabled = props.options.findIndex((option) => !option.disabled);
  if (firstEnabled >= 0) {
    highlightedIndex.value = firstEnabled;
    scrollOptionIntoView(firstEnabled);
  }
}

function highlightLast() {
  const lastEnabled = [...props.options].reverse().findIndex((option) => !option.disabled);
  if (lastEnabled >= 0) {
    const realIndex = props.options.length - 1 - lastEnabled;
    highlightedIndex.value = realIndex;
    scrollOptionIntoView(realIndex);
  }
}

function scrollOptionIntoView(index: number) {
  const dropdown = root.value?.querySelector<HTMLElement>(".select-dropdown");
  const optionEl = dropdown?.children[index] as HTMLElement | undefined;
  if (dropdown && optionEl) {
    const { offsetTop, offsetHeight } = optionEl;
    const visibleTop = dropdown.scrollTop;
    const visibleBottom = visibleTop + dropdown.clientHeight;
    if (offsetTop < visibleTop) {
      dropdown.scrollTo({ top: offsetTop, behavior: "smooth" });
    } else if (offsetTop + offsetHeight > visibleBottom) {
      dropdown.scrollTo({ top: offsetTop - dropdown.clientHeight + offsetHeight, behavior: "smooth" });
    }
  }
}

function onOptionPointerDown(option: SelectOption, index: number) {
  if (option.disabled) return;
  highlightedIndex.value = index;
  selectOption(option);
}

function onClickOutside(event: MouseEvent | TouchEvent) {
  if (!root.value) return;
  if (!root.value.contains(event.target as Node)) {
    setOpen(false);
  }
}

function getOptionId(index: number) {
  return `${dropdownId}-option-${index}`;
}

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) setOpen(false);
  }
);

watch(
  () => props.options,
  () => {
    if (isOpen.value) {
      focusSelectedOrFirst();
    }
  },
  { deep: true }
);

watch(
  () => props.modelValue,
  () => {
    if (!isOpen.value) {
      highlightedIndex.value = props.options.findIndex(
        (option) => option.value === props.modelValue
      );
    }
  }
);

onMounted(() => {
  document.addEventListener("mousedown", onClickOutside);
  document.addEventListener("touchstart", onClickOutside, { passive: true });
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onClickOutside);
  document.removeEventListener("touchstart", onClickOutside);
});
</script>

<style scoped>
.base-select {
  position: relative;
  width: 100%;
  font-size: 0.95rem;
}

.base-select.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.select-trigger {
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

.select-trigger:hover {
  border-color: rgba(15, 167, 201, 0.5);
}

.base-select.is-open .select-trigger,
.select-trigger:focus-visible {
  border-color: var(--focus-ring);
  box-shadow: 0 0 0 3px rgba(11, 61, 145, 0.18);
  outline: none;
}

.select-value {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: inherit;
}

.placeholder {
  color: var(--text-faint);
}

.select-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 0.75rem;
  color: var(--text-dim);
}

.select-icon svg {
  width: 1rem;
  height: 1rem;
}

.select-dropdown {
  position: absolute;
  z-index: 30;
  top: calc(100% + 0.4rem);
  left: 0;
  right: 0;
  max-height: 16rem;
  overflow-y: auto;
  border-radius: var(--radius-md);
  border: 1px solid rgba(199, 210, 220, 0.85);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  box-shadow: var(--shadow-raised);
  padding: 0.35rem;
  list-style: none;
  margin: 0;
  outline: none;
}

.select-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
  border-radius: var(--radius-sm);
  color: var(--text);
  cursor: pointer;
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.select-option:hover,
.select-option.active {
  background: rgba(15, 167, 201, 0.18);
  color: var(--accent);
}

.select-option.selected {
  font-weight: 600;
}

.select-option.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.select-option.disabled:hover,
.select-option.disabled.active {
  background: transparent;
  color: inherit;
}

.option-label {
  flex: 1 1 auto;
}

.option-check {
  width: 1rem;
  height: 1rem;
  color: var(--accent-cyan);
}

.select-option.empty {
  justify-content: center;
  color: var(--text-faint);
  cursor: default;
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
