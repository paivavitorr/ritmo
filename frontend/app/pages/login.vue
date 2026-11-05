<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'

definePageMeta({
  layout: 'auth',
})

const auth = useAuthStore()
const modo = ref<'entrar' | 'registrar'>('entrar')
const nome = ref('')
const email = ref('')
const senha = ref('')
const fuso = ref(
  Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Manaus',
)
const carregando = ref(false)
const erro = ref<string | null>(null)

function alternarModo(novo: 'entrar' | 'registrar') {
  modo.value = novo
  erro.value = null
}

async function submeter() {
  erro.value = null
  carregando.value = true
  try {
    if (modo.value === 'entrar') {
      await auth.login({
        email: email.value,
        senha: senha.value,
      })
    }
    else {
      await auth.registrar({
        nome: nome.value,
        email: email.value,
        senha: senha.value,
        fuso: fuso.value,
      })
    }
    await navigateTo('/')
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(
      e,
      modo.value === 'entrar'
        ? 'Não foi possível entrar. Verifique e-mail e senha.'
        : 'Não foi possível criar sua conta.',
    )
  }
  finally {
    carregando.value = false
  }
}
</script>

<template>
  <section class="rounded-[var(--radius-sheet)] border border-linha bg-papel p-7 shadow-[var(--shadow-elevado)] sm:p-9">
    <header>
      <h1 class="text-2xl font-semibold text-tinta">
        Ritmo
      </h1>
      <p class="mt-1.5 text-sm text-grafite-suave">
        Sua régua diária de rotina em blocos e horas líquidas.
      </p>
    </header>

    <!-- Seletor de modo -->
    <div
      class="mt-6 grid grid-cols-2 rounded-[var(--radius-bloco)] bg-nevoa p-1"
      role="tablist"
    >
      <button
        type="button"
        role="tab"
        :aria-selected="modo === 'entrar'"
        class="rounded-lg py-2 text-sm font-medium transition-colors duration-150"
        :class="modo === 'entrar' ? 'bg-papel text-tinta' : 'text-grafite-suave hover:text-tinta'"
        @click="alternarModo('entrar')"
      >
        Entrar
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="modo === 'registrar'"
        class="rounded-lg py-2 text-sm font-medium transition-colors duration-150"
        :class="modo === 'registrar' ? 'bg-papel text-tinta' : 'text-grafite-suave hover:text-tinta'"
        @click="alternarModo('registrar')"
      >
        Criar conta
      </button>
    </div>

    <form
      class="mt-6 flex flex-col gap-4"
      @submit.prevent="submeter"
    >
      <BaseInput
        v-if="modo === 'registrar'"
        id="campo-nome"
        v-model="nome"
        label="Como prefere ser chamado?"
        placeholder="Seu nome"
        obrigatorio
      />

      <BaseInput
        id="campo-email"
        v-model="email"
        tipo="email"
        label="E-mail"
        placeholder="voce@exemplo.com"
        obrigatorio
      />

      <BaseInput
        id="campo-senha"
        v-model="senha"
        tipo="password"
        label="Senha"
        placeholder="Mínimo de 8 caracteres"
        :dica="modo === 'registrar' ? 'Use pelo menos 8 caracteres.' : ''"
        obrigatorio
      />

      <BaseInput
        v-if="modo === 'registrar'"
        id="campo-fuso"
        v-model="fuso"
        label="Fuso horário"
        dica="Detectado automaticamente do seu dispositivo."
        obrigatorio
      />

      <p
        v-if="erro"
        class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
        role="alert"
      >
        {{ erro }}
      </p>

      <div class="mt-2">
        <BaseButton
          tipo="submit"
          bloco
          tamanho="lg"
          :carregando="carregando"
        >
          {{ modo === 'entrar' ? 'Entrar na rotina' : 'Criar conta e começar' }}
        </BaseButton>
      </div>
    </form>
  </section>
</template>
