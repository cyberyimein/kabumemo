<template>
  <section class="positions-panel surface-panel app-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("positions.title") }}</h2>
        <p>{{ t("positions.description") }}</p>
      </div>
      <div class="header-actions">
        <button type="button" class="ghost-button" :disabled="splitDetectionLoading" @click="runSplitDetection">
          {{ splitDetectionLoading ? t("positions.splitDetection.loading") : t("positions.splitDetection.action") }}
        </button>
        <button
          type="button"
          class="primary-btn"
          :disabled="!selectedPosition"
          @click="openHistory"
        >
          {{ t("positions.actions.viewHistory") }}
        </button>
        <button type="button" class="ghost-button" @click="$emit('refresh-quotes')">
          {{ t("positions.actions.refreshQuotes") }}
        </button>
        <button type="button" class="refresh-button" @click="$emit('refresh')">
          {{ t("common.actions.refresh") }}
        </button>
      </div>
    </header>

    <section v-if="splitDetectionOpen" class="split-detection">
      <div class="split-detection__header">
        <div>
          <h3>{{ t("positions.splitDetection.title") }}</h3>
          <p>{{ t("positions.splitDetection.description") }}</p>
        </div>
        <button type="button" class="ghost-button" @click="splitDetectionOpen = false">{{ t("common.actions.close") }}</button>
      </div>
      <p v-if="splitDetectionError" class="split-detection__error">{{ splitDetectionError }}</p>
      <template v-else-if="splitDetectionResult">
        <p class="split-detection__summary">
          {{ t("positions.splitDetection.summary", { count: splitDetectionResult.scanned_symbols, candidates: splitDetectionResult.candidates.length }) }}
        </p>
        <p v-if="splitDetectionResult.failed_symbols.length" class="split-detection__warning">
          {{ t("positions.splitDetection.failed", { symbols: splitDetectionResult.failed_symbols.join(', ') }) }}
        </p>
        <div v-if="splitDetectionResult.candidates.length" class="table-scroll split-table">
          <table>
            <thead><tr>
              <th>{{ t("positions.table.symbol") }}</th>
              <th>{{ t("positions.splitDetection.date") }}</th>
              <th>{{ t("positions.splitDetection.ratio") }}</th>
              <th class="numeric">{{ t("positions.splitDetection.before") }}</th>
              <th class="numeric">{{ t("positions.splitDetection.after") }}</th>
              <th></th>
            </tr></thead>
            <tbody><tr v-for="candidate in splitDetectionResult.candidates" :key="`${candidate.symbol}-${candidate.effective_date}`">
              <td><strong>{{ candidate.symbol }}</strong></td>
              <td>{{ candidate.effective_date }}</td>
              <td>1 : {{ formatNumber(candidate.ratio_after) }}</td>
              <td class="numeric">{{ formatNumber(candidate.quantity_before) }}</td>
              <td class="numeric"><input v-model.number="candidate.suggested_quantity_after" class="quantity-correction" type="number" min="0" step="0.000001" /></td>
              <td class="numeric"><button type="button" class="primary-btn" :disabled="registeringSplitKey === splitCandidateKey(candidate)" @click="registerSplitCandidate(candidate)">{{ t("positions.splitDetection.apply") }}</button></td>
            </tr></tbody>
          </table>
        </div>
        <p v-else class="split-detection__empty">{{ t("positions.splitDetection.empty") }}</p>
      </template>
    </section>

    <p v-if="quotes?.as_of" class="quotes-meta">
      {{ t("positions.quotesAsOf", { date: quotes.as_of }) }}
    </p>

    <div class="position-kpis">
      <article>
        <span>{{ t("positions.summary.open") }}</span>
        <strong>{{ activePositions.length }}</strong>
        <small>{{ t("positions.summary.closed", { count: closedPositions.length }) }}</small>
      </article>
      <article>
        <span>{{ t("positions.summary.jp") }}</span>
        <strong>{{ jpPositionCount }}</strong>
        <small>Tokyo Stock Exchange</small>
      </article>
      <article>
        <span>{{ t("positions.summary.us") }}</span>
        <strong>{{ usPositionCount }}</strong>
        <small>NYSE / NASDAQ</small>
      </article>
      <article class="position-kpis__wide">
        <span>{{ t("positions.summary.unrealized") }}</span>
        <div class="currency-results">
          <strong v-for="item in unrealizedByCurrency" :key="item.currency" :class="valueClass(item.value)">
            {{ formatCurrencyValue(item.value, item.currency) }}
          </strong>
        </div>
        <small>{{ t("positions.summary.marketValueHint") }}</small>
      </article>
    </div>

    <div v-if="selectedPosition" class="selection-details selection-details--position">
      <div class="selection-details__header">
        <span class="selection-pill">{{ selectedPosition.symbol }}</span>
        <div class="inline-tags">
          <span class="flat-tag">{{ marketLabel(selectedPosition.market) }}</span>
          <span
            v-for="entry in selectedPosition.breakdown"
            :key="`${selectedPosition.symbol}-${entry.currency}`"
            class="flat-tag"
          >
            {{ currencySymbol(entry.currency) }}
          </span>
        </div>
      </div>
      <div v-if="selectedPosition.group_breakdown.length" class="group-summary-list">
        <div v-for="group in selectedPosition.group_breakdown" :key="groupKey(selectedPosition, group)" class="group-summary-item">
          <span>{{ group.funding_group }}</span>
          <strong>{{ formatGroupQuantity(group) }}</strong>
          <span>{{ formatCurrencyValue(group.average_cost, group.currency) }}</span>
        </div>
      </div>
    </div>

    <div class="surface-group">
      <section class="surface positions-ledger">
        <div class="ledger-heading">
          <h3>{{ t("positions.activeTitle", { count: activePositions.length }) }}</h3>
          <span>{{ t("positions.selectionHint") }}</span>
        </div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("positions.table.symbol") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.cost") }}</th>
                <th class="numeric">{{ t("positions.table.price") }}</th>
                <th class="numeric">{{ t("positions.table.unrealized") }}</th>
                <th>{{ t("positions.table.source") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activePositions.length">
                <td colspan="6" class="empty">{{ t("positions.emptyActive") }}</td>
              </tr>
              <tr
                v-for="item in pagedActivePositions"
                :key="rowKey(item)"
                :class="['position-row', { selected: isSelected(item) }]"
                tabindex="0"
                @click="handleRowClick(item)"
                @keydown.enter.prevent="handleRowClick(item)"
              >
                  <td>
                    <div class="symbol-cell">
                      <span class="market-dot" :class="`market-dot--${item.market.toLowerCase()}`"></span>
                      <div><strong>{{ item.symbol }}</strong><small>{{ marketLabel(item.market) }}</small></div>
                    </div>
                  </td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td class="numeric">{{ formatAverageCostBreakdown(item.breakdown) }}</td>
                  <td class="numeric">{{ formatPriceBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', unrealizedClass(item.breakdown)]">
                    {{ formatUnrealizedBreakdown(item.breakdown) }}
                  </td>
                  <td>
                    <div class="inline-tags">
                      <span class="flat-tag">{{ item.group_breakdown.length }} {{ t("positions.groupTable.group") }}</span>
                    </div>
                  </td>
                </tr>
            </tbody>
          </table>
        </div>
        <PaginationControls
          v-if="activeTotalItems || activeTotalPages > 1"
          :page="activePage"
          :total-pages="activeTotalPages"
          :total-items="activeTotalItems"
          @update:page="setActivePage"
        />
      </section>

      <section class="surface closed-section">
        <div class="closed-section__header">
          <h3>{{ t("positions.closedTitle", { count: closedPositions.length }) }}</h3>
          <button type="button" class="ghost-button" @click="showClosed = !showClosed">
            {{ showClosed ? t("positions.actions.collapseClosed") : t("positions.actions.expandClosed") }}
          </button>
        </div>
        <template v-if="showClosed">
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("positions.table.symbol") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.pl") }}</th>
                <th>{{ t("positions.table.source") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!closedPositions.length">
                <td colspan="4" class="empty">{{ t("positions.emptyClosed") }}</td>
              </tr>
              <tr
                v-for="item in pagedClosedPositions"
                :key="rowKey(item)"
                :class="['position-row', { selected: isSelected(item) }]"
                tabindex="0"
                @click="handleRowClick(item)"
                @keydown.enter.prevent="handleRowClick(item)"
              >
                  <td>
                    <div class="symbol-cell">
                      <span class="market-dot" :class="`market-dot--${item.market.toLowerCase()}`"></span>
                      <div><strong>{{ item.symbol }}</strong><small>{{ marketLabel(item.market) }}</small></div>
                    </div>
                  </td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatProfitBreakdown(item.breakdown) }}
                  </td>
                  <td>
                    <div class="inline-tags">
                      <span class="flat-tag">{{ item.group_breakdown.length }} {{ t("positions.groupTable.group") }}</span>
                    </div>
                  </td>
                </tr>
            </tbody>
          </table>
        </div>
        <PaginationControls
          v-if="closedTotalItems || closedTotalPages > 1"
          :page="closedPage"
          :total-pages="closedTotalPages"
          :total-items="closedTotalItems"
          @update:page="setClosedPage"
        />
        </template>
      </section>
    </div>
  </section>

  <div v-if="historyOpen" class="modal-backdrop" @click.self="closeHistory">
    <div class="modal-panel" role="dialog" aria-modal="true">
      <header class="modal-header">
        <h3>{{ t("positions.history.title", { symbol: historyTitle }) }}</h3>
        <button type="button" class="ghost-button" @click="closeHistory">
          {{ t("common.actions.close") }}
        </button>
      </header>
      <section class="modal-body">
        <p v-if="historyLoading" class="modal-status">
          {{ t("positions.history.loading") }}
        </p>
        <p v-else-if="historyError" class="modal-status error">
          {{ historyError }}
        </p>
        <p v-else-if="!historyData || !historyData.series.length" class="modal-status">
          {{ t("positions.history.empty") }}
        </p>
        <div v-else ref="historyChartEl" class="history-chart"></div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import * as echarts from "echarts";

import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import { ApiError, detectStockSplits, getPositionHistory } from "@/services/api";
import type {
  Position,
  PositionBreakdown,
  PositionGroupBreakdown,
  PositionHistoryResponse,
  QuoteSnapshot,
  StockSplitCandidate,
  StockSplitDetectionResponse,
  StockSplitPayload,
} from "@/types/api";

const props = defineProps<{ positions: Position[]; quotes?: QuoteSnapshot | null }>();

type StockSplitRegistrationEvent = {
  data: StockSplitPayload;
  onDone: (success: boolean) => void;
};

const emit = defineEmits<{
  (e: "refresh"): void;
  (e: "refresh-quotes"): void;
  (e: "register-split", payload: StockSplitRegistrationEvent): void;
}>();

const { t } = useI18n();

function hasOpenQuantity(position: Position): boolean {
  return position.breakdown.some((entry) => Math.abs(entry.quantity) > 1e-9);
}

const activePositions = computed(() => props.positions.filter(hasOpenQuantity));
const showClosed = ref(false);
const jpPositionCount = computed(() => activePositions.value.filter((item) => item.market === "JP").length);
const usPositionCount = computed(() => activePositions.value.filter((item) => item.market === "US").length);
const unrealizedByCurrency = computed(() => {
  const totals = new Map<string, number>();
  activePositions.value.forEach((position) => position.breakdown.forEach((entry) => {
    totals.set(entry.currency, (totals.get(entry.currency) ?? 0) + (entry.unrealized_pl ?? 0));
  }));
  return Array.from(totals, ([currency, value]) => ({ currency: currency as "JPY" | "USD", value }));
});

function valueClass(value: number): string {
  return value > 0 ? "positive" : value < 0 ? "negative" : "";
}

const {
  page: activePage,
  totalPages: activeTotalPages,
  totalItems: activeTotalItems,
  offset: activeOffset,
  pageSize: activePageSize,
  setPage: setActivePage,
} = usePagination(computed(() => activePositions.value.length));

const pagedActivePositions = computed(() =>
  activePositions.value.slice(activeOffset.value, activeOffset.value + activePageSize)
);

const closedPositions = computed(() => props.positions.filter((item) => !hasOpenQuantity(item)));

const {
  page: closedPage,
  totalPages: closedTotalPages,
  totalItems: closedTotalItems,
  offset: closedOffset,
  pageSize: closedPageSize,
  setPage: setClosedPage,
} = usePagination(computed(() => closedPositions.value.length));

const pagedClosedPositions = computed(() =>
  closedPositions.value.slice(closedOffset.value, closedOffset.value + closedPageSize)
);

const selectedKey = ref<string | null>(null);
const selectedPosition = ref<Position | null>(null);
const splitDetectionOpen = ref(false);
const splitDetectionLoading = ref(false);
const splitDetectionError = ref<string | null>(null);
const splitDetectionResult = ref<StockSplitDetectionResponse | null>(null);
const registeringSplitKey = ref<string | null>(null);
const historyOpen = ref(false);
const historyLoading = ref(false);
const historyError = ref<string | null>(null);
const historyData = ref<PositionHistoryResponse | null>(null);
const historyChartEl = ref<HTMLDivElement | null>(null);
let historyChart: echarts.ECharts | null = null;

const historyTitle = computed(() => {
  if (!selectedPosition.value) {
    return "";
  }
  return `${selectedPosition.value.symbol} (${selectedPosition.value.market})`;
});

function rowKey(position: Position): string {
  return `${position.symbol}-${position.market}`;
}

function selectPosition(position: Position): void {
  selectedKey.value = rowKey(position);
  selectedPosition.value = position;
}

function isSelected(position: Position): boolean {
  return selectedKey.value === rowKey(position);
}

function handleRowClick(position: Position): void {
  selectPosition(position);
}

function groupKey(position: Position, entry: PositionGroupBreakdown): string {
  return `${rowKey(position)}-${entry.funding_group}-${entry.currency}`;
}

watch(
  () => props.positions,
  (positions) => {
    const validKeys = new Set(positions.map(rowKey));
    if (selectedKey.value && !validKeys.has(selectedKey.value)) {
      selectedKey.value = null;
      selectedPosition.value = null;
    }
  }
);

function asErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return t("common.states.error");
}

function splitCandidateKey(candidate: StockSplitCandidate): string {
  return `${candidate.symbol}-${candidate.market}-${candidate.effective_date}`;
}

async function runSplitDetection(): Promise<void> {
  splitDetectionOpen.value = true;
  splitDetectionLoading.value = true;
  splitDetectionError.value = null;
  try {
    splitDetectionResult.value = await detectStockSplits();
  } catch (error: unknown) {
    splitDetectionError.value = asErrorMessage(error);
  } finally {
    splitDetectionLoading.value = false;
  }
}

function registerSplitCandidate(candidate: StockSplitCandidate): void {
  if (candidate.quantity_before <= 0 || candidate.suggested_quantity_after <= 0) {
    splitDetectionError.value = t("positions.splitDetection.invalidQuantity");
    return;
  }
  const key = splitCandidateKey(candidate);
  registeringSplitKey.value = key;
  emit("register-split", {
    data: {
      symbol: candidate.symbol,
      market: candidate.market,
      effective_date: candidate.effective_date,
      ratio_before: 1,
      ratio_after: candidate.suggested_quantity_after / candidate.quantity_before,
      notes: t("positions.splitDetection.recordNote"),
    },
    onDone: (success: boolean) => {
      registeringSplitKey.value = null;
      if (!success || !splitDetectionResult.value) return;
      splitDetectionResult.value.candidates = splitDetectionResult.value.candidates.filter(
        (item) => splitCandidateKey(item) !== key
      );
    },
  });
}

async function openHistory(): Promise<void> {
  if (!selectedPosition.value) {
    return;
  }
  historyOpen.value = true;
  await loadHistory();
}

function closeHistory(): void {
  historyOpen.value = false;
  historyError.value = null;
  historyLoading.value = false;
  historyData.value = null;
  if (historyChart) {
    historyChart.dispose();
    historyChart = null;
  }
  window.removeEventListener("resize", handleChartResize);
}

async function loadHistory(): Promise<void> {
  if (!selectedPosition.value) {
    return;
  }
  historyLoading.value = true;
  historyError.value = null;
  historyData.value = null;
  try {
    const result = await getPositionHistory(
      selectedPosition.value.symbol,
      selectedPosition.value.market,
      "1y"
    );
    historyData.value = result;
  } catch (error: unknown) {
    historyError.value = asErrorMessage(error);
  } finally {
    historyLoading.value = false;
    if (historyData.value) {
      await nextTick();
      renderHistoryChart();
    }
  }
}

function renderHistoryChart(): void {
  if (!historyChartEl.value || !historyData.value) {
    return;
  }
  if (!historyChart) {
    historyChart = echarts.init(historyChartEl.value);
    window.addEventListener("resize", handleChartResize);
  }

  const dates = historyData.value.series.map((point) => point.date);
  const closes = historyData.value.series.map((point) => point.close);
  const markers = historyData.value.markers.filter(
    (marker) => marker.currency === historyData.value?.currency
  );
  const buyPoints = markers
    .filter((marker) => marker.side === "buy")
    .map((marker) => [marker.date, marker.price]);
  const sellPoints = markers
    .filter((marker) => marker.side === "sell")
    .map((marker) => [marker.date, marker.price]);

  historyChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
    },
    grid: { left: 50, right: 24, top: 24, bottom: 40 },
    xAxis: {
      type: "category",
      data: dates,
      boundaryGap: false,
      axisLabel: { color: "#6b7280" },
      axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.6)" } },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: "#6b7280" },
      splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
    },
    series: [
      {
        name: "Close",
        type: "line",
        data: closes,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#0ea5e9" },
      },
      {
        name: "Buy",
        type: "scatter",
        data: buyPoints,
        symbol: "triangle",
        symbolSize: 10,
        itemStyle: { color: "#22c55e" },
      },
      {
        name: "Sell",
        type: "scatter",
        data: sellPoints,
        symbol: "triangle",
        symbolRotate: 180,
        symbolSize: 10,
        itemStyle: { color: "#ef4444" },
      },
    ],
  });
}

