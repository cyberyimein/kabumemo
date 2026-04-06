<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-main">
        <div>
          <h1>{{ t("app.header.title") }}</h1>
          <p class="tagline">{{ t("app.header.tagline") }}</p>
        </div>
        <div class="header-summary" aria-label="overview">
          <article v-for="item in headerStats" :key="item.label" class="header-stat">
            <span class="header-stat__label">{{ item.label }}</span>
            <strong class="header-stat__value">{{ item.value }}</strong>
          </article>
        </div>
        <section class="header-goal" :aria-label="t('app.goal.title')">
          <div class="header-goal__meta">
            <div>
              <p class="header-goal__eyebrow">{{ t("app.goal.title") }}</p>
              <h2 class="header-goal__value">{{ headerGoal.currentLabel }}</h2>
            </div>
            <div class="header-goal__stats">
              <span>{{ t("app.goal.target", { amount: headerGoal.targetLabel }) }}</span>
              <span v-if="headerGoal.rateLabel">{{ t("app.goal.rate", { rate: headerGoal.rateLabel }) }}</span>
              <strong>{{ t("app.goal.progress", { percent: headerGoal.percentLabel }) }}</strong>
            </div>
          </div>
          <div
            class="header-goal__track"
            role="progressbar"
            :aria-valuemin="0"
            :aria-valuemax="100"
            :aria-valuenow="headerGoal.percentValue"
          >
            <div class="header-goal__fill" :style="{ width: `${headerGoal.percentValue}%` }"></div>
          </div>
          <p class="header-goal__caption">{{ headerGoal.caption }}</p>
        </section>
      </div>
      <div class="header-controls">
        <div class="status-chip" :class="healthStatus.className">
          <span class="status-dot"></span>
          <span>{{ healthStatus.label }}</span>
        </div>
        <transition name="notification-pop">
          <div
            v-if="notification"
            class="notification toast-inline"
            :class="notification.type"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <strong>{{ t(`app.notifications.${notification.type}`) }}：</strong>
            <span>{{ notification.message }}</span>
          </div>
        </transition>
        <div
          class="language-toggle"
          role="group"
          :aria-label="t('app.language.label')"
        >
          <button
            v-for="item in localeOptions"
            :key="item.value"
            type="button"
            class="language-chip"
            :class="{ 'is-active': selectedLocale === item.value }"
            :aria-pressed="selectedLocale === item.value"
            @click="changeLocale(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </header>

    <section v-if="loading" class="loading-state">
      <div class="spinner" aria-hidden="true"></div>
      <p>{{ t("app.loading") }}</p>
    </section>

    <template v-else>
      <TabNav v-model="currentTab" :tabs="tabOptions" :aria-label="t('app.navLabel')" />

      <TransactionsTab
        v-if="currentTab === 'transactions'"
        :transactions="state.transactions"
        :funding-groups="state.fundingGroups"
        @create="handleCreateTransaction"
        @update="handleUpdateTransaction"
        @delete="handleDeleteTransaction"
        @refresh="handleRefreshTransactions"
        @notify="handleNotify"
      />

      <PositionsTab
        v-else-if="currentTab === 'positions'"
        :positions="state.positions"
        :quotes="state.quotes"
        @refresh="handleRefreshPositions"
        @refresh-quotes="handleRefreshQuotes"
      />

      <FundsTab
        v-else-if="currentTab === 'funds'"
        :funding-groups="state.fundingGroups"
        :funds="state.fundSnapshots.funds"
        :aggregated="state.fundSnapshots.aggregated"
        :capital-adjustments="state.capitalAdjustments"
        :stock-splits="state.stockSplits"
        :fx-exchanges="state.fxExchanges"
        :transactions="state.transactions"
        @create="handleCreateFundingGroup"
        @delete="handleDeleteFundingGroup"
        @refresh="handleRefreshFunds"
        @add-capital="handleAddCapital"
        @add-stock-split="handleAddStockSplit"
        @delete-stock-split="handleDeleteStockSplit"
        @add-fx="handleAddFxExchange"
        @delete-fx="handleDeleteFxExchange"
      />

      <ImportTab
        v-else-if="currentTab === 'import'"
        :funding-groups="state.fundingGroups"
        @imported="handleImportedTransactions"
        @notify="handleNotify"
      />

      <AnnualTaxTab
        v-else
        :pending-transactions="pendingTaxTransactions"
        :funding-groups="state.fundingGroups"
        @changed="handleAnnualTaxChanged"
        @notify="handleNotify"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import FundsTab from "@/components/FundsTab.vue";
