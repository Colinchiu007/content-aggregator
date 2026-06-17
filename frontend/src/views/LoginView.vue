<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 32, message: '用户名长度为 2-32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  const success = await userStore.login({
    username: form.username,
    password: form.password,
  })
  loading.value = false

  if (success) {
    const redirect = (route.query.redirect as string) ?? '/'
    router.push(redirect)
  }
}
</script>

<template>
  <div class="login-view">
    <el-card shadow="hover" class="login-card">
      <h2 class="login-title">登录</h2>
      <p class="login-subtitle">登录 HotRewrite 开始使用</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="0"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" class="full-width">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 160px);
  padding: 24px;
}

.login-card {
  width: 400px;
  max-width: 100%;
}

.login-title {
  text-align: center;
  font-size: 24px;
  margin: 0 0 8px;
}

.login-subtitle {
  text-align: center;
  color: var(--el-text-color-secondary);
  margin: 0 0 24px;
  font-size: 14px;
}

.full-width {
  width: 100%;
}

.login-footer {
  text-align: center;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.login-footer a {
  color: var(--el-color-primary);
  text-decoration: none;
  margin-left: 4px;
}
</style>
