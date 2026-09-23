import type { Issue, SchemaResult, ValidationResult } from "src/types/reportingType"

/**
 * The two gates a filing passes before it can be downloaded: the regulator's
 * business rules, then its XML schema.
 *
 * Errors and warnings are kept visually distinct because they mean different
 * things — an error would have the filing rejected, a warning is something
 * the regulator flags but accepts. Each finding shows its own control code,
 * which is how a preparer looks the rule up in the published rule set.
 */

const LEVEL_STYLES: Record<Issue["level"], string> = {
    error: "border-red-300 bg-red-50 text-red-900",
    warning: "border-amber-300 bg-amber-50 text-amber-900",
}

export const IssueList: React.FC<{ issues: Issue[] }> = ({ issues }) => (
    <ul className="flex flex-col gap-2">
        {issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`}
                className={`rounded-md border px-3 py-2 text-sm ${LEVEL_STYLES[issue.level]}`}>
                <span className="font-semibold">{issue.code}</span>
                <span className="mx-2 opacity-40">—</span>
                <span>{issue.message}</span>
            </li>
        ))}
    </ul>
)

export const SchemaBadge: React.FC<{ result: SchemaResult; label: string }> = ({ result, label }) => {
    if (!result.available) {
        return (
            <p className="rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                {label}: schema validation is unavailable on the server ({result.detail ?? "lxml is not installed"}).
            </p>
        )
    }
    if (result.valid) {
        return (
            <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                {label}: valid against the regulator's official XSD schema.
            </p>
        )
    }
    return (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
            <p className="font-semibold">
                {label} is not valid against the official schema. Do not submit it — please report this.
            </p>
            <ul className="mt-2 list-disc pl-5 font-mono text-xs">
                {result.errors.slice(0, 10).map((error, index) => <li key={index}>{error}</li>)}
            </ul>
        </div>
    )
}

const ValidationReport: React.FC<{ validation: ValidationResult }> = ({ validation }) => {
    const { errors, warnings } = validation
    if (!errors.length && !warnings.length) {
        return (
            <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                Every implemented control passes.
            </p>
        )
    }
    return (
        <div className="flex flex-col gap-3">
            {errors.length > 0 && (
                <section>
                    <h4 className="mb-2 text-sm font-semibold text-red-900">
                        {errors.length} blocking {errors.length === 1 ? "control" : "controls"} — the filing
                        would be rejected
                    </h4>
                    <IssueList issues={errors} />
                </section>
            )}
            {warnings.length > 0 && (
                <section>
                    <h4 className="mb-2 text-sm font-semibold text-amber-900">
                        {warnings.length} {warnings.length === 1 ? "warning" : "warnings"} — accepted, but flagged
                    </h4>
                    <IssueList issues={warnings} />
                </section>
            )}
        </div>
    )
}

export default ValidationReport
