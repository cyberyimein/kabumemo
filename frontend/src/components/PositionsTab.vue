<template>
  <section class="positions-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("positions.title") }}</h2>
        <p>{{ t("positions.description") }}</p>
      </div>
      <div class="header-actions">
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

    <p v-if="quotes?.as_of" class="quotes-meta">
      {{ t("positions.quotesAsOf", { date: quotes.as_of }) }}
    </p>

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
      <section class="surface">
        <h3>{{ t("positions.activeTitle", { count: activePositions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="select-column"></th>
                <th>{{ t("positions.table.symbol") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.cost") }}</th>
                <th class="numeric">{{ t("positions.table.price") }}</th>
                <th class="numeric">{{ t("positions.table.unrealized") }}</th>
                <th>{{ t("common.labels.tags") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activePositions.length">
                <td colspan="7" class="empty">{{ t("positions.emptyActive") }}</td>
              </tr>
              <tr
                v-for="item in pagedActivePositions"
                :key="rowKey(item)"
                :class="['position-row', { selected: isSelected(item) }]"
                @click="handleRowClick(item)"
              >
                  <td class="select-column" @click.stop>
                    <input
                      type="radio"
                      name="position-select"
                      :checked="isSelected(item)"
                      @change="selectPosition(item)"
                    />
                  </td>
                  <td>
                    <div class="symbol-cell">
                      <span>{{ item.symbol }}</span>
                    </div>
                  </td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td class="numeric">{{ formatAverageCostBreakdown(item.breakdown) }}</td>
                  <td class="numeric">{{ formatPriceBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatUnrealizedBreakdown(item.breakdown) }}
                  </td>
                  <td>
                    <div class="inline-tags">
                      <span class="flat-tag">{{ marketLabel(item.market) }}</span>
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

      <section class="surface">
        <h3>{{ t("positions.closedTitle", { count: closedPositions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="select-column"></th>
                <th>{{ t("positions.table.symbol") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.pl") }}</th>
                <th>{{ t("common.labels.tags") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!closedPositions.length">
                <td colspan="5" class="empty">{{ t("positions.emptyClosed") }}</td>
              </tr>
              <tr
                v-for="item in pagedClosedPositions"
                :key="rowKey(item)"
                :class="['position-row', { selected: isSelected(item) }]"
                @click="handleRowClick(item)"
              >
                  <td class="select-column" @click.stop>
                    <input
                      type="radio"
                      name="position-select"
                      :checked="isSelected(item)"
                      @change="selectPosition(item)"
                    />
                  </td>
                  <td>
                    <div class="symbol-cell">
                      <span>{{ item.symbol }}</span>
                    </div>
                  </td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatProfitBreakdown(item.breakdown) }}
                  </td>
                  <td>
                    <div class="inline-tags">
                      <span class="flat-tag">{{ marketLabel(item.market) }}</span>
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
import { ApiError, getPositionHistory } from "@/services/api";
import type {
  Position,
  PositionBreakdown,
  PositionGroupBreakdown,
  PositionHistoryResponse,
  QuoteSnapshot,
} from "@/types/api";

const props = defineProps<{ positions: Position[]; quotes?: QuoteSnapshot | null }>();

defineEmits<{
  (e: "refresh"): void;
  (e: "refresh-quotes"): void;
}>();

const { t } = useI18n();

function hasOpenQuantity(position: Position): boolean {
  return position.breakdown.some((entry) => Math.abs(entry.quantity) > 1e-9);
}

const activePositions = computed(() => props.positions.filter(hasOpenQuantity));

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
  padding: 0.8rem 1rem;
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

.position-row.selected {
  background: rgba(30, 156, 90, 0.06);
  box-shadow: inset 0 0 0 1px rgba(30, 156, 90, 0.24);
}

.symbol-cell {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

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
