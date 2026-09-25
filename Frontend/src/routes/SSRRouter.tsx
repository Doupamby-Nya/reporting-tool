import { Navigate, Route, Routes } from "react-router-dom"

import ModuleGate from "@components/ModuleGate"
import { MODULES, REFERENCE_STEP, firstStepOf, type ModuleNav } from "@config/navigation"
import { useCurrentUser } from "@hooks/useCurrentUser"
import ChainLayout from "@layouts/ChainLayout"
import MainLayout from "@layouts/MainLayout"
import Dashboard from "@pages/Dashboard"
import Guide from "@pages/Guide"
import Home from "@pages/Home"
import Login from "@pages/Login"

// Each reporting declares its own pages under pages/<reporting>/: a Home
// page, which is the landing page of /<reporting>, and the steps that are
// particular to it. The steps every reporting shares live in pages/shared/.
import AifmdGeneration from "@pages/aifmd/Generation"
import AifmdHome from "@pages/aifmd/Home"
import AifmdIngestion from "@pages/aifmd/Ingestion"
import AifmdRules from "@pages/aifmd/Rules"
import BclGeneration from "@pages/bcl/Generation"
import BclHome from "@pages/bcl/Home"
import BclIngestion from "@pages/bcl/Ingestion"
import BclRules from "@pages/bcl/Rules"
import EsefHome from "@pages/esef/Home"
import FatcaConfiguration from "@pages/fatca/Configuration"
import FatcaGeneration from "@pages/fatca/Generation"
import FatcaHome from "@pages/fatca/Home"
import FatcaIngestion from "@pages/fatca/Ingestion"
import FatcaNotification from "@pages/fatca/Notification"
import FatcaRules from "@pages/fatca/Rules"
import O41Home from "@pages/o41/Home"
import PriipsConfiguration from "@pages/priips/Configuration"
import PriipsEngine from "@pages/priips/Engine"
import PriipsHome from "@pages/priips/Home"
import PriipsIngestion from "@pages/priips/Ingestion"
import PriipsKid from "@pages/priips/Kid"
import SaqHome from "@pages/saq/Home"
import ControlsAudit from "@pages/shared/ControlsAudit"
import FilingGeneration from "@pages/shared/FilingGeneration"
import Regulation from "@pages/shared/Regulation"
import RulesCatalogue from "@pages/shared/RulesCatalogue"
import WorkbookIngestion from "@pages/shared/WorkbookIngestion"
import XmlPreview from "@pages/shared/XmlPreview"
import UrrHome from "@pages/urr/Home"

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

/** The landing page of each reporting — declared by the reporting itself. */
const HOMES: Record<string, StepComponent> = {
    priips: PriipsHome, fatca: FatcaHome, urr: UrrHome, o41: O41Home,
    esef: EsefHome, aifmd: AifmdHome, saq: SaqHome, bcl: BclHome,
}

/** A bare module URL lands on the reporting's own Home page; a module
 *  without one would fall back to the first step of its chain. */
const landingFor = (module: ModuleNav): React.ReactElement => {
    const Home = HOMES[module.key]
    return Home ? <Home /> : <Navigate to={firstStepOf(module)} replace />
}

const componentFor = (moduleKey: string, step: string): StepComponent =>
    STEPS[moduleKey]?.[step] ?? SHARED[step] ?? Dashboard

/** The dashboard summarises the user's modules; without any there is nothing to show. */
const DashboardGate: React.FC = () => {
    const { me, modules } = useCurrentUser()
    if (!me) return <Navigate to="/login?next=%2Fdashboard" replace />
    return modules.length > 0 ? <Dashboard /> : <Navigate to="/" replace />
}

const SSRRouter: React.FC = () => (
    <Routes>
        <Route path="/" element={<MainLayout />}>
            {/* Public: the home page, the guide and signing in. */}
            <Route index element={<Home />} />
            <Route path="guide" element={<Guide />} />
            <Route path="login" element={<Login />} />
            <Route path="dashboard" element={<DashboardGate />} />

            {MODULES.map((module) => (
                <Route key={module.key} path={module.key}
                    element={<ModuleGate module={module}><ChainLayout module={module} /></ModuleGate>}>
                    <Route index element={landingFor(module)} />
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
