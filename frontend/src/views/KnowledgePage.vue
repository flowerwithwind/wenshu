<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>知识库管理</h1>
        <p>维护 NL2SQL Few-shot、同义词与领域映射，直接影响智能问数的 SQL 生成质量</p>
      </div>
    </header>
    <div class="content">
      <KnowledgeManager embedded />
    </div>
  </div>
</template>

<script setup>
import KnowledgeManager from '../components/KnowledgeManager.vue'
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  padding: 20px 28px 20px;
  background:
    radial-gradient(ellipse 60% 40% at 100% 0%, rgba(79, 70, 229, 0.06), transparent),
    var(--bg);
}

.page-header {
  flex-shrink: 0;
  margin-bottom: 14px;
}

.page-header h1 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
  max-width: 720px;
}

.content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
}
</style>
