import type { TipoIrregularidade } from '../../api'

export const TIPOS: { valor: TipoIrregularidade; rotulo: string }[] = [
  { valor: 'fraude', rotulo: 'Fraude no medidor' },
  { valor: 'ligacao_clandestina', rotulo: 'Ligação clandestina ("gato")' },
  { valor: 'erro_leitura', rotulo: 'Erro de leitura' },
  { valor: 'erro_cadastro', rotulo: 'Erro de cadastro' },
  { valor: 'nenhuma', rotulo: 'Nenhuma irregularidade encontrada' },
]