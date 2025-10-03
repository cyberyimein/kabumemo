<template>
  <div class="pagination" role="navigation" :aria-label="t('common.pagination.label')">
    <span class="summary">
      {{ summaryLabel }}
    </span>
    <div class="buttons">
      <button
        type="button"
        class="pagination-btn"
        :disabled="disabled || page <= 1"
        @click="emit('update:page', page - 1)"
      >
        {{ t('common.pagination.previous') }}
      </button>
      <button
        type="button"
        class="pagination-btn"
        :disabled="disabled || page >= totalPages"
        @click="emit('update:page', page + 1)"
      >
        {{ t('common.pagination.next') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  page: number;
  totalPages: number;
  totalItems: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:page", value: number): void;
}>();

const { t } = useI18n();

const summaryLabel = computed(() =>
  t("common.pagination.summary", {
    page: props.totalPages === 0 ? 0 : props.page,
    pages: Math.max(1, props.totalPages),
    total: props.totalItems,
  })
);
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0.2rem;
  color: var(--text-dim);
}

.summary {
  font-size: 0.88rem;
}

.buttons {
  display: flex;
  gap: 0.5rem;
}

.pagination-btn {
  border: 1px solid var(--divider);
  background: var(--panel-alt);
  color: var(--text);
  padding: 0.35rem 0.9rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.pagination-btn:hover:enabled {
  background: rgba(15, 167, 201, 0.1);
  border-color: rgba(15, 167, 201, 0.4);
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .buttons {
    justify-content: space-between;
  }
}
</style>