import ImportTab from "@/components/ImportTab.vue";
import AnnualTaxTab from "@/components/AnnualTaxTab.vue";
import PositionsTab from "@/components/PositionsTab.vue";
import TabNav from "@/components/TabNav.vue";
import TransactionsTab from "@/components/TransactionsTab.vue";
import {
  ApiError,
  addFundingCapital,
  createFxExchange,
  createFundingGroup,
  createStockSplit,
  createTransaction,
  deleteFxExchange,
  deleteFundingGroup,
  deleteStockSplit,
  deleteTransaction,
  getAnnualTaxSettlements,
  getCapitalAdjustments,
  getFxExchanges,
  getFunds,
  getFundingGroups,
  getHealth,
  getPositions,
  getUsdJpyRate,
  getQuotes,
  getStockSplits,
  refreshQuotes,
  getTransactions,
  updateTransaction,
} from "@/services/api";
import { SUPPORTED_LOCALES, setLocale } from "@/i18n";
import type { LocaleCode } from "@/i18n";
import type {
  AggregatedFundSnapshot,
  AnnualTaxSettlement,
  FundingCapitalAdjustment,
  FundingCapitalAdjustmentRequest,
  FxExchangeCreate,
  FxExchangeRecord,
  FundSnapshot,
  FundingGroup,
  HealthResponse,
  Position,
  QuoteSnapshot,
  StockSplit,
  StockSplitPayload,
  Transaction,
  TransactionCreate,
  TransactionUpdate,
} from "@/types/api";

type TabId = "transactions" | "positions" | "funds" | "import" | "tax";

type TransactionCreatePayload = {
  transaction: TransactionCreate;
};

type TransactionUpdateEvent = {
  id: string;
  data: TransactionUpdate;
  onDone: (success: boolean) => void;
};

type CapitalAdditionEvent = {
  data: FundingCapitalAdjustmentRequest;
  onDone: (success: boolean) => void;
};

type StockSplitEvent = {
  data: StockSplitPayload;
  onDone: (success: boolean) => void;
};

const { t, locale } = useI18n();

const localeOptions = SUPPORTED_LOCALES;
const selectedLocale = computed(() => locale.value as LocaleCode);

function changeLocale(value: LocaleCode) {
  if (selectedLocale.value === value) {
    return;
  }
  setLocale(value);
  locale.value = value;
}

const state = reactive({
  transactions: [] as Transaction[],
  positions: [] as Position[],
  fundSnapshots: {
    funds: [] as FundSnapshot[],
    aggregated: [] as AggregatedFundSnapshot[],
  },
  fundingGroups: [] as FundingGroup[],
  capitalAdjustments: [] as FundingCapitalAdjustment[],
  stockSplits: [] as StockSplit[],
  fxExchanges: [] as FxExchangeRecord[],
  annualTaxSettlements: [] as AnnualTaxSettlement[],
  quotes: { as_of: "", records: [] } as QuoteSnapshot,
});

const currentTab = ref<TabId>("transactions");
const loading = ref(true);
const USD_GOAL_TARGET = 100000;
const usdJpyRate = ref<number | null>(null);
const notification = ref<{
  type: "success" | "error" | "info";
  message: string;
} | null>(null);
const health = ref<HealthResponse | null>(null);

const settledTaxYears = computed(() => new Set(state.annualTaxSettlements.map((item) => item.year)));

function tradeYearOf(transaction: Transaction): number | null {
  const raw = transaction.trade_date;
  if (!raw) {
    return null;
  }
  const year = Number.parseInt(String(raw).slice(0, 4), 10);
  return Number.isFinite(year) ? year : null;
}

const pendingTaxTransactions = computed(() =>
  state.transactions.filter((tx: Transaction) => {
    if (tx.taxed !== "N" || tx.quantity >= 0) {
      return false;
    }
    const tradeYear = tradeYearOf(tx);
    return tradeYear === null || !settledTaxYears.value.has(tradeYear);
  })
);

