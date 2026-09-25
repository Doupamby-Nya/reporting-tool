import { InlineNotice } from "@components/Notice"
import type { FormSchema } from "src/types/reportingType"

/**
 * Which of a regime's templates this filing has to fill.
 *
 * ESMA publishes AIFMD as one workbook holding four templates, and nothing
 * on the workbook says which of them applies to you — the content type
 * decides, and getting it wrong means filing a report the regulator was not
 * expecting. So the rule is stated here, against the value actually chosen.
 */
const TemplateGuide: React.FC<{ schema: FormSchema; values: Record<string, unknown> }> =
    ({ schema, values }) => {
        const rule = schema.template_rule
        if (!rule || !schema.templates) return null

        // The deciding field is addressed as "aif_info.aif_content_type".
        const path = rule.field.split(".")
        let node: unknown = values
        for (const step of path) {
            node = (node as Record<string, unknown> | undefined)?.[step]
        }
        const chosen = node === undefined || node === null ? "" : String(node)
        const required = rule.applies[chosen] ?? []

        return (
            <section className="flex flex-col gap-3 rounded-lg border border-[#1F5FA8]/30
                                bg-[#1F5FA8]/5 p-5">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">
                        Which template this filing fills
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-600">
                        ESMA&apos;s consolidated workbook holds four templates. The{" "}
                        {rule.label.toLowerCase()} decides which of them apply.
                    </p>
                </div>

                {chosen ? (
                    <p className="text-sm text-slate-800">
                        <span className="font-semibold">{chosen}</span>:{" "}
                        {rule.options[chosen] ?? "unknown content type"}
                    </p>
                ) : (
                    <InlineNotice>
                        No {rule.label.toLowerCase()} chosen yet, so the applicable templates cannot be
                        determined. Set it in the AIF file section below.
                    </InlineNotice>
                )}

                <ul className="grid gap-2 sm:grid-cols-2">
                    {Object.entries(schema.templates).map(([name, when]) => {
                        const applies = required.includes(name)
                        return (
                            <li key={name}
                                className={[
                                    "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
                                    applies
                                        ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                                        : "border-slate-200 bg-white text-slate-500",
                                ].join(" ")}>
                                <span aria-hidden="true">{applies ? "✓" : ""}</span>
                                <span>
                                    <span className="font-medium">{name}</span>
                                    <span className="block text-xs opacity-80">{when}</span>
                                </span>
                            </li>
                        )
                    })}
                </ul>
            </section>
        )
    }

export default TemplateGuide
