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
                <th>{{ t("positions.table.quantity") }}</th>
                <th>{{ t("positions.table.cost") }}</th>
                <th>{{ t("positions.table.pl") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!activePositions.length">
                <td colspan="5" class="empty">{{ t("positions.emptyActive") }}</td>
              </tr>
              <tr v-for="item in activePositions" :key="`${item.symbol}-${item.market}`">
                <td>{{ item.symbol }}</td>
                <td>{{ marketLabel(item.market) }}</td>
                <td>{{ formatNumber(item.quantity) }}</td>
                <td>{{ formatCurrency(item.average_cost, item.market) }}</td>
                <td :class="profitClass(item.realized_pl)">
                  {{ formatProfit(item.realized_pl, item.market) }}
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
                <th>{{ t("positions.table.quantity") }}</th>
                <th>{{ t("positions.table.pl") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!closedPositions.length">
                <td colspan="4" class="empty">{{ t("positions.emptyClosed") }}</td>
              </tr>
              <tr v-for="item in closedPositions" :key="`${item.symbol}-${item.market}`">
                <td>{{ item.symbol }}</td>
                <td>{{ marketLabel(item.market) }}</td>
                <td>{{ formatNumber(item.quantity) }}</td>
                <td :class="profitClass(item.realized_pl)">
                  {{ formatProfit(item.realized_pl, item.market) }}
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

import type { Position } from "@/types/api";

const props = defineProps<{ positions: Position[] }>();

defineEmits<{
  (e: "refresh"): void;
}>();

const { t } = useI18n();

const activePositions = computed(() =>
  props.positions.filter((item) => Math.abs(item.quantity) > 1e-9)
);

const closedPositions = computed(() =>
  props.positions.filter((item) => Math.abs(item.quantity) <= 1e-9)
);

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function marketToCurrency(market: string): "JPY" | "USD" {
  return market === "US" ? "USD" : "JPY";
}

function formatCurrency(value: number, market: string): string {
  const currency = marketToCurrency(market);
  const locale = currency === "USD" ? "en-US" : "ja-JP";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(value);
}

function formatProfit(value: number, market: string): string {
  const formatter = new Intl.NumberFormat(market === "US" ? "en-US" : "ja-JP", {
    style: "currency",
    currency: market === "US" ? "USD" : "JPY",
  });
  return formatter.format(value);
}

function profitClass(value: number): Record<string, boolean> {
  return {
    positive: value >= 0,
    negative: value < 0,
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

</style>