const tabOptions = computed(() => [
  { id: "transactions", label: t("tabs.transactions"), badge: state.transactions.length },
  { id: "positions", label: t("tabs.positions"), badge: state.positions.length },
  { id: "funds", label: t("tabs.funds"), badge: state.fundingGroups.length },
  { id: "import", label: t("tabs.import"), badge: 0 },
  { id: "tax", label: t("tabs.tax"), badge: pendingTaxTransactions.value.length },
]);

const healthStatus = computed(() => {
  if (!health.value) {
    return { label: t("app.status.unknown"), className: "unknown" };
  }
  return health.value.status === "ok"
    ? { label: t("app.status.online"), className: "healthy" }
    : { label: t("app.status.offline"), className: "error" };
});

const headerStats = computed(() => {
  const activePositions = state.positions.filter((position) =>
    position.breakdown.some((item) => item.quantity > 0)
  ).length;
  const fundTotal = state.fundSnapshots.aggregated.length
    ? state.fundSnapshots.aggregated
        .map((row) => `${row.currency} ${new Intl.NumberFormat("en-US", { maximumFractionDigits: row.currency === "JPY" ? 0 : 2 }).format(row.current_total)}`)
        .join(" / ")
    : t("app.overview.zeroState");

  return [
    { label: t("app.overview.cards.trades"), value: String(state.transactions.length) },
    { label: t("app.overview.cards.positions"), value: String(activePositions) },
    { label: t("app.overview.cards.tax"), value: String(pendingTaxTransactions.value.length) },
    { label: t("app.overview.chartEyebrow"), value: fundTotal },
  ];
});

const headerGoal = computed(() => {
  const usdRow = state.fundSnapshots.aggregated.find((row) => row.currency === "USD");
  const jpyRow = state.fundSnapshots.aggregated.find((row) => row.currency === "JPY");
  const currentValue =
    (usdRow?.current_total ?? 0) +
    (usdJpyRate.value && usdJpyRate.value > 0 ? (jpyRow?.current_total ?? 0) / usdJpyRate.value : 0);
  const percentRaw = USD_GOAL_TARGET > 0 ? (currentValue / USD_GOAL_TARGET) * 100 : 0;
  const percentValue = Math.max(0, Math.min(100, Math.round(percentRaw * 10) / 10));
  const rateLabel = usdJpyRate.value
    ? new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(usdJpyRate.value)
    : null;

  return {
    currentLabel: formatUsdCurrency(currentValue),
    targetLabel: formatUsdCurrency(USD_GOAL_TARGET),
    rateLabel,
    percentLabel: new Intl.NumberFormat(locale.value, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(percentValue),
    percentValue,
    caption: rateLabel
      ? t("app.goal.captionLive")
      : t("app.goal.captionFallback"),
  };
});

onMounted(async () => {
  await Promise.all([refreshAllData(), loadHealth(), loadUsdJpyRate()]);
});

async function loadUsdJpyRate() {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return;
  }

  try {
    usdJpyRate.value = await getUsdJpyRate();
  } catch {
    usdJpyRate.value = null;
  }
}

