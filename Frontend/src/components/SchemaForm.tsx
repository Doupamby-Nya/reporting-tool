import { useState } from "react"

import FieldHelp from "@components/FieldHelp"
import CodeLabel from "@components/CodeLabel"
import { splitCode } from "@components/splitCode"
import RepeatingBlock from "@components/RepeatingBlock"
import type { FormField, FormSchema, FormSection } from "src/types/reportingType"

/**
 * Renders a regime's capture form from the schema the API serves.
 *
 * The form is not written here, because it is not this layer's to decide:
 * every field exists because a regulator asks for it, and the generator
 * reads it back under an exact name. Both come from the engine, so the
 * client's job is to render whatever it is handed — which is what stops the
 * screen and the filing drifting apart.
 *
 * Values are held as strings, as inputs hold them; the generation step
 * converts them at the boundary, where an empty field can be told from a
 * reported zero.
 */
export type FormValues = Record<string, unknown>

const INPUT = "rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-[#0A2647]"

const inputType = (type: string) =>
    type === "date" ? "date" : type === "number" || type === "integer" ? "number" : "text"

/** What a field of each type takes, said in the preparer's words. */
const EXPECTS: Record<string, string> = {
    date: "a date",
    number: "an amount",
    integer: "a whole number",
    boolean: "yes or no",
    select: "one of the regulator's own codes",
    country: "an ISO 3166 country code",
    text: "text",
}

/**
 * A field's caption: the regulator's code first, then its wording, then the
 * help marker. The code leads because that is how the regulator's own
 * instructions are indexed — a preparer checking a screen against the
 * rulebook looks for the number.
 *
 * Many fields carry their code inside `hint` (an item number, an XBRL
 * concept, an EDIFACT wire code); where the hint is short enough to be a
 * code it is promoted to the front, and where it is a path it stays in the
 * help instead of cluttering the line.
 */
const codeOf = (field: FormField): string | undefined => {
    const hint = field.hint?.trim()
    if (!hint) return undefined
    return hint.length <= 12 && !hint.includes(" ") ? hint : undefined
}

const Caption: React.FC<{ field: FormField; note?: string }> = ({ field, note }) => {
    const split = splitCode(field.label)
    const code = codeOf(field) ?? split.code ?? undefined
    return (
        <span className="flex flex-1 items-start gap-1.5 font-medium leading-snug text-slate-700">
            {code && <span className="font-mono text-xs text-[#1F5FA8]">{code}</span>}
            <span>{split.text}</span>
            <FieldHelp code={code} label={field.label} target={code ? undefined : field.hint}
                expects={EXPECTS[field.type] ?? "text"} note={note} />
        </span>
    )
}

const Scalar: React.FC<{
    field: FormField
    value: unknown
    onChange: (next: unknown) => void
    countries: [string, string][]
}> = ({ field, value, onChange, countries }) => {
    if (field.type === "boolean") {
        return (
            <label className="flex h-full items-end gap-2 py-2 text-sm">
                <input type="checkbox" checked={value === true || value === "true"}
                    onChange={(event) => onChange(event.target.checked)} />
                <span className="text-slate-700">{field.label}</span>
            </label>
        )
    }

    const options: [string, string][] = field.type === "country"
        ? countries
        : Object.entries(field.options ?? {})

    return (
        <label className="flex h-full flex-col gap-1 text-sm">
            <Caption field={field}
                note={options.length ? `${options.length} code(s) available.` : undefined} />
            {options.length > 0 ? (
                <select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}
                    className={INPUT}>
                    <option value="">Select</option>
                    {options.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                </select>
            ) : (
                <input type={inputType(field.type)} value={String(value ?? "")}
                    onChange={(event) => onChange(event.target.value)} className={INPUT} />
            )}
        </label>
    )
}

/**
 * A line of a regulator's schedule is either a figure in its own right or an
 * "of which" under the one above it, and the wording alone does not say
 * which — the labels differ by an ellipsis. So a line that has a breakdown
 * beneath it is shaded and set in medium, and its breakdown is indented.
 * Without that the two read as one flat list and a preparer cannot tell a
 * total from a component of it.
 */
