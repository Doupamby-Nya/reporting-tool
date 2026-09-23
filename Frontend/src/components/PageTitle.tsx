/** The heading every step opens with: what this step is, and what it does. */
const PageTitle: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => (
    <header>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-600">{subtitle}</p>}
    </header>
)

export default PageTitle
