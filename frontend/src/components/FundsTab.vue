<template>
  <section class="funds-panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("funds.title") }}</h2>
        <p>{{ t("funds.description") }}</p>
      </div>
      <button type="button" class="refresh-button" @click="$emit('refresh')">
        {{ t("common.actions.refresh") }}
      </button>
    </header>

    <div class="panel-grid">
      <form class="surface" @submit.prevent="handleSubmit">
        <h3>{{ t("funds.formTitle") }}</h3>
        <div class="form-grid">
          <label>
            <span>{{ t("funds.fields.name") }}</span>
            <input
              v-model.trim="form.name"
              type="text"
              required
              :placeholder="t('funds.placeholders.name')"
            />
          </label>
          <label>
            <span>{{ t("funds.fields.currency") }}</span>
            <select v-model="form.currency" required>
              <option value="JPY">{{ t("common.currencies.JPY") }}</option>
              <option value="USD">{{ t("common.currencies.USD") }}</option>
            </select>
          </label>
          <label>
            <span>{{ t("funds.fields.initial") }}</span>
            <input
              v-model.number="form.initial_amount"
              type="number"
              step="0.01"
              min="0"
              required
            />
          </label>
          <label class="full">
            <span>{{ t("funds.fields.notes") }}</span>
            <textarea
              v-model.trim="form.notes"
              rows="2"
              :placeholder="t('funds.placeholders.notes')"
            ></textarea>
          </label>
        </div>
        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="pending">
            {{ t("funds.submit") }}
          </button>
        </div>
      </form>

      <div class="surface">
        <h3>{{ t("funds.listTitle", { count: fundingGroups.length }) }}</h3>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("funds.table.name") }}</th>
                <th>{{ t("funds.table.currency") }}</th>
                <th>{{ t("funds.table.initial") }}</th>
                <th>{{ t("funds.table.notes") }}</th>
                <th>{{ t("funds.table.actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!fundingGroups.length">
                <td colspan="5" class="empty">{{ t("funds.emptyGroups") }}</td>
              </tr>
              <tr v-for="group in fundingGroups" :key="group.name">
                <td>{{ group.name }}</td>
                <td>{{ group.currency }}</td>
                <td>
                  {{ formatCurrency(group.initial_amount, group.currency) }}
                </td>
                <td>{{ group.notes || "-" }}</td>
                <td>
                  <button
                    class="danger-btn"
                    type="button"
                    @click="confirmDelete(group.name)"
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

    <div class="surface">
      <h3>{{ t("funds.snapshotTitle") }}</h3>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ t("funds.snapshotTable.name") }}</th>
              <th>{{ t("funds.snapshotTable.currency") }}</th>
              <th>{{ t("funds.snapshotTable.initial") }}</th>
              <th>{{ t("funds.snapshotTable.current") }}</th>
              <th>{{ t("funds.snapshotTable.pl") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!funds.length">
              <td colspan="5" class="empty">{{ t("funds.emptySnapshot") }}</td>
            </tr>
            <tr v-for="item in funds" :key="item.name">
              <td>{{ item.name }}</td>
              <td>{{ item.currency }}</td>
              <td>{{ formatCurrency(item.initial_amount, item.currency) }}</td>
              <td>{{ formatCurrency(item.current_total, item.currency) }}</td>
              <td
                :class="{
                  positive: item.total_pl >= 0,
                  negative: item.total_pl < 0,
                }"
              >
                {{ formatCurrency(item.total_pl, item.currency) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";

import type { FundSnapshot, FundingGroup } from "@/types/api";

const props = defineProps<{
  fundingGroups: FundingGroup[];
  funds: FundSnapshot[];
}>();

const emit = defineEmits<{
  (e: "create", payload: FundingGroup): void;
  (e: "delete", name: string): void;
  (e: "refresh"): void;
}>();

const { t } = useI18n();

const pending = ref(false);
const form = reactive<FundingGroup>({
  name: "",
  currency: "JPY",
  initial_amount: 0,
  notes: "",
});

function resetForm(): void {
  form.name = "";
  form.currency = "JPY";
  form.initial_amount = 0;
  form.notes = "";
}

function formatCurrency(value: number, currency: string): string {
  const locale = currency === "USD" ? "en-US" : "ja-JP";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(value);
}

async function handleSubmit() {
  if (!form.name) {
    return;
  }
  pending.value = true;
  try {
    const payload: FundingGroup = {
      name: form.name.trim(),
      currency: form.currency,
      initial_amount: Number(form.initial_amount),
      notes: form.notes?.trim() || undefined,
    };
    emit("create", payload);
    resetForm();
  } finally {
    pending.value = false;
  }
}

function confirmDelete(name: string) {
  if (props.fundingGroups.length <= 1) {
    alert(t("funds.confirm.mustKeepOne"));
    return;
  }
  if (window.confirm(t("funds.confirm.delete", { name }))) {
    emit("delete", name);
  }
}
</script>

<style scoped>
.funds-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  padding: clamp(1.6rem, 3vw, 2.4rem);
  overflow: hidden;
}

.funds-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.08) 58%, rgba(255, 255, 255, 0)),
    radial-gradient(circle at 90% 10%, rgba(255, 200, 67, 0.18), transparent 55%);
  mix-blend-mode: overlay;
  opacity: 0.42;
}

.funds-panel > * {
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
  grid-template-columns: minmax(320px, 420px) 1fr;
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

.primary-btn {
  align-self: flex-end;
}

.table-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--divider);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.table-scroll table {
  min-width: 560px;
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


.danger-btn {
  border-radius: 999px;
  border: 1px solid rgba(225, 57, 45, 0.5);
  background: linear-gradient(180deg, rgba(225, 57, 45, 0.15), rgba(225, 57, 45, 0.08));
  color: var(--accent-red);
  padding: 0.4rem 1rem;
  font-size: 0.82rem;
  letter-spacing: 0.45px;
  cursor: pointer;
  transition: transform var(--transition), box-shadow var(--transition);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.danger-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
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
