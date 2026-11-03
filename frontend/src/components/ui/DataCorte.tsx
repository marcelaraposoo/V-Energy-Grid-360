import { CalendarCheck } from 'lucide-react'
import { dataCorteGold, formatarData } from '../../utils/periodosDashboard'
import './portal.css'

// Até quando os números valem: o fim da base no contrato da Gold.
export function DataCorte() {
  return (
    <p className="data-corte">
      <CalendarCheck size={13} strokeWidth={1.75} aria-hidden="true" />
      Dados até {formatarData(dataCorteGold)}
    </p>
  )
}