function handleChartResize(): void {
  historyChart?.resize();
}

onBeforeUnmount(() => {
  if (historyChart) {
    historyChart.dispose();
    historyChart = null;
  }
  window.removeEventListener("resize", handleChartResize);
});

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function currencySymbol(currency: "JPY" | "USD"): string {
  return currency === "USD" ? "$" : "¥";
}

function formatCurrencyValue(value: number, currency: "JPY" | "USD"): string {
  const locale = currency === "USD" ? "en-US" : "ja-JP";
  const formatted = new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

  if (currency === "JPY") {
    return formatted.replace("￥", "¥");
  }
  return formatted;
}

function formatQuantityBreakdown(breakdown: PositionBreakdown[]): string {
  if (!breakdown.length) {
    return "-";
  }

  const totalQuantity = breakdown.reduce((sum, entry) => sum + entry.quantity, 0);
  return formatNumber(totalQuantity);
}

function formatGroupQuantity(entry: PositionGroupBreakdown): string {
  return `${formatNumber(entry.quantity)}${currencySymbol(entry.currency)}`;
}

function formatAverageCostBreakdown(breakdown: PositionBreakdown[]): string {
  if (!breakdown.length) {
    return "-";
  }

  // 将平均成本以本币显示并拼接，帮助用户快速比较多币种成本。
  return breakdown
    .map((entry) => formatCurrencyValue(entry.average_cost, entry.currency))
    .join(" / ");
}

