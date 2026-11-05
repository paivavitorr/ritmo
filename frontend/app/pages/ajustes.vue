<script setup lang="ts">
import { extrairMensagemErro } from '~/composables/useApi'
import { usePushNotification } from '~/composables/usePushNotification'
import type { UsuarioRead } from '~/stores/auth'

const auth = useAuthStore()
const { requisitar } = useApi()
const {
  suportado,
  inscrito,
  permissao,
  carregando: carregandoPush,
  erro: erroPush,
  ativar: ativarPush,
  desativar: desativarPush,
} = usePushNotification()

const nome = ref(auth.usuario?.nome ?? '')
const fuso = ref(auth.usuario?.fuso ?? 'America/Manaus')
const antecedencia = ref(String(auth.usuario?.antecedencia_padrao_min ?? 10))
const salvando = ref(false)
const mensagem = ref<string | null>(null)
const erro = ref<string | null>(null)

async function salvarAjustes() {
  erro.value = null
  mensagem.value = null
  salvando.value = true
  const minParsed = Number(antecedencia.value)
  const antecedenciaMin = Number.isNaN(minParsed) || minParsed < 0
    ? 10
    : Math.round(minParsed)
  try {
    const atualizado = await requisitar<UsuarioRead>('/auth/eu', {
      method: 'PATCH',
      body: {
        nome: nome.value.trim(),
        fuso: fuso.value.trim(),
        antecedencia_padrao_min: antecedenciaMin,
      },
    })
    auth.usuario = atualizado
    mensagem.value = 'Ajustes salvos.'
  }
  catch (e: unknown) {
    erro.value = extrairMensagemErro(e, 'Não foi possível salvar os ajustes.')
  }
  finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="max-w-lg">
    <h1 class="text-2xl font-semibold text-tinta">
      Ajustes
    </h1>
    <p class="mt-1 text-sm text-grafite-suave">
      Preferências da sua conta, fuso horário e antecedência padrão dos lembretes.
    </p>

    <form
      class="mt-8 flex flex-col gap-5 rounded-[var(--radius-bloco)] border border-linha bg-papel p-6"
      @submit.prevent="salvarAjustes"
    >
      <BaseInput
        id="ajuste-nome"
        v-model="nome"
        label="Nome"
        obrigatorio
      />

      <BaseInput
        id="ajuste-fuso"
        v-model="fuso"
        label="Fuso horário (IANA)"
        dica="Define os limites do seu dia na régua e nos resumos."
        obrigatorio
      />

      <BaseInput
        id="ajuste-antecedencia"
        v-model="antecedencia"
        tipo="number"
        min="0"
        max="1440"
        tabular
        label="Lembrar antes do bloco (minutos)"
        obrigatorio
      />

      <p
        v-if="erro"
        class="rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
        role="alert"
      >
        {{ erro }}
      </p>
      <p
        v-if="mensagem"
        class="rounded-[var(--radius-bloco)] border border-salvia-200 bg-salvia-50 px-3.5 py-2.5 text-sm text-salvia-700"
        role="status"
      >
        {{ mensagem }}
      </p>

      <div class="flex items-center justify-between pt-2">
        <BaseButton
          variante="perigo"
          @click="auth.sair()"
        >
          Sair da conta
        </BaseButton>

        <BaseButton
          tipo="submit"
          :carregando="salvando"
        >
          Salvar alterações
        </BaseButton>
      </div>
    </form>

    <!-- Card de Notificações Web Push -->
    <section class="mt-8 rounded-[var(--radius-bloco)] border border-linha bg-papel p-6">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-base font-medium text-tinta">
            Notificações Web Push
          </h2>
          <p class="mt-1 text-sm text-grafite-suave">
            Receba lembretes automáticos no navegador minutos antes de cada bloco planejado começar.
          </p>
        </div>
        <span
          v-if="!suportado"
          class="inline-flex shrink-0 items-center rounded-full bg-ardosia-100 px-2.5 py-0.5 text-xs font-medium text-grafite-suave"
        >
          Não suportado
        </span>
        <span
          v-else-if="inscrito"
          class="inline-flex shrink-0 items-center rounded-full bg-salvia-100 px-2.5 py-0.5 text-xs font-medium text-salvia-700"
        >
          Ativo neste aparelho
        </span>
        <span
          v-else-if="permissao === 'denied'"
          class="inline-flex shrink-0 items-center rounded-full bg-rosa-cha-100 px-2.5 py-0.5 text-xs font-medium text-erro"
        >
          Bloqueado
        </span>
        <span
          v-else
          class="inline-flex shrink-0 items-center rounded-full bg-ardosia-100 px-2.5 py-0.5 text-xs font-medium text-grafite-suave"
        >
          Inativo
        </span>
      </div>

      <div
        v-if="erroPush"
        class="mt-4 rounded-[var(--radius-bloco)] border border-rosa-cha-200 bg-rosa-cha-50 px-3.5 py-2.5 text-sm text-erro"
        role="alert"
      >
        {{ erroPush }}
      </div>

      <p
        v-if="permissao === 'denied'"
        class="mt-4 text-xs text-grafite-suave"
      >
        As notificações estão bloqueadas nas permissões do navegador para este site. Libere nas configurações para receber alertas.
      </p>

      <div
        v-if="suportado"
        class="mt-5 flex items-center justify-end"
      >
        <BaseButton
          v-if="inscrito"
          variante="secundario"
          tamanho="sm"
          :carregando="carregandoPush"
          @click="desativarPush()"
        >
          Desativar notificações
        </BaseButton>
        <BaseButton
          v-else
          variante="primario"
          tamanho="sm"
          :carregando="carregandoPush"
          :desabilitado="permissao === 'denied'"
          @click="ativarPush()"
        >
          Ativar notificações neste aparelho
        </BaseButton>
      </div>
    </section>
  </div>
</template>
