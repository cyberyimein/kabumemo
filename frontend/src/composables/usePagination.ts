import { computed, ref, watch } from "vue";
import type { ComputedRef, Ref } from "vue";

interface UsePaginationOptions {
  pageSize?: number;
  initialPage?: number;
}

interface UsePaginationResult {
  page: Ref<number>;
  pageSize: number;
  totalItems: ComputedRef<number>;
  totalPages: ComputedRef<number>;
  offset: ComputedRef<number>;
  endIndex: ComputedRef<number>;
  canPrev: ComputedRef<boolean>;
  canNext: ComputedRef<boolean>;
  setPage: (value: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  reset: () => void;
}

const DEFAULT_PAGE_SIZE = 50;

export function usePagination(
  totalItems: ComputedRef<number>,
  options: UsePaginationOptions = {}
): UsePaginationResult {
  const pageSize = Math.max(1, options.pageSize ?? DEFAULT_PAGE_SIZE);
  const page = ref(Math.max(1, options.initialPage ?? 1));

  const totalPages = computed(() => {
    const total = totalItems.value;
    if (!Number.isFinite(total) || total <= 0) {
      return 1;
    }
    return Math.max(1, Math.ceil(total / pageSize));
  });

  const offset = computed(() => (page.value - 1) * pageSize);
  const endIndex = computed(() => Math.min(totalItems.value, offset.value + pageSize));

  const canPrev = computed(() => page.value > 1);
  const canNext = computed(() => page.value < totalPages.value);

  const setPage = (value: number) => {
    if (!Number.isFinite(value)) {
      return;
    }
    const normalized = Math.floor(value);
    const clamped = Math.min(totalPages.value, Math.max(1, normalized));
    page.value = clamped;
  };

  const nextPage = () => {
    if (canNext.value) {
      setPage(page.value + 1);
    }
  };

  const prevPage = () => {
    if (canPrev.value) {
      setPage(page.value - 1);
    }
  };

  const reset = () => {
    page.value = 1;
  };

  watch(
    totalItems,
    () => {
      if (page.value > totalPages.value) {
        page.value = totalPages.value;
      }
      if (page.value < 1) {
        page.value = 1;
      }
    },
    { immediate: true }
  );

  return {
    page,
    pageSize,
    totalItems,
    totalPages,
    offset,
    endIndex,
    canPrev,
    canNext,
    setPage,
    nextPage,
    prevPage,
    reset,
  };
}