const isBreakdownOf = (field: FormField): boolean => {
    // Most labels lead with the regulator's item number ("6011 \u2014 of which
    // from Luxembourg"), so the marker is looked for after it. The marker
    // itself is the regulator's own wording \u2014 "of which" \u2014 or an ellipsis or
    // indentation where a schedule uses those instead.
    const wording = field.label.replace(/^\s*[\w.-]+\s*[\u2014\u2013-]\s*/, "")
    return /^[\s\u2026.]/.test(wording) || /^of which/i.test(wording.trim())
}

/** An amount line: the label on the left, the figure on the right, as the
 *  regulator's own schedules are laid out. */
const Amount: React.FC<{
    field: FormField
    value: unknown
    onChange: (next: string) => void
    consolidating?: boolean
    child?: boolean
}> = ({ field, value, onChange, consolidating = false, child = false }) => (
    <label className={[
        "flex items-center justify-between gap-4 border-b py-1.5 text-sm",
        consolidating
            ? "border-slate-200 bg-slate-100/70 px-2 font-medium text-slate-900"
            : "border-slate-100",
        child ? "pl-6" : "",
    ].join(" ")}>
        <Caption field={field}
            note="Leave empty for 'not reported'. That is not the same as reporting a zero." />
        <input type="number" step="0.01" value={String(value ?? "")} placeholder="Not reported"
            onChange={(event) => onChange(event.target.value)}
            className="w-44 shrink-0 rounded-md border border-slate-300 px-2 py-1 text-right text-sm
                       font-normal outline-none focus:border-[#0A2647]" />
    </label>
)

/** Renders a run of amount lines, shading each one that has a breakdown. */
const Amounts: React.FC<{
    fields: FormField[]
    read: (key: string) => unknown
    write: (key: string, next: string) => void
}> = ({ fields, read, write }) => (
    <div className="flex flex-col">
        {fields.map((field, index) => {
            const child = isBreakdownOf(field)
            const consolidating = !child && isBreakdownOf(fields[index + 1] ?? field)
            return (
                <Amount key={field.key} field={field} consolidating={consolidating} child={child}
                    value={read(field.key)} onChange={(next) => write(field.key, next)} />
            )
        })}
    </div>
)

const Collapsible: React.FC<{ title: string; count?: number; children: React.ReactNode }> =
    ({ title, count, children }) => {
        const [open, setOpen] = useState(true)
        return (
            <div className="rounded-md border border-slate-200">
                <button type="button" onClick={() => setOpen(!open)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm
                               font-medium text-slate-800 hover:bg-slate-50">
                    <span>{title}{count !== undefined && <span className="ml-2 text-xs text-slate-500">
                        {count} field(s)</span>}</span>
                    <span className="text-slate-400">{open ? "−" : "+"}</span>
                </button>
                {open && <div className="border-t border-slate-100 p-3">{children}</div>}
            </div>
        )
    }

const SchemaForm: React.FC<{
    schema: FormSchema
    values: FormValues
    onChange: (next: FormValues) => void
    countries?: [string, string][]
}> = ({ schema, values, onChange, countries = [] }) => {
    /**
     * A section's key says where its values live in the submission: "" is
     * the top level, `aifm_info` a nested object, `aifm_info.assumptions` a
     * list inside one. Dotted paths are what let a regime with two nested
     * dictionaries — AIFMD — use the same renderer as a flat one.
     */
    const at = (path: string[]): Record<string, unknown> => {
        let node: Record<string, unknown> = values
        for (const step of path) {
            node = (node[step] as Record<string, unknown>) ?? {}
        }
        return node
    }

    const put = (path: string[], key: string, next: unknown): FormValues => {
        if (path.length === 0) return { ...values, [key]: next }
        const [head, ...rest] = path
        const branch = (values[head] as Record<string, unknown>) ?? {}
        let updated: Record<string, unknown>
        if (rest.length === 0) {
            updated = { ...branch, [key]: next }
        } else {
            const inner = (branch[rest[0]] as Record<string, unknown>) ?? {}
            updated = { ...branch, [rest[0]]: { ...inner, [key]: next } }
        }
        return { ...values, [head]: updated }
    }

    const pathOf = (section: FormSection) => section.key ? section.key.split(".") : []

    const read = (section: FormSection, key: string): unknown => at(pathOf(section))[key]

    const write = (section: FormSection, key: string, next: unknown) =>
        onChange(put(pathOf(section), key, next))

    const rowsOf = (section: FormSection): Record<string, unknown>[] => {
        const path = pathOf(section)
        const leaf = path[path.length - 1]
        const parent = at(path.slice(0, -1))
        return (parent[leaf] as Record<string, unknown>[]) ?? []
    }

    const setRows = (section: FormSection, rows: Record<string, unknown>[]) => {
        const path = pathOf(section)
        onChange(put(path.slice(0, -1), path[path.length - 1], rows))
    }

    return (
        <div className="flex flex-col gap-6">
            {schema.sections.map((section) => (
                <section key={section.key || section.title}
                    className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                    {section.kind !== "table" && (
                        <div>
                            <h2 className="text-sm font-semibold text-slate-900">{section.title}</h2>
                            {section.hint && (
                                <p className="mt-0.5 text-xs text-slate-500">{section.hint}</p>
                            )}
                        </div>
                    )}

                    {section.kind === "fields" && (
                        <div className="grid gap-4 md:grid-cols-3">
                            {(section.fields ?? []).map((field) => (
                                <Scalar key={field.key} field={field} countries={countries}
                                    value={read(section, field.key)}
                                    onChange={(next) => write(section, field.key, next)} />
                            ))}
                        </div>
                    )}

                    {section.kind === "amounts" && (
                        <div className="flex flex-col gap-3">
                            {section.groups
                                ? section.groups.map((group) => (
                                    <Collapsible key={group.title} title={group.title}
                                        count={group.fields.length}>
                                        <Amounts fields={group.fields}
                                            read={(key) => read(section, key)}
                                            write={(key, next) => write(section, key, next)} />
                                    </Collapsible>
                                ))
                                : (
                                    <Amounts fields={section.fields ?? []}
                                        read={(key) => read(section, key)}
                                        write={(key, next) => write(section, key, next)} />
                                )}
                        </div>
                    )}

                    {section.kind === "texts" && (
                        <div className="flex flex-col gap-4">
                            {(section.fields ?? []).map((field) => (
                                <label key={field.key} className="flex h-full flex-col gap-1 text-sm">
                                    <Caption field={field} note="Reported as one tagged text block." />
                                    <textarea rows={4} value={String(read(section, field.key) ?? "")}
                                        onChange={(event) => write(section, field.key, event.target.value)}
                                        className={`${INPUT} font-normal`} />
                                </label>
                            ))}
                        </div>
                    )}

                    {section.kind === "questions" && (
                        <div className="flex flex-col gap-3">
                            {(section.groups ?? []).map((group) => (
                                <Collapsible key={group.title} title={group.title}
                                    count={group.fields.length}>
                                    <div className="flex flex-col gap-4">
                                        {group.fields.map((field) => (
                                            <div key={field.key} className="flex flex-col gap-1">
                                                <p className="text-sm text-slate-800"><CodeLabel label={field.label} /></p>
                                                {field.hint && (
                                                    <p className="text-xs italic text-slate-500">
                                                        {field.hint}
                                                    </p>
                                                )}
                                                <div className="flex flex-wrap gap-2">
                                                    {(section.choices ?? []).map((choice) => {
                                                        const active = read(section, field.key) === choice
                                                        return (
                                                            <button key={choice} type="button"
                                                                onClick={() =>
                                                                    write(section, field.key, choice)}
                                                                className={[
                                                                    "rounded-md border px-3 py-1 text-xs",
                                                                    "font-medium transition",
                                                                    active
                                                                        ? "border-[#0A2647] bg-[#0A2647] text-white"
                                                                        : "border-slate-300 text-slate-700 hover:border-[#0A2647]",
                                                                ].join(" ")}>
                                                                {choice}
                                                            </button>
                                                        )
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </Collapsible>
                            ))}
                        </div>
                    )}

                    {section.kind === "table" && (
                        <RepeatingBlock title={section.title} hint={section.hint}
                            columns={section.columns ?? []} rows={rowsOf(section)}
                            countries={countries}
                            onChange={(rows) => setRows(section, rows)} />
                    )}

                </section>
            ))}
        </div>
    )
}

export default SchemaForm
