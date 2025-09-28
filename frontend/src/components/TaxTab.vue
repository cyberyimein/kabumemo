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
        <h3>{{ t("tax.formTitle") }}</h3>

        <p v-if="!form.transaction_id" class="hint">
          {{ t("tax.hint") }}
        </p>

        <template v-else>
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
              />
            </label>
            <label v-if="form.currency === 'USD'">
              <span>{{ t("tax.fields.rate") }}</span>
              <input
                v-model.number="form.exchange_rate"
                type="number"
                step="0.0001"
                min="0"
                :placeholder="t('tax.fields.rate')"
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
                {{
                  t("tax.autoConversion", { auto: autoConvertedUsdDisplay })
                }}
                ·
                {{
                  t("tax.submitAmount", { value: convertedUsdDisplay })
                }}
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
            <button type="submit" class="primary-btn" :disabled="pending">
              {{ t("tax.submit") }}
            </button>
          </div>
        </template>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type {
  Currency,
  FundingGroup,
  TaxSettlementRequest,
  Transaction,
} from "@/types/api";
import BaseSelect from "./ui/BaseSelect.vue";

const props = defineProps<{
  pendingTransactions: Transaction[];
  fundingGroups: FundingGroup[];
}>();

const emit = defineEmits<{
  (e: "settle", payload: TaxSettlementRequest): void;
  (e: "refresh"): void;
}>();

const pending = ref(false);

const { t } = useI18n();

type TaxFormState = TaxSettlementRequest & {
  converted_usd?: number | null;
};

const form = reactive<TaxFormState>({
  transaction_id: "",
  funding_group: "",
  amount: 0,
  currency: "JPY",
  exchange_rate: undefined,
  converted_usd: undefined,
});

const amountLabel = computed(() =>
  form.currency === "USD"
    ? t("tax.fields.amountJPY")
    : t("tax.fields.amount")
);

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
  const override = Number(form.converted_usd);
  if (Number.isNaN(override) || override <= 0) {
    return null;
  }
  return Number(override.toFixed(2));
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

const sortedPending = computed(() =>
  [...props.pendingTransactions].sort((a, b) =>
    a.trade_date < b.trade_date ? 1 : -1
  )
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

const selectedTransaction = computed(() =>
  props.pendingTransactions.find((item) => item.id === form.transaction_id)
);

watch(selectedTransaction, (tx) => {
  if (!tx) {
    return;
  }
  form.funding_group = tx.funding_group;
  const group = props.fundingGroups.find(
    (item) => item.name === tx.funding_group
  );
  form.currency = group?.currency ?? "JPY";
  if (form.currency !== "USD") {
    form.exchange_rate = undefined;
  }
  form.amount = 0;
  form.converted_usd = undefined;
});

watch(
  () => form.currency,
  (currency) => {
    if (currency !== "USD") {
      form.exchange_rate = undefined;
      form.converted_usd = undefined;
    }
  }
);

watch(
  () => form.amount,
  (value) => {
    const numeric = Number(value);
    if (Number.isNaN(numeric) || numeric < 0) {
      form.amount = 0;
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

function selectTransaction(id: string) {
  form.transaction_id = id;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number, currency: string): string {
  const locale = currency === "USD" ? "en-US" : "ja-JP";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(value);
}

async function handleSubmit() {
  if (!form.transaction_id) {
    return;
  }
  if (
    form.currency === "USD" &&
    (effectiveUsdAmount.value === null || effectiveUsdAmount.value <= 0)
  ) {
    return;
  }
  pending.value = true;
  try {
    const amountYen = Number(form.amount);
    const normalizedAmount =
      form.currency === "USD" && effectiveUsdAmount.value !== null
        ? effectiveUsdAmount.value
        : amountYen;
    const payload: TaxSettlementRequest = {
      transaction_id: form.transaction_id,
      funding_group: form.funding_group,
      amount: normalizedAmount,
      currency: form.currency,
      exchange_rate:
        form.currency === "USD" ? Number(form.exchange_rate) || undefined : undefined,
    };
    emit("settle", payload);
    form.transaction_id = "";
    form.funding_group = "";
    form.amount = 0;
    form.currency = "JPY";
    form.exchange_rate = undefined;
    form.converted_usd = undefined;
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
  min-width: 580px;
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
