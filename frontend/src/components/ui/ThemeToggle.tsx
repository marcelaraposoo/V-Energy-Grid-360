import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

export function ThemeToggle() {
  const [tema, setTema] = useState(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  )
  const descricao = tema === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'

  useEffect(() => {
    document.documentElement.dataset.theme = tema
    try {
      localStorage.setItem('v-energy-theme', tema)
    } catch {
      // A troca de tema funciona mesmo sem persistir a preferência.
    }
  }, [tema])

  return (
    <button
      className="icon-button"
      type="button"
      aria-label={descricao}
      title={descricao}
      onClick={() => setTema(tema === 'dark' ? 'light' : 'dark')}
    >
      {tema === 'dark' ? (
        <Sun size={20} aria-hidden="true" />
      ) : (
        <Moon size={20} aria-hidden="true" />
      )}
    </button>
  )
}
