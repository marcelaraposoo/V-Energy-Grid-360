import { useState } from 'react'
import { PageHeader } from '../../components/ui/PageHeader'
import { FilaTab } from './FilaTab'
import { OrdensTab } from './OrdensTab'
import '../../components/ui/portal.css'

type Aba = 'fila' | 'ordens'

export function OrdensPage() {
  const [aba, setAba] = useState<Aba>('fila')
  // Muda sempre que uma ordem é criada na fila, para a lista de ordens recarregar.
  const [versao, setVersao] = useState(0)

  return (
    <>
      <PageHeader
        eyebrow="OPERAÇÕES · PERDAS"
        title="Fila e Ordens de Inspeção"
        description="Escolha as unidades mais promissoras, gere as ordens, acompanhe o campo e registre o que foi encontrado."
      />
      <div className="tabs" role="tablist" aria-label="Seções de inspeção">
        <button
          type="button"
          role="tab"
          id="aba-fila"
          className="tab"
          aria-selected={aba === 'fila'}
          aria-controls="painel-fila"
          onClick={() => setAba('fila')}
        >
          Fila de suspeitas
        </button>
        <button
          type="button"
          role="tab"
          id="aba-ordens"
          className="tab"
          aria-selected={aba === 'ordens'}
          aria-controls="painel-ordens"
          onClick={() => setAba('ordens')}
        >
          Ordens
        </button>
      </div>
      <div role="tabpanel" id="painel-fila" aria-labelledby="aba-fila" hidden={aba !== 'fila'}>
        {aba === 'fila' && <FilaTab onOrdemCriada={() => setVersao((v) => v + 1)} />}
      </div>
      <div role="tabpanel" id="painel-ordens" aria-labelledby="aba-ordens" hidden={aba !== 'ordens'}>
        {aba === 'ordens' && <OrdensTab versao={versao} />}
      </div>
    </>
  )
}
