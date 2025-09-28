<template>
  <nav class="tab-bar" :aria-label="ariaLabel">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      class="tab-pill"
      :class="{ 'is-active': tab.id === modelValue }"
      :data-badge="typeof tab.badge === 'number' ? tab.badge : null"
      @click="$emit('update:modelValue', tab.id)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed } from "vue";
interface TabMeta {
  id: string;
  label: string;
  badge?: number;
}

const props = defineProps<{
  tabs: TabMeta[];
  modelValue: string;
  ariaLabel?: string;
}>();

const ariaLabel = computed(() => props.ariaLabel ?? "Navigation");

defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();
</script>

<style scoped>
.tab-bar {
  width: 100%;
}

.tab-pill::after {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.4rem;
}

.tab-pill:not([data-badge])::after {
  content: none;
}
</style>
