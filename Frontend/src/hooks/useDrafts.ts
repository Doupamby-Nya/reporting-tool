import { useState } from "react"
import { toast } from "react-toastify"

import { loadDraft, saveDraft } from "@api/reportingApi"
import { FORM_ANCHOR } from "@components/IngestionPanel"

/**
 * Saving and re-opening a module's drafts, and whether the management panel
 * is showing.
 *
 * Every ingestion screen needs the same three things, and a regime that
 * carries no draft support at all is a regime a preparer cannot leave
 * half-finished — which is most of them, most of the time.
 *
 * `onOpened` is what the screen does once a draft has been loaded. Every
 * screen uses it for the same thing — show the form — because re-opening a
 * draft and then being left on a closed form is the one outcome nobody
 * wants: the work is restored but invisible.
 */
export function useDrafts<T>(
    moduleKey: string, apply: (data: T) => void, onOpened?: () => void,
) {
    const [panelOpen, setPanelOpen] = useState(false)
    const [name, setName] = useState("")

    const save = async (data: unknown) => {
        if (!name.trim()) {
            toast.error("Give the draft a name first.")
            return
        }
        try {
            await saveDraft(moduleKey, name.trim(), data)
            toast.success(`Draft “${name.trim()}” saved.`)
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const open = async (draftName: string) => {
        try {
            const draft = await loadDraft<T>(moduleKey, draftName)
            apply(draft.data)
            setName(draft.name)
            onOpened?.()
            toast.success(`Draft “${draftName}” loaded into the form.`)
            // After the form has been laid out with the restored values, so
            // the preparer lands on their work rather than on the panel they
            // just closed.
            window.setTimeout(() => {
                document.getElementById(FORM_ANCHOR)
                    ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }, 0)
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    return { panelOpen, setPanelOpen, name, setName, save, open }
}
