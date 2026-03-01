<template>
  <UApp>
    <div class="shell">
      <header class="site-header">
        <div class="header-inner">
          <div class="logo">
            <svg class="logo-mark" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <circle cx="12" cy="12" r="4" fill="currentColor" opacity="0.4"/>
              <line x1="12" y1="2" x2="12" y2="6" stroke="currentColor" stroke-width="1.5"/>
              <line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" stroke-width="1.5"/>
              <line x1="2" y1="12" x2="6" y2="12" stroke="currentColor" stroke-width="1.5"/>
              <line x1="18" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            <span class="logo-text">PI<em>SENSORS</em></span>
          </div>
          <div class="header-right">
            <span class="clock">{{ clock }}</span>
            <UColorModeButton />
          </div>
        </div>
      </header>

      <main class="site-main">
        <NuxtPage />
      </main>
    </div>
  </UApp>
</template>

<script setup lang="ts">
const clock = ref('')

function updateClock() {
  clock.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(() => {
  updateClock()
  const id = setInterval(updateClock, 1000)
  onUnmounted(() => clearInterval(id))
})
</script>

<style>
/* ── Design tokens ── */
:root {
  --bg:           #12121A;
  --surface:      #1E1E2A;
  --raised:       #26263A;
  --border:       #2A2A40;
  --accent:       #63B3ED;
  --success:      #48C78E;
  --warning:      #F6AD55;
  --error:        #FC8181;
  --muted:        #718096;
  --text:         #E2E8F0;
  --font-display: 'Bebas Neue', sans-serif;
  --font-mono:    'DM Mono', monospace;
  --font-body:    'Outfit', sans-serif;
}

/* Light mode overrides */
html:not(.dark) {
  --bg:      #F0F4F8;
  --surface: #FFFFFF;
  --raised:  #E8EEF4;
  --border:  #CBD5E0;
  --text:    #1A202C;
  --muted:   #718096;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
</style>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.site-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 20px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-mark {
  width: 22px;
  height: 22px;
  color: var(--accent);
}

.logo-text {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: 0.12em;
  color: var(--text);
}

.logo-text em {
  font-style: normal;
  color: var(--accent);
  margin-left: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.clock {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--muted);
  letter-spacing: 0.06em;
}

.site-main {
  flex: 1;
  padding: 20px;
}
</style>
