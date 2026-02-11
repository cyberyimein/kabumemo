<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <h1>{{ t("app.header.title") }}</h1>
        <p class="tagline">{{ t("app.header.tagline") }}</p>
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
  getQuotes,
  refreshQuotes,
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
        :fx-exchanges="state.fxExchanges"
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
        :fx-exchanges="state.fxExchanges"
        :transactions="state.transactions"
        @create="handleCreateFundingGroup"
        @delete="handleDeleteFundingGroup"
        @refresh="handleRefreshFunds"
        @add-capital="handleAddCapital"
        @add-fx="handleAddFxExchange"
        @delete-fx="handleDeleteFxExchange"
      />

      <TaxTab
        v-else
        :pending-transactions="pendingTaxTransactions"
        :transactions="state.transactions"
        :settlements="state.taxSettlements"
        :funding-groups="state.fundingGroups"
        @settle="handleSettleTax"
        @update="handleUpdateTaxSettlement"
        @remove="handleDeleteTaxSettlement"
        @refresh="handleRefreshTransactions"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import FundsTab from "@/components/FundsTab.vue";
import PositionsTab from "@/components/PositionsTab.vue";
import TabNav from "@/components/TabNav.vue";
import TaxTab from "@/components/TaxTab.vue";
import TransactionsTab from "@/components/TransactionsTab.vue";
import {
  ApiError,
  addFundingCapital,
  createFxExchange,
  createFundingGroup,
  createTransaction,
  deleteFxExchange,
  deleteFundingGroup,
  deleteTaxSettlement,
  deleteTransaction,
  getCapitalAdjustments,
  getFxExchanges,
  getFunds,
  getFundingGroups,
  getHealth,
  getPositions,
  getQuotes,
  refreshQuotes,
  getTaxSettlements,
  getTransactions,
  settleTax,
  updateTaxSettlement,
  updateTransaction,
} from "@/services/api";
import { SUPPORTED_LOCALES, setLocale } from "@/i18n";
import type { LocaleCode } from "@/i18n";
import type {
  AggregatedFundSnapshot,
  Currency,
  FundingCapitalAdjustment,
  FundingCapitalAdjustmentRequest,
  FxExchangeCreate,
  FxExchangeRecord,
  FundSnapshot,
  FundingGroup,
  HealthResponse,
  Position,
  QuoteSnapshot,
  TaxSettlementRequest,
  TaxSettlementRecord,
  TaxSettlementUpdate,
  Transaction,
  TransactionCreate,
  TransactionUpdate,
} from "@/types/api";

type TabId = "transactions" | "positions" | "funds" | "tax";

type FxDraft = {
  exchange_date: string;
  from_currency: Currency;
  to_currency: Currency;
  from_amount: number;
  to_amount: number;
  rate: number;
};

type TransactionCreatePayload = {
  transaction: TransactionCreate;
  fxDraft?: FxDraft | null;
};

type TransactionUpdateEvent = {
  id: string;
  data: TransactionUpdate;
  fxDraft?: FxDraft | null;
  onDone: (success: boolean) => void;
};

type CapitalAdditionEvent = {
  data: FundingCapitalAdjustmentRequest;
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
  taxSettlements: [] as TaxSettlementRecord[],
  capitalAdjustments: [] as FundingCapitalAdjustment[],
  fxExchanges: [] as FxExchangeRecord[],
  quotes: { as_of: "", records: [] } as QuoteSnapshot,
});

const currentTab = ref<TabId>("transactions");
const loading = ref(true);
const notification = ref<{
  type: "success" | "error" | "info";
  message: string;
} | null>(null);
const health = ref<HealthResponse | null>(null);

const pendingTaxTransactions = computed(() =>
  state.transactions.filter(
    (tx: Transaction) => tx.taxed === "N" && tx.quantity < 0
  )
);