function formatProfitBreakdown(breakdown: PositionBreakdown[]): string {
  if (!breakdown.length) {
    return "-";
  }

  // 同步展示各币种的已实现盈亏，保持和平均成本相同的输出顺序。
  return breakdown
    .map((entry) => formatCurrencyValue(entry.realized_pl, entry.currency))
    .join(" / ");
}

function formatPriceBreakdown(breakdown: PositionBreakdown[]): string {
  if (!breakdown.length) {
    return "-";
  }

  return breakdown
    .map((entry) =>
      entry.current_price == null
        ? "-"
        : formatCurrencyValue(entry.current_price, entry.currency)
    )
    .join(" / ");
}

function formatUnrealizedBreakdown(breakdown: PositionBreakdown[]): string {
  if (!breakdown.length) {
    return "-";
  }

  return breakdown
    .map((entry) =>
      entry.unrealized_pl == null
        ? "-"
        : formatCurrencyValue(entry.unrealized_pl, entry.currency)
    )
    .join(" / ");
}

function profitClass(breakdown: PositionBreakdown[]): Record<string, boolean> {
  const positive = breakdown.some((entry) => entry.realized_pl > 1e-2);
  const negative = breakdown.some((entry) => entry.realized_pl < -1e-2);
  return {
    positive: positive && !negative,
    negative: negative && !positive,
    mixed: positive && negative,
  };
}

