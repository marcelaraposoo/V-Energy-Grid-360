import { useCallback, useEffect, useRef, useState } from 'react'

export type ApiState<T> = {
  data: T | null
  error: Error | null
  loading: boolean
  reload: () => void
}

type Resultado<T> = { chave: string; tentativa: number; data: T | null; error: Error | null }

// Hook para carregar dados de uma tela. Exemplo:
//   const { data, error, loading } = useApi((signal) => api.unidades.visao360(id, signal), [id])
//
// - Chama ao montar e sempre que `deps` mudar (use valores simples: ids, textos, números).
// - Cancela a chamada anterior e ignora respostas atrasadas.
// - `reload()` tenta de novo; durante o reload os dados anteriores continuam disponíveis.
export function useApi<T>(
  carregar: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): ApiState<T> {
  const chave = JSON.stringify(deps)
  const [tentativa, setTentativa] = useState(0)
  const [resultado, setResultado] = useState<Resultado<T> | null>(null)

  // Guarda a versão mais recente da função sem refazer a chamada a cada render.
  const carregarRef = useRef(carregar)
  useEffect(() => {
    carregarRef.current = carregar
  })

  useEffect(() => {
    const controlador = new AbortController()
    Promise.resolve()
      .then(() => carregarRef.current(controlador.signal))
      .then((data) => {
        if (!controlador.signal.aborted) setResultado({ chave, tentativa, data, error: null })
      })
      .catch((erro: unknown) => {
        if (controlador.signal.aborted) return
        const error = erro instanceof Error ? erro : new Error(String(erro))
        setResultado({ chave, tentativa, data: null, error })
      })
    return () => controlador.abort()
  }, [chave, tentativa])

  // Estado derivado: se a resposta guardada não é da chamada atual, ainda está carregando.
  const mesmaChave = resultado !== null && resultado.chave === chave
  const respondeu = mesmaChave && resultado.tentativa === tentativa
  const reload = useCallback(() => setTentativa((n) => n + 1), [])

  return {
    data: mesmaChave ? resultado.data : null,
    error: respondeu ? resultado.error : null,
    loading: !respondeu,
    reload,
  }
}
