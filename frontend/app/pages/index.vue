<template>
  <div class="dashboard">
    <!-- Row 1: BME688 environmental cards -->
    <div class="row bme-row">
      <SensorCard
        title="Temperature"
        :value="bme ? `${bme.temperature_c.toFixed(1)}` : null"
        unit="°C"
        :sub-value="bme ? `${bme.temperature_f.toFixed(1)} °F` : null"
        :status="bme ? 'warn' : (data?.environment_error ? 'error' : 'off')"
        :error="data?.environment_error"
      />
      <SensorCard
        title="Humidity"
        :value="bme ? `${Math.round(bme.humidity_rh)}` : null"
        unit="%"
        :status="bme ? 'ok' : (data?.environment_error ? 'error' : 'off')"
        :error="data?.environment_error"
      />
      <SensorCard
        title="Pressure"
        :value="bme ? `${Math.round(bme.pressure_hpa)}` : null"
        unit="hPa"
        :sub-value="bme ? `${bme.altitude_m.toFixed(0)} m alt` : null"
        :status="bme ? 'ok' : (data?.environment_error ? 'error' : 'off')"
        :error="data?.environment_error"
      />
      <SensorCard
        title="Air Quality"
        :value="bme ? bme.air_quality_label : null"
        unit=""
        :status="bme ? airQualityStatus(bme.air_quality_label) : (data?.environment_error ? 'error' : 'off')"
        :error="data?.environment_error"
      />
    </div>

    <!-- Row 2: PIR | dToF | NFC -->
    <div class="row sensor-row">
      <SensorCard
        :title="`PIR Motion  (×${data?.motion?.event_count ?? 0})`"
        :value="pirValue"
        unit=""
        :status="pirStatus"
        :error="data?.motion_error"
        :highlight="data?.motion?.detected"
      />
      <SensorCard
        title="dToF Distance (centre)"
        :value="dtofValue"
        :unit="data?.distance ? 'mm' : ''"
        :sub-value="data?.distance ? `min ${data.distance.min_mm} mm` : null"
        :status="dtofStatus"
        :error="data?.distance_error"
      />
      <SensorCard
        title="NFC / RFID Tag"
        :value="nfcValue"
        :unit="nfcUnit"
        :status="nfcStatus"
        :error="data?.nfc_error"
      />
    </div>

    <!-- Row 3: Audio VU meter -->
    <div class="row audio-row">
      <div class="audio-card">
        <div class="card-title">Microphone Level</div>
        <div class="vu-wrap">
          <div class="vu-bar-bg">
            <div
              class="vu-bar-fill"
              :class="vuColourClass"
              :style="{ width: `${(data?.audio?.level ?? 0) * 100}%` }"
            />
            <div
              class="vu-peak"
              :style="{ left: `${(data?.audio?.peak_level ?? 0) * 100}%` }"
            />
          </div>
          <div class="vu-labels">
            <span class="vu-db" :class="vuColourClass">{{ data?.audio?.db?.toFixed(1) ?? '—' }} dBFS</span>
            <span class="vu-peak-label">peak {{ data?.audio?.peak_db?.toFixed(1) ?? '—' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- dToF zone heatmap -->
    <div v-if="data?.distance" class="row heatmap-row">
      <div class="heatmap-card">
        <div class="card-title">dToF Zone Map (3×3)</div>
        <div class="zone-grid">
          <div
            v-for="(dist, i) in data.distance.distances_mm"
            :key="i"
            class="zone-cell"
            :class="zoneClass(dist)"
          >
            <span class="zone-dist">{{ dist >= 0 ? dist : '—' }}</span>
            <span class="zone-unit">{{ dist >= 0 ? 'mm' : '' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface BMEData {
  temperature_c: number
  temperature_f: number
  humidity_rh: number
  pressure_hpa: number
  gas_resistance_ohm: number
  altitude_m: number
  air_quality_label: string
}

interface MotionData {
  detected: boolean
  raw_moving: boolean
  event_count: number
}

interface DistanceData {
  distances_mm: number[]
  confidences: number[]
  center_mm: number
  min_mm: number
}

interface NFCData {
  rf_field_present: boolean
  text: string
  raw_hex: string
}

interface AudioData {
  db: number
  peak_db: number
  level: number
  peak_level: number
}

interface SensorSnapshot {
  environment: BMEData | null
  environment_error: string
  motion: MotionData
  motion_error: string
  distance: DistanceData | null
  distance_error: string
  nfc: NFCData | null
  nfc_error: string
  audio: AudioData
}

const apiBase = useApiBase()

// Poll every 500 ms via SSE; fall back to polling if SSE is unavailable
const data = ref<SensorSnapshot | null>(null)

onMounted(() => {
  const es = new EventSource(`${apiBase}/sensors/stream`)
  es.onmessage = (e: MessageEvent) => {
    try {
      data.value = JSON.parse(e.data)
    } catch { /* ignore parse errors */ }
  }
  es.onerror = () => {
    // SSE dropped — fall back to polling
    es.close()
    startPolling()
  }
  onUnmounted(() => es.close())
})

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) return
  const fetchData = async () => {
    try {
      const res = await fetch(`${apiBase}/sensors/all`)
      data.value = await res.json()
    } catch { /* ignore */ }
  }
  fetchData()
  pollTimer = setInterval(fetchData, 1000)
  onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
}

// Derived values
const bme = computed(() => data.value?.environment ?? null)

function airQualityStatus(label: string): string {
  if (label === 'Excellent' || label === 'Good') return 'ok'
  if (label === 'Fair') return 'warn'
  return 'error'
}

const pirValue = computed(() => {
  if (!data.value) return null
  if (data.value.motion_error) return 'ERR'
  return data.value.motion?.detected ? 'MOTION' : 'CLEAR'
})

const pirStatus = computed(() => {
  if (!data.value) return 'off'
  if (data.value.motion_error) return 'off'
  return data.value.motion?.detected ? 'error' : 'ok'
})

const dtofValue = computed(() => {
  if (!data.value?.distance) return data.value?.distance_error ? 'ERR' : null
  const d = data.value.distance.center_mm
  return d >= 0 ? String(d) : '—'
})

const dtofStatus = computed(() => {
  if (!data.value?.distance) return 'off'
  const d = data.value.distance.center_mm
  if (d < 0) return 'off'
  return d < 300 ? 'warn' : 'ok'
})

const nfcValue = computed(() => {
  if (!data.value?.nfc) return data.value?.nfc_error ? 'ERR' : null
  return data.value.nfc.rf_field_present ? 'RF ON' : 'IDLE'
})

const nfcUnit = computed(() => {
  if (!data.value?.nfc) return ''
  const txt = data.value.nfc.text.replace(/\x00/g, '').trim()
  return txt ? txt.slice(0, 16) : ''
})

const nfcStatus = computed(() => {
  if (!data.value?.nfc) return 'off'
  return data.value.nfc.rf_field_present ? 'ok' : 'off'
})

const vuColourClass = computed(() => {
  const db = data.value?.audio?.db ?? -60
  if (db < -12) return 'vu-green'
  if (db < -3) return 'vu-amber'
  return 'vu-red'
})

function zoneClass(dist: number): string {
  if (dist < 0) return 'zone-none'
  if (dist < 200) return 'zone-near'
  if (dist < 800) return 'zone-mid'
  return 'zone-far'
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 1000px;
  margin: 0 auto;
}

/* ── Rows ── */
.bme-row,
.sensor-row {
  display: grid;
  gap: 12px;
}

.bme-row    { grid-template-columns: repeat(4, 1fr); }
.sensor-row { grid-template-columns: repeat(3, 1fr); }

/* ── Audio card ── */
.audio-row {
  display: flex;
}

.audio-card {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-title {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
}

.vu-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
}

.vu-bar-bg {
  flex: 1;
  height: 18px;
  background: var(--raised);
  border-radius: 9px;
  position: relative;
  overflow: visible;
}

.vu-bar-fill {
  height: 100%;
  border-radius: 9px;
  transition: width 0.15s ease;
}

.vu-peak {
  position: absolute;
  top: -3px;
  width: 3px;
  height: 24px;
  background: var(--error);
  border-radius: 2px;
  transform: translateX(-50%);
}

.vu-labels {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 100px;
  gap: 2px;
}

.vu-db {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
}

.vu-peak-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}

.vu-green { background: var(--success); color: var(--success); }
.vu-amber { background: var(--warning); color: var(--warning); }
.vu-red   { background: var(--error);   color: var(--error);   }

/* ── Zone heatmap ── */
.heatmap-row { display: flex; }

.heatmap-card {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 18px;
}

.zone-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
}

.zone-cell {
  border-radius: 8px;
  padding: 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: background 0.2s;
}

.zone-dist {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
}

.zone-unit {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--muted);
}

.zone-none { background: var(--raised); color: var(--muted); }
.zone-near { background: rgba(252, 129, 129, 0.2); color: var(--error); }
.zone-mid  { background: rgba(246, 173, 85, 0.15); color: var(--warning); }
.zone-far  { background: rgba(72, 199, 142, 0.12); color: var(--success); }

/* ── Responsive: Pi 7" display (800px) ── */
@media (max-width: 800px) {
  .bme-row    { grid-template-columns: repeat(2, 1fr); }
  .sensor-row { grid-template-columns: repeat(3, 1fr); }
  .zone-grid  { gap: 6px; }
}

@media (max-width: 500px) {
  .bme-row    { grid-template-columns: repeat(2, 1fr); }
  .sensor-row { grid-template-columns: 1fr; }
}
</style>