function unrealizedClass(breakdown: PositionBreakdown[]): Record<string, boolean> {
  const total = breakdown.reduce((sum, entry) => sum + (entry.unrealized_pl ?? 0), 0);
  return { positive: total > 1e-2, negative: total < -1e-2 };
}

function marketLabel(value: string): string {
  return value === "US"
    ? t("common.toggle.market.us")
    : t("common.toggle.market.jp");
}
</script>

<style scoped>
.positions-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: clamp(1.6rem, 3vw, 2.3rem);
  overflow: hidden;
}

.positions-panel::before {
  content: none;
}

.positions-panel > * {
  position: relative;
  z-index: 1;
}

.surface-group {
  display: flex;
  flex-direction: column;
  gap: clamp(1.5rem, 3vw, 2.4rem);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(199, 210, 220, 0.6);
}

.header-actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}

.ghost-button {
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: #fff;
  color: var(--text-dim);
  padding: 0.55rem 1.25rem;
  font-size: 0.85rem;
  letter-spacing: 0;
  cursor: pointer;
  transition: border-color var(--transition), color var(--transition), background var(--transition);
}

.ghost-button:hover {
  border-color: rgba(30, 156, 90, 0.24);
  color: var(--accent-strong);
  background: var(--panel-soft);
}

.quotes-meta {
  margin: 0;
  color: var(--text-faint);
  font-size: 0.85rem;
}

