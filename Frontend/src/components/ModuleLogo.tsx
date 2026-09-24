import { PITCHES } from "@config/catalogue"

/**
 * A module's logo: its monogram on a hexagon of its own colour. Drawn rather
 * than shipped as images, so a new module gets one by adding a line to the
 * catalogue.
 */
const ModuleLogo: React.FC<{ moduleKey: string; size?: number }> = ({ moduleKey, size = 56 }) => {
    const pitch = PITCHES[moduleKey]
    const color = pitch?.color ?? "#0A2647"
    const monogram = pitch?.monogram ?? moduleKey.toUpperCase()
    const fontSize = monogram.length > 3 ? 17 : 21
    const id = `logo-${moduleKey}`
    return (
        <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={`${monogram} logo`}
            className="shrink-0">
            <defs>
                <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor={color} />
                    <stop offset="100%" stopColor={color} stopOpacity="0.72" />
                </linearGradient>
            </defs>
            <path d="M32 3 L57 17.5 L57 46.5 L32 61 L7 46.5 L7 17.5 Z" fill={`url(#${id})`} />
            <path d="M32 3 L57 17.5 L32 32 L7 17.5 Z" fill="#ffffff" fillOpacity="0.12" />
            <text x="32" y="33" textAnchor="middle" dominantBaseline="central" fill="#ffffff"
                fontSize={fontSize} fontWeight="800" fontFamily="inherit" letterSpacing="-0.5">
                {monogram}
            </text>
        </svg>
    )
}

export default ModuleLogo
