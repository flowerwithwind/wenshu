<template>
  <div class="app-layout">
    <router-view />
  </div>
</template>

<script setup>
</script>

<style scoped>
.app-layout {
  width: 100%;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 子路由根组件（AppLayout）铺满 */
.app-layout > :deep(*) {
  flex: 1;
  min-height: 0;
  min-width: 0;
}
</style>