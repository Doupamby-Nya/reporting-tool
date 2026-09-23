import { Navigate, Route, Routes } from "react-router-dom"

import { MODULES, REFERENCE_STEP, firstStepOf } from "@config/navigation"
import ChainLayout from "@layouts/ChainLayout"
import MainLayout from "@layouts/MainLayout"
import Dashboard from "@pages/Dashboard"
import Guide from "@pages/Guide"

import AifmdGeneration from "@pages/steps/AifmdGeneration"
import AifmdIngestion from "@pages/steps/AifmdIngestion"
import AifmdRules from "@pages/steps/AifmdRules"
import BclGeneration from "@pages/steps/BclGeneration"
import BclIngestion from "@pages/steps/BclIngestion"
import BclRules from "@pages/steps/BclRules"
import ControlsAudit from "@pages/steps/ControlsAudit"
import FatcaConfiguration from "@pages/steps/FatcaConfiguration"
import FatcaGeneration from "@pages/steps/FatcaGeneration"
import FatcaIngestion from "@pages/steps/FatcaIngestion"
import FatcaNotification from "@pages/steps/FatcaNotification"
import FatcaRules from "@pages/steps/FatcaRules"
import FilingGeneration from "@pages/steps/FilingGeneration"
import PriipsConfiguration from "@pages/steps/PriipsConfiguration"
import PriipsEngine from "@pages/steps/PriipsEngine"
import PriipsIngestion from "@pages/steps/PriipsIngestion"
import PriipsKid from "@pages/steps/PriipsKid"
import Regulation from "@pages/steps/Regulation"
import RulesCatalogue from "@pages/steps/RulesCatalogue"
import WorkbookIngestion from "@pages/steps/WorkbookIngestion"
import XmlPreview from "@pages/steps/XmlPreview"

/**
 * Every step of every module's production chain is a route, generated from
 * the navigation config so the tab bar, the side panel and the routes cannot
 * drift apart.
 *
 * Most steps are the platform's shared layers and are served by one
 * component whatever module opens them — controls & audit, the regulatory
 * reference, the preview. The rest are module-specific, and `STEPS` names
 * those exceptions; anything a module does not override falls back to the
 * shared component for that step.
 */
type StepComponent = React.ComponentType

const SHARED: Record<string, StepComponent> = {
    ingestion: WorkbookIngestion,
    rules: RulesCatalogue,
    generation: FilingGeneration,
    preview: XmlPreview,
    controls: ControlsAudit,
    regulation: Regulation,
}

const STEPS: Record<string, Record<string, StepComponent>> = {
    priips: {
        ingestion: PriipsIngestion,
        engine: PriipsEngine,
        generation: PriipsKid,
        configuration: PriipsConfiguration,
    },
    fatca: {
        ingestion: FatcaIngestion,
        rules: FatcaRules,
        generation: FatcaGeneration,
        notification: FatcaNotification,
        configuration: FatcaConfiguration,
    },
    aifmd: {
        ingestion: AifmdIngestion,
        rules: AifmdRules,
        generation: AifmdGeneration,
    },
    bcl: {
        ingestion: BclIngestion,
        rules: BclRules,
        generation: BclGeneration,
    },
}

const componentFor = (moduleKey: string, step: string): StepComponent =>
    STEPS[moduleKey]?.[step] ?? SHARED[step] ?? Dashboard

const SSRRouter: React.FC = () => (
    <Routes>
        <Route path="/" element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="guide" element={<Guide />} />

            {MODULES.map((module) => (
                <Route key={module.key} path={module.key} element={<ChainLayout module={module} />}>
                    {/* A bare module URL lands on the first step of its chain. */}
                    <Route index element={<Navigate to={firstStepOf(module)} replace />} />
                    {/* The chain, plus the regulatory reference — which is
                        reachable from the module but is not a step of it. */}
                    {[...module.steps, REFERENCE_STEP].map((step) => {
                        const Step = componentFor(module.key, step.path)
                        return <Route key={step.path} path={step.path} element={<Step />} />
                    })}
                </Route>
            ))}

            {/* Anything else is a dead end rather than a blank shell. */}
            <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
    </Routes>
)

export default SSRRouter
