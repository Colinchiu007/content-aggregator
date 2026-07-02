<script setup lang="ts">
</script>

<template>
  <footer class="app-footer">
    <div class="footer-content">
      <div class="footer-info">
        <p>HotRewrite v2.0 — 热文采集改写一站式平台</p>
        <p class="footer-sub">帮助内容创作者快速将优质文章进行AI改写，并一键发布到多个平台</p>
      </div>
      <div class="footer-links">
        <a href="#">关于我们</a>
        <a href="#">使用帮助</a>
        <a href="#">服务条款</a>
        <a href="#">隐私政策</a>
      </div>
      <div class="footer-copy">
        <p>© {{ new Date().getFullYear() }} HotRewrite. All rights reserved.</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer {
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  padding: 32px 24px 16px;
  margin-top: auto;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  text-align: center;
}

.footer-info {
  margin-bottom: 16px;
}

.footer-info p {
  margin: 4px 0;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.footer-sub {
  font-size: 12px !important;
  color: var(--el-text-color-secondary) !important;
}

.footer-links {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.footer-links a {
  font-size: 13px;
  color: var(--el-text-color-regular);
  text-decoration: none;
}

.footer-links a:hover {
  color: var(--el-color-primary);
}

.footer-copy {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