async function refreshAllData(showToast = false) {
  try {
    loading.value = true;
    const results = await Promise.allSettled([
      getFundingGroups(),
      getTransactions(),
      getPositions(),
      getFunds(),
      getCapitalAdjustments(),
      getStockSplits(),
      getFxExchanges(),
      getAnnualTaxSettlements(),
      getQuotes(),
    ]);

    const errors: string[] = [];

    const [
      groupsResult,
      transactionsResult,
      positionsResult,
      fundsResult,
      capitalResult,
      stockSplitsResult,
      fxResult,
      annualTaxResult,
      quotesResult,
    ] = results;

    if (groupsResult.status === "fulfilled") {
      state.fundingGroups = groupsResult.value;
    } else {
      errors.push(asErrorMessage(groupsResult.reason));
    }

    if (transactionsResult.status === "fulfilled") {
      state.transactions = transactionsResult.value;
    } else {
      errors.push(asErrorMessage(transactionsResult.reason));
    }

    if (positionsResult.status === "fulfilled") {
      state.positions = positionsResult.value;
    } else {
      errors.push(asErrorMessage(positionsResult.reason));
    }

    if (fundsResult.status === "fulfilled") {
      state.fundSnapshots.funds = fundsResult.value.funds;
      state.fundSnapshots.aggregated = fundsResult.value.aggregated;
    } else {
      errors.push(asErrorMessage(fundsResult.reason));
    }

    if (capitalResult.status === "fulfilled") {
      state.capitalAdjustments = capitalResult.value;
    } else {
      errors.push(asErrorMessage(capitalResult.reason));
    }

    if (stockSplitsResult.status === "fulfilled") {
      state.stockSplits = stockSplitsResult.value;
    } else {
      errors.push(asErrorMessage(stockSplitsResult.reason));
    }

    if (fxResult.status === "fulfilled") {
      state.fxExchanges = fxResult.value;
    } else {
      errors.push(asErrorMessage(fxResult.reason));
    }

    if (annualTaxResult.status === "fulfilled") {
      state.annualTaxSettlements = annualTaxResult.value;
    } else {
      errors.push(asErrorMessage(annualTaxResult.reason));
    }

    if (quotesResult.status === "fulfilled") {
      state.quotes = quotesResult.value;
    } else {
      errors.push(asErrorMessage(quotesResult.reason));
    }

    if (errors.length) {
      showNotification("error", errors[0]);
    } else if (showToast) {
      showNotification("success", t("app.toasts.dataRefreshed"));
    }
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadHealth() {
  try {
    health.value = await getHealth();
  } catch (error: unknown) {
    showNotification("info", t("app.toasts.healthUnavailable"));
  }
}

function showNotification(type: "success" | "error" | "info", message: string) {
  notification.value = { type, message };
  if (type !== "error") {
    window.setTimeout(() => {
      if (notification.value?.message === message) {
        notification.value = null;
      }
    }, 4000);
  }
}

function asErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  } else if (error instanceof Error) {
    return error.message;
  }
  return "发生未知错误";
}

function formatUsdCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

