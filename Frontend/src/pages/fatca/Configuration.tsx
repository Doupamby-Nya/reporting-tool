import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { fetchPreparers, savePreparers } from "@api/reportingApi"
import Notice from "@components/Notice"
import PageTitle from "@components/PageTitle"

type Preparers = Record<string, Record<string, string>>

/**
 * The preparer records a return can be filed under — the depositor point of
 * contact the tax authority corresponds with.
 *
 * The fields a record carries are whatever the reporting engine expects, so
 * they are edited as they come rather than fixed in a form here: adding a
 * field the engine starts to need must not require changing this screen.
 */
const FatcaConfiguration: React.FC = () => {
    const [preparers, setPreparers] = useState<Preparers>({})
    const [selected, setSelected] = useState("")
    const [newName, setNewName] = useState("")
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        fetchPreparers()
            .then((found) => {
                setPreparers(found)
                const names = Object.keys(found)
                if (names.length) setSelected(names[0])
            })
            .catch((error: Error) => toast.error(error.message))
    }, [])

    const names = Object.keys(preparers)
    const record = preparers[selected] ?? {}

    const setField = (field: string, value: string) =>
        setPreparers((current) => ({
            ...current, [selected]: { ...current[selected], [field]: value },
        }))

    const add = () => {
        const name = newName.trim()
        if (!name) return toast.error("Give the preparer a name first.")
        if (preparers[name]) return toast.error(`“${name}” already exists.`)
        // A new record starts with the same fields as an existing one, so a
        // second preparer is never missing something the first needed.
        const shape = names.length ? Object.keys(preparers[names[0]]) : ["name", "email", "phone"]
        setPreparers((current) => ({
            ...current, [name]: Object.fromEntries(shape.map((field) => [field, ""])),
        }))
        setSelected(name)
        setNewName("")
    }

    const remove = (name: string) => {
        setPreparers((current) => {
            const next = { ...current }
            delete next[name]
            return next
        })
        setSelected((current) => (current === name ? "" : current))
    }

    const save = async () => {
        setBusy(true)
        try {
            setPreparers(await savePreparers(preparers))
            toast.success("Preparers saved.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow="FATCA & CRS" title="Configuration"
                subtitle="The preparer records a return can be filed under. A return names one of these;
                          it cannot name a contact that is not on file." />

            <div className="flex flex-wrap items-end gap-3">
                <input value={newName} onChange={(event) => setNewName(event.target.value)}
                    placeholder="Name a new preparer"
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none
                               focus:border-[#0A2647]" />
                <button type="button" onClick={add}
                    className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                               text-[#0A2647] transition hover:bg-slate-100">
                    Add
                </button>
                <button type="button" onClick={save} disabled={busy}
                    className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white transition
                               hover:bg-[#123A6B] disabled:opacity-50">
                    {busy ? "Saving…" : "Save all preparers"}
                </button>
            </div>

            {names.length === 0 ? (
                <Notice eyebrow="Configuration" title="No preparer is configured">
                    A return cannot be generated until at least one exists.
                </Notice>
            ) : (
                <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
                    <div className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-3">
                        {names.map((name) => (
                            <div key={name} className="flex items-center gap-1">
                                <button type="button" onClick={() => setSelected(name)}
                                    className={[
                                        "flex-1 rounded-md px-3 py-2 text-left text-sm font-medium transition",
                                        name === selected
                                            ? "bg-[#0A2647] text-white"
                                            : "text-slate-700 hover:bg-slate-100",
                                    ].join(" ")}>
                                    {name}
                                </button>
                                <button type="button" onClick={() => remove(name)}
                                    aria-label={`Remove ${name}`}
                                    className="px-2 text-xs text-slate-400 hover:text-red-700">×</button>
                            </div>
                        ))}
                    </div>

                    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                        <h2 className="text-sm font-semibold text-slate-900">{selected || "No preparer selected"}</h2>
                        {Object.entries(record).map(([field, value]) => (
                            <label key={field} className="flex flex-col gap-1 text-sm">
                                <span className="font-medium text-slate-700">
                                    {field.replace(/_/g, " ")}
                                </span>
                                <input value={value} onChange={(event) => setField(field, event.target.value)}
                                    className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                               focus:border-[#0A2647]" />
                            </label>
                        ))}
                    </div>
                </div>
            )}
        </section>
    )
}

export default FatcaConfiguration
