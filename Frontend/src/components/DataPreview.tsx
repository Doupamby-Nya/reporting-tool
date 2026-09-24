/**
 * Shows what a workbook parsed into.
 *
 * Each regime names its parsed parts differently — a header and share
 * classes for U 1.1, an entity and its facts for ESEF — so this renders the
 * shape rather than a fixed set of fields: a list of records becomes a
 * table, a mapping becomes a field/value list, and a list of strings becomes
 * the errors the parser raised. The preparer sees exactly what the generator
 * will be given, which is the point of an ingestion step.
 */

const titleOf = (key: string) =>
    key.replace(/_/g, " ").replace(/^./, (character) => character.toUpperCase())

const asText = (value: unknown): string => {
    if (value === null || value === undefined || value === "") return ""
    if (typeof value === "object") return JSON.stringify(value)
    return String(value)
}

const RecordTable: React.FC<{ rows: Record<string, unknown>[] }> = ({ rows }) => {
    // The union of every row's keys, so a row missing a field still lines up
    // under the right column instead of shifting the table.
    const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))))
    return (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>{columns.map((column) => <th key={column} className="px-3 py-2">{titleOf(column)}</th>)}</tr>
                </thead>
                <tbody>
                    {rows.map((row, index) => (
                        <tr key={index} className="border-t border-slate-100">
                            {columns.map((column) => (
                                <td key={column} className="px-3 py-2 text-slate-700">{asText(row[column])}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

const FieldList: React.FC<{ value: Record<string, unknown> }> = ({ value }) => (
    <dl className="grid gap-x-8 gap-y-1 rounded-lg border border-slate-200 bg-white p-4 text-sm sm:grid-cols-2">
        {Object.entries(value).map(([field, fieldValue]) => (
            <div key={field} className="flex justify-between gap-4 border-b border-slate-100 py-1">
                <dt className="text-slate-600">{titleOf(field)}</dt>
                <dd className="text-right font-medium text-slate-900">{asText(fieldValue)}</dd>
            </div>
        ))}
    </dl>
)

const Section: React.FC<{ name: string; value: unknown }> = ({ name, value }) => {
    if (Array.isArray(value)) {
        if (value.length === 0) {
            return (
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    No {titleOf(name).toLowerCase()} in this workbook.
                </p>
            )
        }
        if (value.every((item) => typeof item === "string")) {
            // A list of strings is what every parser returns its problems in.
            return (
                <ul className="flex flex-col gap-1">
                    {(value as string[]).map((message, index) => (
                        <li key={index} className="rounded-md border border-red-200 bg-red-50 px-3 py-2
                                                   text-sm text-red-800">
                            {message}
                        </li>
                    ))}
                </ul>
            )
        }
        return <RecordTable rows={value as Record<string, unknown>[]} />
    }
    if (value && typeof value === "object") return <FieldList value={value as Record<string, unknown>} />
    return <p className="text-sm text-slate-700">{asText(value)}</p>
}

const DataPreview: React.FC<{ data: Record<string, unknown> }> = ({ data }) => (
    <div className="flex flex-col gap-5">
        {Object.entries(data).map(([name, value]) => (
            <section key={name} className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold text-slate-900">{titleOf(name)}</h3>
                <Section name={name} value={value} />
            </section>
        ))}
    </div>
)

export default DataPreview
