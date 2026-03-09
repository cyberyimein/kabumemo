<template>
  <section class="panel surface-panel">
    <header class="panel-header">
      <div>
        <h2>{{ t("imports.title") }}</h2>
        <p>{{ t("imports.description") }}</p>
      </div>
    </header>

    <div class="panel-grid">
      <form class="surface import-form" @submit.prevent="handlePreview">
        <h3>{{ t("imports.formTitle") }}</h3>
        <div class="form-grid">
          <label class="file-field">
            <span>{{ t("imports.fields.domestic") }}</span>
            <input type="file" accept=".csv,text/csv" @change="onFileChange($event, 'domestic')" />
          </label>
          <label class="file-field">
            <span>{{ t("imports.fields.us") }}</span>
            <input type="file" accept=".csv,text/csv" @change="onFileChange($event, 'us')" />
          </label>
          <label>
            <span>{{ t("imports.fields.jpyPositionGroup") }}</span>
            <select v-model="positionGroupJpy">
              <option v-for="group in jpyGroups" :key="group.name" :value="group.name">{{ group.name }}</option>
            </select>
          </label>
          <label>
            <span>{{ t("imports.fields.jpySettlementGroup") }}</span>
            <select v-model="settlementGroupJpy">
              <option v-for="group in jpyGroups" :key="group.name" :value="group.name">{{ group.name }}</option>
            </select>
          </label>
          <label>
            <span>{{ t("imports.fields.usdPositionGroup") }}</span>
            <select v-model="positionGroupUsd">
              <option v-for="group in usdGroups" :key="group.name" :value="group.name">{{ group.name }}</option>
            </select>
          </label>
          <label>
            <span>{{ t("imports.fields.usdSettlementGroup") }}</span>
            <select v-model="settlementGroupUsd">
              <option v-for="group in usdGroups" :key="group.name" :value="group.name">{{ group.name }}</option>
            </select>
          </label>
        </div>
        <div class="form-actions">
          <button type="submit" class="primary-btn" :disabled="pendingPreview">
            {{ t("imports.actions.preview") }}
          </button>
          <button type="button" class="ghost-btn" :disabled="!preview.items.length || pendingApply" @click="handleApply">
            {{ t("imports.actions.apply") }}
          </button>
        </div>
        <p v-if="message" class="hint">{{ message }}</p>
      </form>

      <div class="surface import-preview">
        <h3>{{ t("imports.previewTitle", { count: preview.items.length }) }}</h3>
        <ul v-if="preview.warnings.length" class="warnings">
          <li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li>
        </ul>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{{ t("imports.table.date") }}</th>
                <th>{{ t("imports.table.symbol") }}</th>
                <th>{{ t("imports.table.market") }}</th>
                <th class="numeric">{{ t("imports.table.quantity") }}</th>
                <th class="numeric">{{ t("imports.table.tradeAmount") }}</th>
                <th class="numeric">{{ t("imports.table.settlementAmount") }}</th>
                <th>{{ t("imports.table.positionGroup") }}</th>
                <th>{{ t("imports.table.settlementGroup") }}</th>
                <th>{{ t("imports.table.accountType") }}</th>
                <th>{{ t("imports.table.taxed") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!preview.items.length">
                <td colspan="10" class="empty">{{ t("imports.empty") }}</td>
              </tr>
              <tr v-for="item in preview.items" :key="item.transaction_id">
                <td>{{ item.trade_date }}</td>
                <td>{{ item.symbol }}</td>
                <td>{{ item.market }}</td>
                <td class="numeric">{{ item.quantity }}</td>
                <td class="numeric">{{ formatCurrency(item.trade_amount, item.trade_currency) }}</td>
                <td class="numeric">{{ formatCurrency(item.settlement_amount, item.settlement_currency) }}</td>
                <td>{{ item.position_group }}</td>
                <td>{{ item.settlement_group }}</td>
                <td>{{ item.broker_account_type }}</td>
                <td>{{ item.taxed }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import { applyBrokerImport, previewBrokerImport } from "@/services/api";
import type {
  BrokerImportFile,
  BrokerImportPreviewResponse,
  FundingGroup,
} from "@/types/api";

const props = defineProps<{
  fundingGroups: FundingGroup[];
}>();

const emit = defineEmits<{
  (e: "imported"): void;
  (e: "notify", payload: { type: "success" | "error" | "info"; message: string }): void;
}>();

const { t } = useI18n();

const domesticFile = ref<BrokerImportFile | null>(null);
const usFile = ref<BrokerImportFile | null>(null);
const pendingPreview = ref(false);
const pendingApply = ref(false);
const message = ref("");
const preview = ref<BrokerImportPreviewResponse>({ items: [], warnings: [], applied_count: 0, skipped_count: 0 });

const jpyGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "JPY"));
const usdGroups = computed(() => props.fundingGroups.filter((item) => item.currency === "USD"));

const positionGroupJpy = ref("JPY");
const settlementGroupJpy = ref("JPY");
const positionGroupUsd = ref("USD");
const settlementGroupUsd = ref("USD");

async function fileToPayload(file: File): Promise<BrokerImportFile> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return {
    file_name: file.name,
    content_base64: btoa(binary),
    encoding_hint: null,
  };
}

async function onFileChange(event: Event, type: "domestic" | "us") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    return;
  }
  const payload = await fileToPayload(file);
  if (type === "domestic") {
    domesticFile.value = payload;
  } else {
    usFile.value = payload;
  }
}

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "JPY" ? 0 : 2,
  }).format(amount);
}

async function handlePreview() {
  pendingPreview.value = true;
  message.value = "";
  try {
    preview.value = await previewBrokerImport({
      domestic_report: domesticFile.value,
      us_report: usFile.value,
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
    });
    message.value = t("imports.previewReady", { count: preview.value.items.length });
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("imports.errors.preview") });
  } finally {
    pendingPreview.value = false;
  }
}

async function handleApply() {
  pendingApply.value = true;
  try {
    preview.value = await applyBrokerImport({
      domestic_report: domesticFile.value,
      us_report: usFile.value,
      position_group_jpy: positionGroupJpy.value,
      settlement_group_jpy: settlementGroupJpy.value,
      position_group_usd: positionGroupUsd.value,
      settlement_group_usd: settlementGroupUsd.value,
      replace_existing_transactions: false,
    });
    emit(
      "notify",
      {
        type: "success",
        message: t("imports.applyDone", {
          count: preview.value.applied_count,
          skipped: preview.value.skipped_count,
        }),
      }
    );
    message.value = t("imports.applyDone", {
      count: preview.value.applied_count,
      skipped: preview.value.skipped_count,
    });
    emit("imported");
  } catch (error) {
    emit("notify", { type: "error", message: error instanceof Error ? error.message : t("imports.errors.apply") });
  } finally {
    pendingApply.value = false;
  }
}
</script>

<style scoped>
.import-form,
.import-preview {
  min-height: 100%;
}

.import-form .form-actions {
  justify-content: flex-start;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.file-field {
  justify-content: flex-start;
}
</style>