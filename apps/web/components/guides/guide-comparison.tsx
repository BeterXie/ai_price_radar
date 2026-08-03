export function GuideComparison({ title, columns, rows }: { title?: string; columns: readonly string[]; rows: readonly (readonly string[])[] }) {
  return (
    <div>
      {title ? <h3 className="text-lg font-semibold">{title}</h3> : null}
      <div className={title ? "mt-4 hidden overflow-x-auto rounded-[14px] border hairline md:block" : "hidden overflow-x-auto rounded-[14px] border hairline md:block"}>
        <table className="w-full min-w-[620px] border-collapse text-left text-sm">
          <thead className="bg-black/[.045]">
            <tr>{columns.map((column) => <th key={column} scope="col" className="border-b hairline px-4 py-3 font-semibold">{column}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${rowIndex}-${row[0] || "row"}`} className="bg-[color:var(--panel)] align-top">
                {row.map((cell, cellIndex) => cellIndex === 0 ? (
                  <th key={`${cellIndex}-${cell}`} scope="row" className="border-b hairline px-4 py-4 font-semibold last:border-b-0">{cell}</th>
                ) : (
                  <td key={`${cellIndex}-${cell}`} className="border-b hairline px-4 py-4 leading-6 last:border-b-0">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={title ? "mt-4 grid gap-3 md:hidden" : "grid gap-3 md:hidden"}>
        {rows.map((row, rowIndex) => (
          <dl key={`${rowIndex}-${row[0] || "row"}`} className="rounded-[12px] border hairline bg-[color:var(--panel)] p-4">
            {columns.map((column, columnIndex) => (
              <div key={column} className="grid gap-1 border-b hairline py-3 first:pt-0 last:border-b-0 last:pb-0">
                <dt className="text-xs font-semibold text-[color:var(--muted)]">{column}</dt>
                <dd className="text-sm leading-6">{row[columnIndex] || "未说明"}</dd>
              </div>
            ))}
          </dl>
        ))}
      </div>
    </div>
  );
}
