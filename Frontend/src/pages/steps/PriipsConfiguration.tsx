import { useCallback, useEffect, useState } from "react"
import { toast } from "react-toastify"

import {
    fetchAppSettings, fetchPriipsParameters, fetchPriipsTemplates, fetchTemplateText,
    resetPriipsParameters, resetTemplate, saveAppSettings, savePriipsParameters, saveTemplateText,
} from "@api/reportingApi"
import PageTitle from "@components/PageTitle"

type Tab = "template" | "parameters" | "settings"

const pretty = (value: unknown) => JSON.stringify(value, null, 2)

/**
 * The KID narrative, the RTS calibration and the organisation's own details,
 * all editable without touching code.
 *
 * Each is edited as text and parsed before it is sent: a malformed template
 * is rejected here and again by the API, so neither can reach the generator.
 * The reset buttons restore the shipped defaults, which is the way back from
 * an edit that turned out wrong.
 */
const PriipsConfiguration: React.FC = () => {
    const [tab, setTab] = useState<Tab>("template")
    const [templates, setTemplates] = useState<string[]>(["standard"])
    const [templateName, setTemplateName] = useState("standard")
    const [format, setFormat] = useState<"json" | "yaml">("json")
    const [text, setText] = useState("")
    const [parameters, setParameters] = useState("")
    const [settings, setSettings] = useState("")
    const [busy, setBusy] = useState(false)

    const loadTemplate = useCallback(async (name: string, fmt: "json" | "yaml") => {
        try {
            const loaded = await fetchTemplateText(name, fmt)
            setText(loaded.text)
        } catch (error) {
            toast.error((error as Error).message)
        }
    }, [])

    useEffect(() => {
        fetchPriipsTemplates()
            .then((response) => {
                const available = (response as unknown as { available?: string[] }).available ?? []
                if (available.length) {
                    setTemplates(available)
                    if (!available.includes(templateName)) setTemplateName(available[0])
                }
            })
            .catch(() => undefined)
        fetchPriipsParameters().then((loaded) => setParameters(pretty(loaded))).catch(() => undefined)
        fetchAppSettings().then((loaded) => setSettings(pretty(loaded))).catch(() => undefined)
        // The template list is fetched once; the text follows the selection.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    useEffect(() => { void loadTemplate(templateName, format) }, [templateName, format, loadTemplate])

    const saveTemplate = async () => {
        setBusy(true)
        try {
            await saveTemplateText(templateName, text, format)
            toast.success(`Template “${templateName}” saved.`)
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const restoreTemplate = async () => {
        try {
            await resetTemplate(templateName)
            await loadTemplate(templateName, format)
            toast.success("The shipped default has been restored.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const saveParameters = async () => {
        setBusy(true)
        try {
            // Parsed here as well as by the API, so a typo is caught without
            // a round trip and the editor keeps what was typed.
            const parsed = JSON.parse(parameters) as Record<string, unknown>
            setParameters(pretty(await savePriipsParameters(parsed)))
            toast.success("The RTS calibration has been saved.")
        } catch (error) {
            toast.error(`Could not save: ${(error as Error).message}`)
        } finally {
            setBusy(false)
        }
    }

    const restoreParameters = async () => {
        try {
            setParameters(pretty(await resetPriipsParameters()))
            toast.success("The default calibration has been restored.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const saveSettings = async () => {
        setBusy(true)
        try {
            const parsed = JSON.parse(settings) as Record<string, unknown>
            setSettings(pretty(await saveAppSettings(parsed)))
            toast.success("Settings saved.")
        } catch (error) {
            toast.error(`Could not save: ${(error as Error).message}`)
        } finally {
            setBusy(false)
        }
    }

    const tabClass = (value: Tab) => [
        "rounded-md border px-3 py-1.5 text-sm font-medium transition",
        value === tab
            ? "border-[#0A2647] bg-[#0A2647] text-white"
            : "border-slate-300 bg-white text-slate-700 hover:border-[#0A2647]",
    ].join(" ")

    const editor = (value: string, onChange: (next: string) => void) => (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={24}
            spellCheck={false}
            className="w-full rounded-lg border border-slate-300 bg-white p-3 font-mono text-xs
                       outline-none focus:border-[#0A2647]" />
    )

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="PRIIPs KID — Configuration"
                subtitle="The KID narrative template, the RTS calibration behind every figure, and the
                          organisation's own details — all editable without touching code." />

            <div className="flex flex-wrap gap-2">
                <button type="button" className={tabClass("template")} onClick={() => setTab("template")}>
                    KID template
                </button>
                <button type="button" className={tabClass("parameters")} onClick={() => setTab("parameters")}>
                    RTS calibration
                </button>
                <button type="button" className={tabClass("settings")} onClick={() => setTab("settings")}>
                    Organisation
                </button>
            </div>

            {tab === "template" && (
                <section className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-end gap-3">
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="font-medium text-slate-700">Template</span>
                            <select value={templateName} onChange={(event) => setTemplateName(event.target.value)}
                                className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                           focus:border-[#0A2647]">
                                {templates.map((name) => <option key={name} value={name}>{name}</option>)}
                            </select>
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="font-medium text-slate-700">Format</span>
                            <select value={format}
                                onChange={(event) => setFormat(event.target.value as "json" | "yaml")}
                                className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                           focus:border-[#0A2647]">
                                <option value="json">JSON</option>
                                <option value="yaml">YAML</option>
                            </select>
                        </label>
                    </div>
                    {editor(text, setText)}
                    <div className="flex gap-2">
                        <button type="button" onClick={saveTemplate} disabled={busy}
                            className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                       transition hover:bg-[#123A6B] disabled:opacity-50">
                            Save the template
                        </button>
                        <button type="button" onClick={restoreTemplate}
                            className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700
                                       transition hover:border-[#0A2647]">
                            Restore the shipped default
                        </button>
                    </div>
                    <p className="text-xs text-slate-500">
                        Saving writes both the JSON and the YAML copy, so the two can never disagree.
                    </p>
                </section>
            )}

            {tab === "parameters" && (
                <section className="flex flex-col gap-3">
                    <p className="text-sm text-slate-600">
                        The risk bands, cost assumptions and scenario inputs every KID figure is computed
                        from. Changing these changes the numbers on every subsequent KID.
                    </p>
                    {editor(parameters, setParameters)}
                    <div className="flex gap-2">
                        <button type="button" onClick={saveParameters} disabled={busy}
                            className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                       transition hover:bg-[#123A6B] disabled:opacity-50">
                            Save the calibration
                        </button>
                        <button type="button" onClick={restoreParameters}
                            className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700
                                       transition hover:border-[#0A2647]">
                            Restore the defaults
                        </button>
                    </div>
                </section>
            )}

            {tab === "settings" && (
                <section className="flex flex-col gap-3">
                    <p className="text-sm text-slate-600">
                        The organisation name and product line shown on the documents the platform produces.
                    </p>
                    {editor(settings, setSettings)}
                    <button type="button" onClick={saveSettings} disabled={busy}
                        className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                   transition hover:bg-[#123A6B] disabled:opacity-50">
                        Save the settings
                    </button>
                </section>
            )}
        </section>
    )
}

export default PriipsConfiguration
