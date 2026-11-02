import assert from 'node:assert/strict'
import test from 'node:test'
import { formatarData, formatarDataHora } from '../src/features/unidades/formatters.ts'
import { fmtDataHora } from '../src/utils/format.ts'

test('datas com horário aceitam ISO e espaço como separador', () => {
  for (const valor of ['2025-07-01T14:30:00', '2025-07-01 14:30:00', '2025-07-01T14:30:00.000-03:00']) {
    assert.equal(formatarData(valor), '01/07/2025')
    assert.equal(formatarDataHora(valor), '01/07/2025 às 14:30')
    assert.equal(fmtDataHora(valor), '01/07/2025 14:30')
  }
})

test('datas sem horário e competências continuam formatadas', () => {
  assert.equal(formatarData('2026-06-30'), '30/06/2026')
  assert.equal(formatarDataHora('2026-06-30'), '30/06/2026')
  assert.equal(formatarData('2026-06'), '06/2026')
  assert.equal(formatarData(null), 'Não disponível')
})
