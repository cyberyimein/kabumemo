<template>
  <section class="positions-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("positions.title") }}</h2>
        <p>{{ t("positions.description") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="$emit('refresh')">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

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
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activePositions.length">
                <td colspan="5" class="empty">{{ t("positions.emptyActive") }}</td>
              </tr>
              <tr v-for="item in activePositions" :key="`${item.symbol}-${item.market}`">
                <td>{{ item.symbol }}</td>
                <td>{{ marketLabel(item.market) }}</td>
                <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                <td class="numeric">{{ formatAverageCostBreakdown(item.breakdown) }}</td>
                <td :class="['numeric', profitClass(item.breakdown)]">
                  {{ formatProfitBreakdown(item.breakdown) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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
              </tr>
            </thead>
            <tbody>
              <tr v-if="!closedPositions.length">
                <td colspan="4" class="empty">{{ t("positions.emptyClosed") }}</td>
              </tr>
              <tr v-for="item in closedPositions" :key="`${item.symbol}-${item.market}`">
                <td>{{ item.symbol }}</td>
                <td>{{ marketLabel(item.market) }}</td>
                <td class="numeric">{{ formatQuantityBreakdown(item.breakdown) }}</td>
                <td :class="['numeric', profitClass(item.breakdown)]">
                  {{ formatProfitBreakdown(item.breakdown) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { Position, PositionBreakdown } from "@/types/api";

const props = defineProps<{ positions: Position[] }>();

defineEmits<{
  (e: "refresh"): void;
}>();

const { t } = useI18n();

function hasOpenQuantity(position: Position): boolean {
  return position.breakdown.some((entry) => Math.abs(entry.quantity) > 1e-9);
}

const activePositions = computed(() => props.positions.filter(hasOpenQuantity));

const closedPositions = computed(() => props.positions.filter((item) => !hasOpenQuantity(item)));

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

</style>
