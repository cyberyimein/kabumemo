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

    <section
      v-if="notification"
      class="notification"
      :class="notification.type"
    >
      <strong>{{ t(`app.notifications.${notification.type}`) }}：</strong>
      <span>{{ notification.message }}</span>
    </section>

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
        @delete="handleDeleteTransaction"
        @refresh="handleRefreshTransactions"
      />

      <PositionsTab
        v-else-if="currentTab === 'positions'"
        :positions="state.positions"
        @refresh="handleRefreshPositions"
      />

      <FundsTab
        v-else-if="currentTab === 'funds'"
        :funding-groups="state.fundingGroups"
        :funds="state.funds"
        @create="handleCreateFundingGroup"
        @delete="handleDeleteFundingGroup"
        @refresh="handleRefreshFunds"
      />

      <TaxTab
        v-else
        :pending-transactions="pendingTaxTransactions"
        :funding-groups="state.fundingGroups"
        @settle="handleSettleTax"
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
  createFundingGroup,
  createTransaction,
  deleteFundingGroup,
  deleteTransaction,
  getFunds,
  getFundingGroups,
  getHealth,
  getPositions,
  getTransactions,
  settleTax,
} from "@/services/api";
import { SUPPORTED_LOCALES, setLocale } from "@/i18n";
import type { LocaleCode } from "@/i18n";
import type {
  FundSnapshot,
  FundingGroup,
  HealthResponse,
  Position,
  TaxSettlementRequest,
  Transaction,
  TransactionCreate,
} from "@/types/api";

type TabId = "transactions" | "positions" | "funds" | "tax";

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
  funds: [] as FundSnapshot[],
  fundingGroups: [] as FundingGroup[],
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
    const [groups, transactions, positions, funds] = await Promise.all([
      getFundingGroups(),
      getTransactions(),
      getPositions(),
      getFunds(),
    ]);
    state.fundingGroups = groups;
    state.transactions = transactions;
    state.positions = positions;
    state.funds = funds;
    if (showToast) {
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

async function handleCreateTransaction(payload: TransactionCreate) {
  try {
    await createTransaction(payload);
    showNotification("success", t("transactions.toasts.created"));
    await Promise.all([reloadTransactions(), reloadPositions(), reloadFunds()]);
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

async function handleRefreshPositions() {
  await reloadPositions();
  showNotification("success", t("positions.toasts.refreshed"));
}

async function handleRefreshFunds() {
  await Promise.all([reloadFundingGroups(), reloadFunds()]);
  showNotification("success", t("funds.toasts.refreshed"));
}

async function handleCreateFundingGroup(payload: FundingGroup) {
  try {
    await createFundingGroup(payload);
    showNotification("success", t("funds.toasts.created"));
    await Promise.all([reloadFundingGroups(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleDeleteFundingGroup(name: string) {
  try {
    await deleteFundingGroup(name);
    showNotification("success", t("funds.toasts.deleted"));
    await Promise.all([reloadFundingGroups(), reloadFunds()]);
  } catch (error: unknown) {
    showNotification("error", asErrorMessage(error));
  }
}

async function handleSettleTax(payload: TaxSettlementRequest) {
  try {
    await settleTax(payload);
    showNotification("success", t("tax.toasts.updated"));
    await Promise.all([reloadTransactions(), reloadFunds()]);
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

async function reloadFunds() {
  state.funds = await getFunds();
}

async function reloadFundingGroups() {
  state.fundingGroups = await getFundingGroups();
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
