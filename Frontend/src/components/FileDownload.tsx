import type { GeneratedFile } from "src/types/reportingType"
import { SchemaBadge } from "@components/ValidationReport"

/**
 * A produced filing, offered as a download.
 *
 * The API returns the document as text rather than a stream, so the browser
 * builds the file itself. That keeps the filename the regulator's naming
 * convention requires — a name the regulator rejects the filing over if it
 * is wrong — under the API's control rather than the browser's.
 */
const FileDownload: React.FC<{ file: GeneratedFile }> = ({ file }) => {
    const download = () => {
        const blob = new Blob([file.content], { type: "application/xml;charset=utf-8" })
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement("a")
        anchor.href = url
        anchor.download = file.filename
        anchor.click()
        URL.revokeObjectURL(url)
    }

    return (
        <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="font-semibold text-slate-900">{file.label}</p>
                    <p className="truncate font-mono text-xs text-slate-500">{file.filename}</p>
                    {typeof file.record_count === "number" && (
                        <p className="mt-1 text-xs text-slate-500">
                            {file.record_count} reporting {file.record_count === 1 ? "record" : "records"}
                        </p>
                    )}
                </div>
                <button type="button" onClick={download}
                    className="shrink-0 rounded-md bg-[#0A2647] px-4 py-2 text-sm font-medium text-white
                               transition hover:bg-[#123A6B]">
                    Download
                </button>
            </div>
            <SchemaBadge result={file.schema_validation} label={file.label} />
        </div>
    )
}

export default FileDownload