const tabOptions = computed(() => [
  { id: "transactions", label: t("tabs.transactions"), badge: state.transactions.length },
  { id: "positions", label: t("tabs.positions"), badge: state.positions.length },
  { id: "funds", label: t("tabs.funds"), badge: state.fundingGroups.length },
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

onMounted(async () => {
  await Promise.all([refreshAllData(), loadHealth()]);
});

async function refreshAllData(showToast = false) {
  try {
    loading.value = true;
    const results = await Promise.allSettled([
      getFundingGroups(),
      getTransactions(),
      getPositions(),
      getFunds(),
      getTaxSettlements(),
      getCapitalAdjustments(),
      getFxExchanges(),
      getQuotes(),
    ]);

    const errors: string[] = [];

    const [
      groupsResult,
      transactionsResult,
      positionsResult,
      fundsResult,
      settlementsResult,
      capitalResult,
      fxResult,
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

    if (settlementsResult.status === "fulfilled") {
      state.taxSettlements = settlementsResult.value;
    } else {
      errors.push(asErrorMessage(settlementsResult.reason));
    }

    if (capitalResult.status === "fulfilled") {
      state.capitalAdjustments = capitalResult.value;
    } else {
      errors.push(asErrorMessage(capitalResult.reason));
    }

    if (fxResult.status === "fulfilled") {
      state.fxExchanges = fxResult.value;
    } else {
      errors.push(asErrorMessage(fxResult.reason));
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

async function handleCreateTransaction(payload: TransactionCreatePayload) {
  try {
    const created = await createTransaction(payload.transaction);
    if (payload.fxDraft) {
      await createFxExchange({
        ...payload.fxDraft,
        transaction_id: created.id,
      });
    }
    showNotification("success", t("transactions.toasts.created"));
    await Promise.all([
      reloadTransactions(),
      reloadPositions(),
      reloadFunds(),
      reloadFxExchanges(),
    ]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleUpdateTransaction(payload: TransactionUpdateEvent) {
  try {
    await updateTransaction(payload.id, payload.data);
    const existingFx = state.fxExchanges.find((item) => item.transaction_id === payload.id);
    if (payload.fxDraft) {
      if (existingFx) {
        await deleteFxExchange(existingFx.id);
      }
      await createFxExchange({
        ...payload.fxDraft,
        transaction_id: payload.id,
      });
    } else if (existingFx) {
      await deleteFxExchange(existingFx.id);
    }
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
      reloadTaxSettlements(),
      reloadFxExchanges(),
    ]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteTransaction(id: string) {
  try {
    await deleteTransaction(id);
    showNotification("success", t("transactions.toasts.deleted"));
    await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds(), reloadTaxSettlements()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleRefreshTransactions() {
  await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds(), reloadTaxSettlements()]);
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

async function handleAddFxExchange(payload: FxExchangeCreate) {
  try {
    await createFxExchange(payload);
    showNotification("success", t("funds.fx.toasts.created"));
    await reloadFxExchanges();
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteFxExchange(id: string) {
  try {
    await deleteFxExchange(id);
    showNotification("success", t("funds.fx.toasts.deleted"));
    await reloadFxExchanges();
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleSettleTax(payload: TaxSettlementRequest) {
  try {
    await settleTax(payload);
    showNotification("success", t("tax.toasts.updated"));
    await Promise.all([reloadTransactions(), reloadFunds(), reloadTaxSettlements()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleUpdateTaxSettlement(event: {
  id: string;
  data: TaxSettlementUpdate;
}) {
  try {
    await updateTaxSettlement(event.id, event.data);
    showNotification("success", t("tax.toasts.updated"));
    await Promise.all([reloadTransactions(), reloadFunds(), reloadTaxSettlements()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteTaxSettlement(id: string) {
  try {
    await deleteTaxSettlement(id);
    showNotification("success", t("tax.toasts.deleted"));
    await Promise.all([reloadTransactions(), reloadFunds(), reloadTaxSettlements()]);
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

async function reloadTaxSettlements() {
  state.taxSettlements = await getTaxSettlements();
}

async function reloadCapitalAdjustments() {
  state.capitalAdjustments = await getCapitalAdjustments();
}

async function reloadFxExchanges() {
  state.fxExchanges = await getFxExchanges();
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

.notification strong {
  min-width: 2.5rem;
}

.loading-state p {
  margin: 0;
  color: var(--text-dim);
}
</style>
