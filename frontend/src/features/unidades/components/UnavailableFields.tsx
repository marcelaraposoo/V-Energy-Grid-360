/** Estrutura de apresentação: ausência de consulta não equivale a valor zero. */
export function UnavailableFields({ labels }: { labels: readonly string[] }) {
  return (
    <dl className="ucv-fields">
      {labels.map((label) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <span aria-label="Não disponível">—</span>
          </dd>
        </div>
      ))}
    </dl>
  )
}
