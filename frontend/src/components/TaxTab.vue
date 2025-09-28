<template>
  <section class="tax-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("tax.title") }}</h2>
        <p>{{ t("tax.description") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="$emit('refresh')">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

    <div class="panel-grid">
      <div class="surface">
        <h3>{{ t("tax.pendingTitle", { count: pendingTransactions.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("tax.table.date") }}</th>
                <th>{{ t("tax.table.symbol") }}</th>
                <th>{{ t("tax.table.quantity") }}</th>
                <th>{{ t("tax.table.fundingGroup") }}</th>
                <th>{{ t("tax.table.amount") }}</th>
                <th>{{ t("tax.table.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!pendingTransactions.length">
                <td colspan="6" class="empty">{{ t("tax.empty") }}</td>
              </tr>
              <tr v-for="item in sortedPending" :key="item.id">
                <td>{{ item.trade_date }}</td>
                <td>{{ item.symbol }}</td>
                <td class="negative">{{ formatNumber(item.quantity) }}</td>
                <td>{{ item.funding_group }}</td>
                <td>
                  {{ formatCurrency(item.gross_amount, item.cash_currency) }}
                </td>
                <td>
                  <button
                    type="button"
                    class="select-btn"
                    :disabled="form.transaction_id === item.id"
                    @click="selectTransaction(item.id)"
                  >
                    {{
                      form.transaction_id === item.id
                        ? t("tax.selected")
                        : t("tax.select")
                    }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <form class="surface" @submit.prevent="handleSubmit">
        <h3>{{ formTitle }}</h3>

        <p v-if="!form.transaction_id && !isEditing" class="hint">
          {{ t("tax.hint") }}
        </p>
        <p v-else-if="isEditing" class="hint editing">
          {{
            t("tax.editingHint", {
              date: selectedSettlement ? formatDate(selectedSettlement.recorded_at) : ""
            })
          }}
        </p>

        <template v-if="form.transaction_id || isEditing">
          <div class="inline-info">
            <span>
              {{
                t("tax.inline.symbol", {
                  value: selectedTransaction?.symbol ?? ""
                })
              }}
            </span>
            <span>
              {{
                t("tax.inline.fundingGroup", {
                  value: selectedTransaction?.funding_group ?? ""
                })
              }}
            </span>
            <span>
              {{
                t("tax.inline.amount", {
                  value: formatCurrency(
                    selectedTransaction?.gross_amount ?? 0,
                    selectedTransaction?.cash_currency ?? "JPY"
                  )
                })
              }}
            </span>
          </div>

          <div class="form-grid">
            <label>
              <span>{{ amountLabel }}</span>
              <input
                v-model.number="form.amount"
                type="number"
                step="0.01"
                min="0"
                required
              />
            </label>
            <label>
              <span>{{ t("tax.fields.currency") }}</span>
              <BaseSelect
                v-model="form.currency"
                :options="currencyOptions"
                :disabled="isEditing"
              />
            </label>
            <label v-if="form.currency === 'USD'">
              <span>{{ t("tax.fields.rate") }}</span>
              <input
                v-model.number="form.exchange_rate"
                type="number"
                step="0.0001"
                min="0"
                required
              />
            </label>
            <label v-if="form.currency === 'USD'" class="full">
              <span>{{ t("tax.fields.converted") }}</span>
              <input
                v-model.number="form.converted_usd"
                type="number"
                step="0.01"
                min="0"
                :placeholder="t('tax.convertedHint')"
              />
              <span class="conversion-hint" aria-live="polite">
                {{ t("tax.autoConversion", { auto: autoConvertedUsdDisplay }) }} ·
                {{ t("tax.submitAmount", { value: convertedUsdDisplay }) }}
              </span>
            </label>
            <label class="full">
              <span>{{ t("common.labels.memo") }}</span>
              <input
                :value="selectedTransaction?.memo || ''"
                type="text"
                disabled
              />
            </label>
          </div>
          <div class="form-actions">
            <button
              v-if="isEditing"
              type="button"
              class="ghost-btn"
              @click="cancelEditing"
            >
              {{ t("tax.cancelEdit") }}
            </button>
            <button type="submit" class="primary-btn" :disabled="pending">
              {{ submitLabel }}
            </button>
          </div>
        </template>
      </form>

      <div class="surface">
        <h3>{{ t("tax.historyTitle", { count: settlements.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("tax.historyTable.recordedAt") }}</th>
                <th>{{ t("tax.historyTable.tradeDate") }}</th>
                <th>{{ t("tax.historyTable.symbol") }}</th>
                <th>{{ t("tax.historyTable.amount") }}</th>
                <th>{{ t("tax.historyTable.converted") }}</th>
                <th>{{ t("tax.historyTable.fundingGroup") }}</th>
                <th>{{ t("tax.historyTable.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!settlementRows.length">
                <td colspan="7" class="empty">{{ t("tax.historyEmpty") }}</td>
              </tr>
              <tr
                v-for="row in settlementRows"
                :key="row.record.id"
                :class="{ active: editingSettlementId === row.record.id }"
              >
                <td>{{ formatDate(row.record.recorded_at) }}</td>
                <td>{{ row.transaction?.trade_date ?? "—" }}</td>
                <td>{{ row.transaction?.symbol ?? row.record.transaction_id }}</td>
                <td>{{ formatCurrency(row.record.amount, row.record.currency) }}</td>
                <td>{{ formatCurrency(row.record.jpy_equivalent, "JPY") }}</td>
                <td>{{ row.record.funding_group }}</td>
                <td class="actions-cell">
                  <button
                    type="button"
                    class="select-btn"
                    :disabled="pending || editingSettlementId === row.record.id"
                    @click="selectSettlement(row.record.id)"
                  >
                    {{
                      editingSettlementId === row.record.id
                        ? t("tax.selected")
                        : t("common.actions.edit")
                    }}
                  </button>
                  <button
                    type="button"
                    class="select-btn danger"
                    :disabled="pending"
                    @click="handleRemoveSettlement(row.record.id)"
                  >
                    {{ t("common.actions.delete") }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type {
  Currency,
  FundingGroup,
  TaxSettlementRecord,
  TaxSettlementRequest,
  TaxSettlementUpdate,
  Transaction,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";

type TaxSettlementUpdateEvent = {
  id: string;
  data: TaxSettlementUpdate;
};

const props = defineProps<{
  pendingTransactions: Transaction[];
  transactions: Transaction[];
  settlements: TaxSettlementRecord[];
  fundingGroups: FundingGroup[];
}>();

const emit = defineEmits<{
  (e: "settle", payload: TaxSettlementRequest): void;
  (e: "update", payload: TaxSettlementUpdateEvent): void;
  (e: "remove", settlementId: string): void;
  (e: "refresh"): void;
}>();

const pending = ref(false);
const editingSettlementId = ref<string | null>(null);

const { t } = useI18n();

type TaxFormState = {
  transaction_id: string;
  funding_group: string;
  amount: number;
  currency: Currency;
  exchange_rate: number | null;
  converted_usd: number | null;
};

const createDefaultFormState = (): TaxFormState => ({
  transaction_id: "",
  funding_group: "",
  amount: 0,
  currency: "JPY",
  exchange_rate: null,
  converted_usd: null,
});

const form = reactive<TaxFormState>(createDefaultFormState());

const isEditing = computed(() => editingSettlementId.value !== null);

const formTitle = computed(() =>
  isEditing.value ? t("tax.formTitleEdit") : t("tax.formTitle")
);

const submitLabel = computed(() =>
  isEditing.value ? t("tax.submitUpdate") : t("tax.submit")
);

const transactionLookup = computed(() => {
  const map = new Map<string, Transaction>();
  props.transactions.forEach((item) => map.set(item.id, item));
  return map;
});

const fundingGroupLookup = computed(() => {
  const map = new Map<string, FundingGroup>();
  props.fundingGroups.forEach((group) => map.set(group.name, group));
  return map;
});

const selectedTransaction = computed(() =>
  form.transaction_id ? transactionLookup.value.get(form.transaction_id) ?? null : null
);

const selectedSettlement = computed(() =>
  editingSettlementId.value
    ? props.settlements.find((item) => item.id === editingSettlementId.value) ?? null
    : null
);

const amountLabel = computed(() =>
  form.currency === "USD"
    ? t("tax.fields.amountJPY")
    : t("tax.fields.amount")
);

const sortedPending = computed(() =>
  [...props.pendingTransactions].sort((a, b) =>
    a.trade_date < b.trade_date ? 1 : -1
  )
);

const sortedSettlements = computed(() =>
  [...props.settlements].sort((a, b) =>
    a.recorded_at < b.recorded_at ? 1 : -1
  )
);

const settlementRows = computed(() =>
  sortedSettlements.value.map((record) => ({
    record,
    transaction: transactionLookup.value.get(record.transaction_id) ?? null,
  }))
);

const currencyOptions = computed(() => [
  {
    label: t("common.currencies.JPY"),
    value: "JPY" as Currency,
  },
  {
    label: t("common.currencies.USD"),
    value: "USD" as Currency,
  },
]);

const autoConvertedUsdAmount = computed(() => {
  if (form.currency !== "USD") {
    return null;
  }
  const yen = Number(form.amount);
  const rate = Number(form.exchange_rate);
  if (!yen || !rate || rate <= 0) {
    return null;
  }
  return Number((yen / rate).toFixed(2));
});

const manualUsdAmount = computed(() => {
  if (form.currency !== "USD") {
    return null;
  }
  const override = form.converted_usd;
  if (override == null) {
    return null;
  }
  const numeric = Number(override);
  if (Number.isNaN(numeric) || numeric <= 0) {
    return null;
  }
  return Number(numeric.toFixed(2));
});

const effectiveUsdAmount = computed(() => {
  if (form.currency !== "USD") {
    return null;
  }
  return manualUsdAmount.value ?? autoConvertedUsdAmount.value;
});

const convertedUsdDisplay = computed(() => {
  if (form.currency !== "USD" || effectiveUsdAmount.value === null) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(effectiveUsdAmount.value);
});

const autoConvertedUsdDisplay = computed(() => {
  if (form.currency !== "USD" || autoConvertedUsdAmount.value === null) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(autoConvertedUsdAmount.value);
});

watch(
  () => form.amount,
  (value) => {
    if (value == null || Number.isNaN(value) || value < 0) {
      form.amount = 0;
    }
  }
);

watch(
  () => form.exchange_rate,
  (value) => {
    if (value == null) {
      return;
    }
    const numeric = Number(value);
    if (Number.isNaN(numeric) || numeric <= 0) {
      form.exchange_rate = null;
    }
  }
);

watch(
  () => form.converted_usd,
  (value) => {
    if (value == null) {
      return;
    }
    const numeric = Number(value);
    if (Number.isNaN(numeric) || numeric < 0) {
      form.converted_usd = 0;
    }
  }
);

watch(
  () => form.currency,
  (currency) => {
    if (currency !== "USD") {
      form.exchange_rate = null;
      form.converted_usd = null;
    }
  }
);

watch(selectedTransaction, (tx) => {
  if (!tx) {
    return;
  }
  form.funding_group = tx.funding_group;
  if (isEditing.value) {
    return;
  }
  const group = fundingGroupLookup.value.get(tx.funding_group);
  form.currency = group?.currency ?? "JPY";
  if (form.currency !== "USD") {
    form.exchange_rate = null;
    form.converted_usd = null;
  }
  form.amount = 0;
});

function resetForm() {
  Object.assign(form, createDefaultFormState());
  editingSettlementId.value = null;
}

function selectTransaction(id: string) {
  if (editingSettlementId.value) {
    resetForm();
  }
  const transaction = props.pendingTransactions.find((item) => item.id === id);
  form.transaction_id = id;
  form.funding_group = transaction?.funding_group ?? "";
  if (transaction) {
    const group = fundingGroupLookup.value.get(transaction.funding_group);
    form.currency = group?.currency ?? "JPY";
  }
}

function selectSettlement(id: string) {
  const record = props.settlements.find((item) => item.id === id);
  if (!record) {
    return;
  }
  editingSettlementId.value = record.id;
  form.transaction_id = record.transaction_id;
  form.funding_group = record.funding_group;
  form.currency = record.currency;
  form.exchange_rate = record.exchange_rate ?? null;
  if (record.currency === "USD") {
    form.amount = record.jpy_equivalent;
    form.converted_usd = record.amount;
  } else {
    form.amount = record.amount;
    form.converted_usd = null;
  }
}

function cancelEditing() {
  resetForm();
}

function handleRemoveSettlement(id: string) {
  emit("remove", id);
  if (editingSettlementId.value === id) {
    resetForm();
  }
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat(currency === "USD" ? "en-US" : "ja-JP", {
    style: "currency",
    currency,
  }).format(value);
}

function formatDate(value: string): string {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" }).format(dt);
}

function normalizedAmount(): number | null {
  if (form.currency === "USD") {
    const usdAmount = effectiveUsdAmount.value;
    if (usdAmount == null || usdAmount <= 0) {
      return null;
    }
    return usdAmount;
  }
  const value = Number(form.amount);
  if (Number.isNaN(value) || value <= 0) {
    return null;
  }
  return value;
}

async function handleSubmit() {
  if (!form.transaction_id) {
    return;
  }
  const amount = normalizedAmount();
  if (amount === null) {
    return;
  }
  if (form.currency === "USD" && (form.exchange_rate == null || form.exchange_rate <= 0)) {
    return;
  }
  const groupCurrency = fundingGroupLookup.value.get(form.funding_group)?.currency;
  if (groupCurrency && groupCurrency !== form.currency) {
    return;
  }
  pending.value = true;
  try {
    if (isEditing.value && editingSettlementId.value) {
      const patch: TaxSettlementUpdate = {
        amount,
        funding_group: form.funding_group,
        exchange_rate:
          form.currency === "USD"
            ? form.exchange_rate ?? undefined
            : undefined,
      };
      emit("update", { id: editingSettlementId.value, data: patch });
    } else {
      const payload: TaxSettlementRequest = {
        transaction_id: form.transaction_id,
        funding_group: form.funding_group,
        amount,
        currency: form.currency,
        exchange_rate:
          form.currency === "USD"
            ? form.exchange_rate ?? undefined
            : undefined,
      };
      emit("settle", payload);
    }
    resetForm();
  } finally {
    pending.value = false;
  }
}
</script>

<style scoped>
.tax-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  padding: clamp(1.6rem, 3vw, 2.4rem);
  overflow: hidden;
}

.tax-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(130deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.1) 60%, rgba(255, 255, 255, 0)),
    radial-gradient(circle at 0% 0%, rgba(11, 61, 145, 0.16), transparent 55%);
  mix-blend-mode: overlay;
  opacity: 0.4;
}

.tax-panel > * {
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
  font-size: 1.32rem;
  letter-spacing: 0.6px;
  color: var(--accent);
}

.panel-header p {
  margin-top: 0.4rem;
  color: var(--text-dim);
  font-size: 0.88rem;
}

.panel-grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: 1fr minmax(320px, 420px);
}

@media (max-width: 1024px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}

.surface {
  border-radius: var(--radius-lg);
  border: 1px solid var(--divider);
  background: linear-gradient(180deg, var(--panel-alt), var(--panel));
  box-shadow: var(--shadow-soft);
  padding: clamp(1.35rem, 2.6vw, 1.9rem);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.surface h3 {
  font-size: 0.95rem;
  letter-spacing: 1.05px;
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
  min-width: 720px;
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

.table-scroll tbody tr.active {
  background: rgba(15, 167, 201, 0.15);
}

.empty {
  text-align: center;
  color: var(--text-faint);
}

.primary-btn {
  align-self: flex-end;
}

.select-btn {
  border-radius: 999px;
  border: 1px solid rgba(15, 167, 201, 0.45);
  background: rgba(15, 167, 201, 0.12);
  color: var(--accent-cyan);
  padding: 0.4rem 1rem;
  font-size: 0.82rem;
  letter-spacing: 0.4px;
  cursor: pointer;
  transition: transform var(--transition), box-shadow var(--transition), opacity var(--transition);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.select-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
}

.select-btn:disabled {
  cursor: default;
  opacity: 0.65;
  transform: none;
  box-shadow: none;
}

.select-btn.danger {
  border-color: rgba(222, 49, 72, 0.45);
  background: rgba(222, 49, 72, 0.12);
  color: var(--accent-red);
}

.actions-cell {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ghost-btn {
  border-radius: 999px;
  border: 1px dashed var(--divider);
  background: transparent;
  color: var(--text-dim);
  padding: 0.45rem 1rem;
  font-size: 0.82rem;
  letter-spacing: 0.4px;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition);
}

.ghost-btn:hover {
  color: var(--accent);
  border-color: rgba(15, 167, 201, 0.6);
}


.inline-info {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.88rem;
  color: var(--text-dim);
}

.hint {
  color: var(--text-faint);
  letter-spacing: 0.5px;
}

.hint.editing {
  color: var(--accent);
}

.conversion-hint {
  font-size: 0.8rem;
  color: var(--accent);
  letter-spacing: 0.45px;
}

.negative {
  color: var(--accent-red);
  font-weight: 600;
}
</style>
