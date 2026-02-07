<template>
  <section class="positions-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("positions.title") }}</h2>
        <p>{{ t("positions.description") }}</p>
      </div>
      <div class="header-actions">
        <button type="button" class="ghost-button" @click="$emit('refresh-quotes')">
          {{ t("positions.actions.refreshQuotes") }}
        </button>
        <button type="button" class="refresh-button" @click="$emit('refresh')">
          {{ t("common.actions.refresh") }}
        </button>
      </div>
    </header>

    <p v-if="quotes.as_of" class="quotes-meta">
      {{ t("positions.quotesAsOf", { date: quotes.as_of }) }}
    </p>

    <div class="surface-group">
      <section class="surface">
        <h3>{{ t("positions.activeTitle", { count: activePositions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("positions.table.symbol") }}</th>
                <th>{{ t("positions.table.market") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.cost") }}</th>
                <th class="numeric">{{ t("positions.table.pl") }}</th>
                <th class="numeric">{{ t("positions.table.price") }}</th>
                <th class="numeric">{{ t("positions.table.unrealized") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activePositions.length">
                <td colspan="7" class="empty">{{ t("positions.emptyActive") }}</td>
              </tr>
              <template v-for="item in pagedActivePositions" :key="rowKey(item)">
                <tr
                  :class="['position-row', { clickable: hasGroupBreakdown(item), expanded: isExpanded(rowKey(item)) }]"
                  @click="handleRowClick(item)"
                >
                  <td>
                    <div class="symbol-cell">
                      <span
                        v-if="hasGroupBreakdown(item)"
                        :class="['chevron', { open: isExpanded(rowKey(item)) }]"
                        aria-hidden="true"
                      ></span>
                      <span>{{ item.symbol }}</span>
                    </div>
                  </td>
                  <td>{{ marketLabel(item.market) }}</td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td class="numeric">{{ formatAverageCostBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatProfitBreakdown(item.breakdown) }}
                  </td>
                  <td class="numeric">{{ formatPriceBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatUnrealizedBreakdown(item.breakdown) }}
                  </td>
                </tr>
                <tr
                  v-if="hasGroupBreakdown(item) && isExpanded(rowKey(item))"
                  :key="`${rowKey(item)}-details`"
                  class="group-row"
                >
                  <td colspan="5">
                    <div class="group-table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            <th>{{ t("positions.groupTable.group") }}</th>
                            <th class="numeric">{{ t("positions.table.quantity") }}</th>
                            <th class="numeric">{{ t("positions.table.cost") }}</th>
                            <th class="numeric">{{ t("positions.table.pl") }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="group in item.group_breakdown"
                            :key="groupKey(item, group)"
                          >
                            <td>
                              <span class="group-name">{{ group.funding_group }}</span>
                              <span class="group-currency">{{ currencySymbol(group.currency) }}</span>
                            </td>
                            <td class="numeric">{{ formatGroupQuantity(group) }}</td>
                            <td class="numeric">{{ formatCurrencyValue(group.average_cost, group.currency) }}</td>
                            <td :class="['numeric', profitClassForGroup(group)]">
                              {{ formatCurrencyValue(group.realized_pl, group.currency) }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </td>
                </tr>
              </template>
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
                <th>{{ t("positions.table.symbol") }}</th>
                <th>{{ t("positions.table.market") }}</th>
                <th class="numeric">{{ t("positions.table.quantity") }}</th>
                <th class="numeric">{{ t("positions.table.pl") }}</th>
                <th class="numeric">{{ t("positions.table.price") }}</th>
                <th class="numeric">{{ t("positions.table.unrealized") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!closedPositions.length">
                <td colspan="6" class="empty">{{ t("positions.emptyClosed") }}</td>
              </tr>
              <template v-for="item in pagedClosedPositions" :key="rowKey(item)">
                <tr
                  :class="['position-row', { clickable: hasGroupBreakdown(item), expanded: isExpanded(rowKey(item)) }]"
                  @click="handleRowClick(item)"
                >
                  <td>
                    <div class="symbol-cell">
                      <span
                        v-if="hasGroupBreakdown(item)"
                        :class="['chevron', { open: isExpanded(rowKey(item)) }]"
                        aria-hidden="true"
                      ></span>
                      <span>{{ item.symbol }}</span>
                    </div>
                  </td>
                  <td>{{ marketLabel(item.market) }}</td>
                  <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatProfitBreakdown(item.breakdown) }}
                  </td>
                  <td class="numeric">{{ formatPriceBreakdown(item.breakdown) }}</td>
                  <td :class="['numeric', profitClass(item.breakdown)]">
                    {{ formatUnrealizedBreakdown(item.breakdown) }}
                  </td>
                </tr>
                <tr
                  v-if="hasGroupBreakdown(item) && isExpanded(rowKey(item))"
                  :key="`${rowKey(item)}-details`"
                  class="group-row"
                >
                  <td colspan="4">
                    <div class="group-table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            <th>{{ t("positions.groupTable.group") }}</th>
                            <th class="numeric">{{ t("positions.table.quantity") }}</th>
                            <th class="numeric">{{ t("positions.table.cost") }}</th>
                            <th class="numeric">{{ t("positions.table.pl") }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="group in item.group_breakdown"
                            :key="groupKey(item, group)"
                          >
                            <td>
                              <span class="group-name">{{ group.funding_group }}</span>
                              <span class="group-currency">{{ currencySymbol(group.currency) }}</span>
                            </td>
                            <td class="numeric">{{ formatGroupQuantity(group) }}</td>
                            <td class="numeric">{{ formatCurrencyValue(group.average_cost, group.currency) }}</td>
                            <td :class="['numeric', profitClassForGroup(group)]">
                              {{ formatCurrencyValue(group.realized_pl, group.currency) }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </td>
                </tr>
              </template>
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
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import PaginationControls from "./ui/PaginationControls.vue";
import { usePagination } from "@/composables/usePagination";
import type { Position, PositionBreakdown, PositionGroupBreakdown } from "@/types/api";

const props = defineProps<{ positions: Position[] }>();

defineEmits<{
  (e: "refresh"): void;
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

const expandedRows = ref<Set<string>>(new Set());

function rowKey(position: Position): string {
  return `${position.symbol}-${position.market}`;
}

function hasGroupBreakdown(position: Position): boolean {
  return Array.isArray(position.group_breakdown) && position.group_breakdown.length > 0;
}

function isExpanded(key: string): boolean {
  return expandedRows.value.has(key);
}

function toggleRow(key: string): void {
  const next = new Set(expandedRows.value);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  expandedRows.value = next;
}

function handleRowClick(position: Position): void {
  if (!hasGroupBreakdown(position)) {
    return;
  }
  toggleRow(rowKey(position));
}

function groupKey(position: Position, entry: PositionGroupBreakdown): string {
  return `${rowKey(position)}-${entry.funding_group}-${entry.currency}`;
}

watch(
  () => props.positions,
  (positions) => {
    if (!expandedRows.value.size) {
      return;
    }
    const validKeys = new Set(positions.map(rowKey));
    expandedRows.value = new Set(
      [...expandedRows.value].filter((key) => validKeys.has(key))
    );
  }
);

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

  // 格式化每个币种的仓位数量，保持零仓位时也至少展示一项，便于核对双币种持仓。
  const formatted = breakdown
    .map((entry) => ({
      absolute: Math.abs(entry.quantity),
      display: `${formatNumber(entry.quantity)}${currencySymbol(entry.currency)}`,
    }))
    .filter(
      (entry, _, array) => entry.absolute > 1e-9 || array.every((item) => item.absolute <= 1e-9)
    );

  return formatted.map((entry) => entry.display).join(" / ");
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

function profitClass(breakdown: PositionBreakdown[]): Record<string, boolean> {
  const positive = breakdown.some((entry) => entry.realized_pl > 1e-2);
  const negative = breakdown.some((entry) => entry.realized_pl < -1e-2);
  return {
    positive: positive && !negative,
    negative: negative && !positive,
    mixed: positive && negative,
  };
}

function profitClassForGroup(entry: PositionGroupBreakdown): Record<string, boolean> {
  return profitClass([
    {
      currency: entry.currency,
      quantity: entry.quantity,
      average_cost: entry.average_cost,
      realized_pl: entry.realized_pl,
    } as PositionBreakdown,
  ]);
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
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.1) 55%, rgba(255, 255, 255, 0)),
    radial-gradient(circle at 100% 0%, rgba(15, 167, 201, 0.16), transparent 55%);
  mix-blend-mode: overlay;
  opacity: 0.4;
}

.positions-panel > * {
  position: relative;
  z-index: 1;
}

.surface-group {
  display: grid;
  gap: clamp(1.5rem, 3vw, 2.4rem);
}

@media (min-width: 960px) {
  .surface-group {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
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
  border-radius: 999px;
  border: 1px solid var(--divider);
  background: linear-gradient(180deg, var(--panel), var(--panel-alt));
  color: var(--text-dim);
  padding: 0.55rem 1.25rem;
  font-size: 0.85rem;
  letter-spacing: 0.6px;
  cursor: pointer;
  transition: border-color var(--transition), color var(--transition), transform var(--transition);
}

.ghost-button:hover {
  border-color: var(--accent-cyan);
  color: var(--accent-cyan);
  transform: translateY(-1px);
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
  background: linear-gradient(180deg, var(--panel-alt), var(--panel));
  box-shadow: var(--shadow-soft);
  padding: clamp(1.3rem, 2.6vw, 1.8rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  min-height: 100%;
}

.surface h3 {
  font-size: 0.95rem;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: var(--text-faint);
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.table-scroll table {
  min-width: 520px;
}

.table-scroll thead {
  background: linear-gradient(180deg, rgba(11, 61, 145, 0.08), rgba(11, 61, 145, 0));
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.65px;
  font-size: 0.78rem;
}

.table-scroll th,
.table-scroll td {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid var(--divider);
  font-size: 0.95rem;
  color: var(--text);
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  white-space: nowrap;
}

.table-scroll tbody tr:hover {
  background: rgba(15, 167, 201, 0.08);
}

.position-row.clickable td {
  cursor: pointer;
}

.position-row.expanded {
  background: rgba(15, 167, 201, 0.12);
}

.symbol-cell {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.chevron {
  display: inline-block;
  width: 0.6rem;
  height: 0.6rem;
  border: solid var(--text-dim);
  border-width: 0 0.12rem 0.12rem 0;
  transform: rotate(45deg);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.chevron.open {
  transform: rotate(135deg);
  border-color: var(--accent);
}

.group-row td {
  padding: 0;
  background: rgba(11, 61, 145, 0.04);
}

.group-table-wrapper {
  padding: 0.6rem 1.25rem 1rem;
}

.group-table-wrapper table {
  width: 100%;
  border-collapse: collapse;
}

.group-table-wrapper thead {
  color: var(--text-faint);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.group-table-wrapper th,
.group-table-wrapper td {
  border-bottom: 1px solid var(--divider);
  padding: 0.55rem 0.75rem;
  font-size: 0.88rem;
}

.group-table-wrapper tbody tr:last-child td {
  border-bottom: none;
}

.group-name {
  font-weight: 600;
  margin-right: 0.4rem;
}

.group-currency {
  color: var(--text-faint);
  font-size: 0.82rem;
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

@media (max-width: 768px) {
  .positions-panel {
    padding: 1.3rem;
  }

  .table-scroll table {
    min-width: 520px;
  }
}

</style>