.split-detection { display: grid; gap: .9rem; padding: 1.15rem 1.25rem; border: 1px solid var(--divider); background: #fff; }
.split-detection__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.split-detection__header h3 { font-size: 1rem; }
.split-detection__header p { margin-top: .3rem; color: var(--text-dim); font-size: .84rem; }
.split-detection__summary, .split-detection__empty { color: var(--text-dim); font-size: .84rem; }
.split-detection__warning { color: var(--accent-warm); font-size: .82rem; }
.split-detection__error { color: var(--accent-red); font-size: .84rem; }
.split-table { border-radius: 0; }
.quantity-correction { width: 8rem; height: 36px; padding: 0 .65rem; border: 1px solid var(--divider-bold); border-radius: 6px; background: var(--panel); color: var(--text); text-align: right; font: inherit; font-variant-numeric: tabular-nums; }

.position-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(130px, 0.7fr)) minmax(280px, 1.5fr);
  gap: 0.75rem;
}

.position-kpis article {
  display: flex;
  min-height: 104px;
  flex-direction: column;
  justify-content: space-between;
  padding: 1rem 1.1rem;
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  background: #fff;
}

.position-kpis span,
.position-kpis small { color: var(--text-faint); font-size: 0.78rem; }
.position-kpis strong { font-size: 1.65rem; font-variant-numeric: tabular-nums; }
.currency-results { display: flex; gap: 1.25rem; flex-wrap: wrap; }
.currency-results strong { font-size: 1.25rem; }
.closed-section__header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }

