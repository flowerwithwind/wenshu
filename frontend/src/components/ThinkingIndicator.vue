<template>
  <div class="thinking-indicator">
    <div class="thinking-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
    </div>
    <div class="thinking-body">
      <div class="thinking-title">
        <span class="brain-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.3 4.3-2.5 5.5L12 22l-4.5-7.5C6.3 13.3 5 11.5 5 9a7 7 0 0 1 7-7z"/>
          </svg>
        </span>
        {{ title }}
      </div>
      <div class="thinking-sub">{{ subtitle }}</div>
      <div class="thinking-dots" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <div class="thinking-bar">
        <div class="thinking-bar-inner"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '模型正在思考' },
  subtitle: { type: String, default: '正在分析问题并生成回答…' },
})
</script>

<style scoped>
.thinking-indicator {
  display: flex;
  gap: 12px;
  padding: 8px 0 4px;
  animation: fadeIn 0.35s ease;
}

.thinking-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.12);
}

.thinking-body {
  flex: 1;
  background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
  border: 1px solid #e0e7ff;
  border-radius: 14px;
  padding: 14px 16px;
  max-width: 420px;
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.06);
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #312e81;
}

.brain-icon {
  display: inline-flex;
  color: var(--primary);
  animation: pulseSoft 1.4s ease-in-out infinite;
}

.thinking-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.thinking-dots {
  display: flex;
  gap: 5px;
  margin-top: 12px;
}

.thinking-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
  opacity: 0.35;
  animation: bounceDot 1.2s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) { animation-delay: 0.15s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.3s; }

.thinking-bar {
  margin-top: 12px;
  height: 3px;
  background: #e0e7ff;
  border-radius: 99px;
  overflow: hidden;
}

.thinking-bar-inner {
  width: 40%;
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--primary), #818cf8, var(--primary));
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}

@keyframes bounceDot {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
  40% { transform: translateY(-5px); opacity: 1; }
}

@keyframes shimmer {
  0% { transform: translateX(-30%); background-position: 0% 50%; }
  100% { transform: translateX(280%); background-position: 100% 50%; }
}

@keyframes pulseSoft {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.08); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
