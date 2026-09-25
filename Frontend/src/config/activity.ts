import type { IconType } from "react-icons"
import {
    FiBookOpen, FiCheckSquare, FiDownload, FiEdit3, FiFileText, FiLogIn, FiSettings, FiShield,
    FiTrash2, FiUploadCloud, FiUserCheck,
} from "react-icons/fi"

import { PITCHES } from "@config/catalogue"
import { MODULES } from "@config/navigation"
import type { ActivityAction } from "src/types/reportingType"

/**
 * How activity is named and drawn. The API records an action key; everything
 * a person reads about it — the breakdown label, the timeline sentence, its
 * icon — is decided here, once.
 */
export type ActionMeta = {
    label: string
    icon: IconType
    /** "Generated 12 filings", "Made 3 review decisions". */
    sentence: (count: number) => string
    /** One subject of this kind, in the timeline's list. */
    unit: [string, string]
}

const plural = (count: number, [one, many]: [string, string]) => `${count} ${count === 1 ? one : many}`

export const ACTIONS: Record<ActivityAction, ActionMeta> = {
    generated: { label: "Filings generated", icon: FiFileText, unit: ["filing", "filings"],
        sentence: (n) => `Generated ${plural(n, ["filing", "filings"])}` },
    reviewed: { label: "Review decisions", icon: FiUserCheck, unit: ["decision", "decisions"],
        sentence: (n) => `Made ${plural(n, ["review decision", "review decisions"])}` },
    validated: { label: "Controls run", icon: FiCheckSquare, unit: ["run", "runs"],
        sentence: (n) => `Ran the controls ${n === 1 ? "once" : `${n} times`}` },
    ingested: { label: "Files ingested", icon: FiUploadCloud, unit: ["file", "files"],
        sentence: (n) => `Ingested ${plural(n, ["file", "files"])}` },
    drafted: { label: "Drafts saved", icon: FiEdit3, unit: ["draft", "drafts"],
        sentence: (n) => `Saved ${plural(n, ["draft", "drafts"])}` },
    deleted: { label: "Drafts deleted", icon: FiTrash2, unit: ["draft", "drafts"],
        sentence: (n) => `Deleted ${plural(n, ["draft", "drafts"])}` },
    consulted: { label: "Texts consulted", icon: FiBookOpen, unit: ["text", "texts"],
        sentence: (n) => `Consulted the regulator's texts ${n === 1 ? "once" : `${n} times`}` },
    downloaded: { label: "Files downloaded", icon: FiDownload, unit: ["file", "files"],
        sentence: (n) => `Downloaded ${plural(n, ["file", "files"])}` },
    configured: { label: "Settings changed", icon: FiSettings, unit: ["change", "changes"],
        sentence: (n) => `Changed the settings ${n === 1 ? "once" : `${n} times`}` },
    signed_in: { label: "Sign-ins", icon: FiLogIn, unit: ["sign-in", "sign-ins"],
        sentence: (n) => `Signed in ${n === 1 ? "once" : `${n} times`}` },
    administered: { label: "Administration", icon: FiShield, unit: ["change", "changes"],
        sentence: (n) => `Made ${plural(n, ["administration change", "administration changes"])}` },
}

export const countOf = (count: number, unit: [string, string]) => plural(count, unit)

/** A module's name and colour; the fund registry and the platform itself
 *  are not modules but are places work happens. */
export function moduleMeta(key: string): { label: string; color: string } {
    const module = MODULES.find((candidate) => candidate.key === key)
    if (module) return { label: module.label, color: PITCHES[key]?.color ?? "#0A2647" }
    if (key === "funds") return { label: "Fund registry", color: "#64748B" }
    return { label: "Platform", color: "#94A3B8" }
}

/** The calendar's five shades, from an empty day to the busiest: the
 *  corporate navy, lightened. */
export const HEAT = ["#E9EEF5", "#BFD3EA", "#7FA7D6", "#2F6BB3", "#0A2647"]