@media (max-width: 900px) {
  .position-kpis { grid-template-columns: repeat(2, 1fr); }
}

.panel-header h2 {
  font-size: 1.3rem;
  letter-spacing: 0.5px;
  color: var(--accent);
}

.panel-header p {
  margin-top: 0.4rem;
  color: var(--text-dim);
  font-size: 0.92rem;
}

.surface {
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: var(--panel-alt);
  box-shadow: none;
  padding: clamp(1.3rem, 2.6vw, 1.8rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  min-height: 100%;
}

.positions-ledger { padding: 0; overflow: hidden; gap: 0; }
.ledger-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.15rem 1.25rem; }
.ledger-heading span { color: var(--text-faint); font-size: .78rem; }
.positions-ledger .table-scroll { border-width: 1px 0 0; border-radius: 0; }

.surface h3 {
  font-size: 1rem;
  letter-spacing: -0.01em;
  text-transform: none;
  color: var(--text);
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: none;
}

.table-scroll table {
  min-width: 520px;
}

.table-scroll thead {
  background: var(--panel-soft);
  color: var(--text-dim);
  text-transform: none;
  letter-spacing: 0;
  font-size: 0.78rem;
}

.table-scroll th,
.table-scroll td {
  padding: 0.72rem 1rem;
  border-bottom: 1px solid var(--divider);
  font-size: 0.95rem;
  color: var(--text);
}

