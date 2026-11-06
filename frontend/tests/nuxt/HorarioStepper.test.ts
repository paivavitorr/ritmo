import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import HorarioStepper from '~/components/bloco/HorarioStepper.vue'

describe('HorarioStepper', () => {
  it('renderiza o rótulo e o valor', async () => {
    const wrapper = await mountSuspended(HorarioStepper, {
      props: { id: 't-ini', modelValue: '08:00', label: 'Início', campo: 'inicio' },
    })
    expect(wrapper.text()).toContain('Início')
    expect(wrapper.find('input').element.value).toBe('08:00')
  })

  it('emite o horário ajustado ao clicar nos botões acessíveis', async () => {
    const wrapper = await mountSuspended(HorarioStepper, {
      props: { id: 't-ini', modelValue: '08:00', label: 'Início', campo: 'inicio' },
    })
    await wrapper.find('button[aria-label="Início: 5 minutos a mais"]').trigger('click')
    await wrapper.find('button[aria-label="Início: 5 minutos a menos"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['08:05'], ['07:55']])
  })

  it('campo fim aceita 24:00 como 00:00', async () => {
    const wrapper = await mountSuspended(HorarioStepper, {
      props: { id: 't-fim', modelValue: '23:55', label: 'Término', campo: 'fim' },
    })
    await wrapper.find('button[aria-label="Término: 5 minutos a mais"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['00:00'])
  })
})
