/**
 * The heading every step opens with: the module it belongs to, what this step
 * is, and what it does.
 */
const PageTitle: React.FC<{ title: string; eyebrow?: string; subtitle?: string }> = ({ title, eyebrow, subtitle }) => (
    <header>
        {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-wide text-[#1F5FA8]">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-600">{subtitle}</p>}
    </header>
)

export default PageTitle