.select-column {
  width: 2.5rem;
  text-align: center;
}

.select-column input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--accent);
  cursor: pointer;
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  white-space: nowrap;
}

.table-scroll tbody tr:hover {
  background: rgba(30, 156, 90, 0.04);
}

.position-row td {
  cursor: pointer;
}

.position-row { outline: none; transition: background var(--transition), box-shadow var(--transition); }
.position-row:focus-visible { box-shadow: inset 3px 0 var(--focus-ring); }

.position-row.selected {
  background: rgba(30, 156, 90, 0.06);
  box-shadow: inset 0 0 0 1px rgba(30, 156, 90, 0.24);
}

.symbol-cell {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.symbol-cell > div { display: grid; gap: .1rem; }
.symbol-cell strong { font-size: .94rem; letter-spacing: .01em; }
.symbol-cell small { color: var(--text-faint); font-size: .7rem; }
.market-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.market-dot--us { background: #315f78; box-shadow: 0 0 0 3px rgba(49,95,120,.12); }

.selection-details {
  display: grid;
  gap: 0.75rem;
  padding: 0.95rem 1rem;
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  background: #fff;
}

.selection-details__header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.group-summary-list {
  display: grid;
  gap: 0.55rem;
}

.group-summary-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 0.75rem;
  align-items: center;
  padding-top: 0.55rem;
  border-top: 1px solid var(--divider);
  font-size: 0.88rem;
}

.empty {
  text-align: center;
  color: var(--text-faint);
}

.positive {
  color: var(--accent-cyan);
  font-weight: 600;
}

.negative {
  color: var(--accent-red);
  font-weight: 600;
}

.mixed {
  color: var(--accent-orange, #d97706);
  font-weight: 600;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 50;
}

.modal-panel {
  width: min(900px, 100%);
  background: var(--panel);
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  box-shadow: var(--shadow-soft);
  padding: 1.5rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--accent);
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.modal-status {
  margin: 0;
  color: var(--text-dim);
  font-size: 0.9rem;
}

.modal-status.error {
  color: var(--accent-red);
}

.history-chart {
  width: 100%;
  height: 360px;
}

@media (max-width: 768px) {
  .positions-panel {
    padding: 1.3rem;
  }

  .table-scroll table {
    min-width: 520px;
  }
}

</style>