async function handleCreateTransaction(payload: TransactionCreatePayload) {
  try {
    await createTransaction(payload.transaction);
    showNotification("success", t("transactions.toasts.created"));
    await Promise.all([
      reloadTransactions(),
      reloadPositions(),
      reloadFunds(),
    ]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleUpdateTransaction(payload: TransactionUpdateEvent) {
  try {
    await updateTransaction(payload.id, payload.data);
    payload.onDone(true);
    showNotification("success", t("transactions.toasts.updated"));
  } catch (error: unknown) {
    payload.onDone(false);
    showNotification("error", asErrorMessage(error));
    return;
  }

  try {
    await Promise.all([
      reloadTransactions(),
      reloadPositions(),
      reloadFunds(),
    ]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteTransaction(id: string) {
  try {
    await deleteTransaction(id);
    showNotification("success", t("transactions.toasts.deleted"));
    await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleRefreshTransactions() {
  await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds()]);
  showNotification("success", t("transactions.toasts.refreshed"));
}

function handleNotify(payload: { type: "success" | "error" | "info"; message: string }) {
  showNotification(payload.type, payload.message);
}

async function handleRefreshPositions() {
  await reloadPositions();
  showNotification("success", t("positions.toasts.refreshed"));
}

async function handleRefreshQuotes() {
  try {
    await refreshQuotes();
    await Promise.all([reloadQuotes(), reloadPositions()]);
    showNotification("success", t("positions.toasts.quotesRefreshed"));
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleRefreshFunds() {
  await Promise.all([
    reloadFundingGroups(),
    reloadTransactions(),
    reloadFunds(),
    reloadCapitalAdjustments(),
    reloadStockSplits(),
    reloadFxExchanges(),
  ]);
  showNotification("success", t("funds.toasts.refreshed"));
}

async function handleCreateFundingGroup(payload: FundingGroup) {
  try {
    await createFundingGroup(payload);
    showNotification("success", t("funds.toasts.created"));
    await Promise.all([reloadFundingGroups(), reloadFunds(), reloadCapitalAdjustments()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteFundingGroup(name: string) {
  try {
    await deleteFundingGroup(name);
    showNotification("success", t("funds.toasts.deleted"));
    await Promise.all([reloadFundingGroups(), reloadFunds(), reloadCapitalAdjustments()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleAddCapital(event: CapitalAdditionEvent) {
  try {
    await addFundingCapital(event.data);
    event.onDone(true);
    showNotification("success", t("funds.toasts.capitalAdded"));
    await Promise.all([
      reloadFundingGroups(),
      reloadFunds(),
      reloadCapitalAdjustments(),
      reloadFxExchanges(),
    ]);
  } catch (error: unknown) {
    event.onDone(false);
    showNotification("error", asErrorMessage(error));
  }
}

async function handleAddStockSplit(event: StockSplitEvent) {
  try {
    await createStockSplit(event.data);
    event.onDone(true);
    showNotification("success", t("funds.stockSplits.toasts.created"));
    await Promise.all([
      reloadStockSplits(),
      reloadPositions(),
      reloadFunds(),
    ]);
  } catch (error: unknown) {
    event.onDone(false);
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteStockSplit(id: string) {
  try {
    await deleteStockSplit(id);
    showNotification("success", t("funds.stockSplits.toasts.deleted"));
    await Promise.all([
      reloadStockSplits(),
      reloadPositions(),
      reloadFunds(),
    ]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleAddFxExchange(payload: FxExchangeCreate) {
  try {
    await createFxExchange(payload);
    showNotification("success", t("funds.fx.toasts.created"));
    await Promise.all([reloadFxExchanges(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteFxExchange(id: string) {
  try {
    await deleteFxExchange(id);
    showNotification("success", t("funds.fx.toasts.deleted"));
    await Promise.all([reloadFxExchanges(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleImportedTransactions() {
  try {
    await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleAnnualTaxChanged() {
  try {
    await Promise.all([reloadFunds(), reloadAnnualTaxSettlements()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function reloadTransactions() {
  state.transactions = await getTransactions();
}

async function reloadPositions() {
  state.positions = await getPositions();
}

async function reloadQuotes() {
  state.quotes = await getQuotes();
}

async function reloadFunds() {
  const snapshot = await getFunds();
  state.fundSnapshots.funds = snapshot.funds;
  state.fundSnapshots.aggregated = snapshot.aggregated;
}

async function reloadFundingGroups() {
  state.fundingGroups = await getFundingGroups();
}

async function reloadCapitalAdjustments() {
  state.capitalAdjustments = await getCapitalAdjustments();
}

async function reloadStockSplits() {
  state.stockSplits = await getStockSplits();
}

async function reloadFxExchanges() {
  state.fxExchanges = await getFxExchanges();
}

async function reloadAnnualTaxSettlements() {
  state.annualTaxSettlements = await getAnnualTaxSettlements();
}
</script>

<style scoped>
.app-shell {
  gap: clamp(1.5rem, 3vw, 2.5rem);
}

.app-header {
  flex-wrap: wrap;
  gap: 1rem;
}

.tagline {
  color: var(--text-dim);
}

.header-goal {
  display: grid;
  gap: 0.7rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: var(--panel-alt);
}

.header-goal__meta {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.header-goal__eyebrow {
  font-size: 0.76rem;
  color: var(--text-faint);
}

.header-goal__value {
  margin-top: 0.2rem;
  font-size: clamp(1.2rem, 2vw, 1.6rem);
  line-height: 1.05;
  letter-spacing: -0.04em;
  color: var(--text);
}

.header-goal__stats {
  display: grid;
  gap: 0.2rem;
  text-align: right;
  color: var(--text-dim);
  font-size: 0.82rem;
}

.header-goal__stats strong {
  color: var(--accent-strong);
  font-size: 0.98rem;
}

.header-goal__track {
  width: 100%;
  height: 0.8rem;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 55%, #ffffff);
  border: 1px solid color-mix(in srgb, var(--accent) 12%, var(--divider));
}

.header-goal__fill {
  height: 100%;
  min-width: 0;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent) 0%, var(--accent-cyan) 100%);
  transition: width var(--transition);
}

.header-goal__caption {
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--text-dim);
}

.notification strong {
  min-width: 2.5rem;
}

.loading-state p {
  margin: 0;
  color: var(--text-dim);
}

@media (max-width: 640px) {
  .header-goal__stats {
    width: 100%;
    text-align: left;
  }
}
</style>
