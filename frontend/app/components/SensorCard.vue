<template>
  <div class="sensor-card" :class="[`status-${status}`, { highlight }]">
    <div class="card-title">{{ title }}</div>
    <div class="card-body">
      <template v-if="value !== null && value !== undefined">
        <span class="card-value">{{ value }}</span>
        <span v-if="unit" class="card-unit">{{ unit }}</span>
      </template>
      <template v-else-if="error">
        <span class="card-value na">ERR</span>
      </template>
      <template v-else>
        <span class="card-value na">N/A</span>
      </template>
    </div>
    <div v-if="subValue" class="card-sub">{{ subValue }}</div>
    <div v-else-if="error" class="card-error">{{ truncate(error) }}</div>
    <div class="status-dot" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  title: string
  value?: string | null
  unit?: string
  subValue?: string | null
  status?: 'ok' | 'warn' | 'error' | 'off'
  error?: string
  highlight?: boolean
}>()

function truncate(s: string, max = 32): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}
</script>

<style scoped>
.sensor-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: border-color 0.2s, box-shadow 0.2s;
  overflow: hidden;
}

/* Status colour variants */
.sensor-card.status-ok    { border-color: rgba(72,  199, 142, 0.4); }
.sensor-card.status-warn  { border-color: rgba(246, 173, 85,  0.4); }
.sensor-card.status-error { border-color: rgba(252, 129, 129, 0.4); }
.sensor-card.status-off   { opacity: 0.55; }

.sensor-card.highlight {
  box-shadow: 0 0 0 2px var(--error);
  animation: pulse 1s ease infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(252, 129, 129, 0.8); }
  50%       { box-shadow: 0 0 0 6px rgba(252, 129, 129, 0.15); }
}

.card-title {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-body {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.card-value {
  font-family: var(--font-display);
  font-size: 32px;
  line-height: 1;
  color: var(--text);
  letter-spacing: 0.02em;
}

.card-value.na {
  font-size: 24px;
  color: var(--muted);
}

.card-unit {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}

.card-sub {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}

.card-error {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--error);
  opacity: 0.8;
}

/* Status dot (bottom-right corner) */
.status-dot {
  position: absolute;
  bottom: 8px;
  right: 10px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
  opacity: 0.4;
}

.status-ok    .status-dot { background: var(--success); opacity: 1; }
.status-warn  .status-dot { background: var(--warning); opacity: 1; }
.status-error .status-dot { background: var(--error);   opacity: 1; }

/* Colour the value text by status */
.status-warn  .card-value:not(.na) { color: var(--warning); }
.status-error .card-value:not(.na) { color: var(--error);   }
.status-ok    .card-value:not(.na) { color: var(--success); }
</style>
