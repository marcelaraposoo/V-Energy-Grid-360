import {
  ChartNoAxesCombined,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  ScanLine,
  Sparkles,
  TrendingUpDown,
} from 'lucide-react'
import { matchPath } from 'react-router-dom'

// Somente páginas incluídas nesta etapa. Novas telas entram aqui com sua rota.
export const navigation = [
  {
    group: 'Visão geral',
    items: [{ title: 'Dashboard Executivo', to: '/', icon: LayoutDashboard }],
  },
  {
    group: 'Análises',
    items: [
      { title: 'Análise de Receita', to: '/receita', icon: TrendingUpDown },
      { title: 'Visão 360 da UC', to: '/uc', icon: ScanLine },
      { title: 'Qualidade do Serviço', to: '/qualidade', icon: Gauge },
    ],
  },
  {
    group: 'Operações',
    items: [
      {
        title: 'Fila e Ordens de Inspeção',
        to: '/inspecoes/ordens',
        icon: ClipboardList,
      },
    ],
  },
  {
    group: 'Inteligência',
    items: [{ title: 'Assistente IA', to: '/assistente', icon: Sparkles }],
  },
]

export function getCurrentPage(pathname: string) {
  for (const section of navigation) {
    const page = section.items.find((item) =>
      matchPath({ path: item.to, end: item.to === '/' }, pathname),
    )
    if (page) return { ...page, group: section.group }
  }
  return {
    title: 'Página não encontrada',
    group: 'Portal',
    icon: ChartNoAxesCombined,
    to: pathname,
  }
}