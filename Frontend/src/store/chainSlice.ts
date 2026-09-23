import { createSlice, type PayloadAction } from "@reduxjs/toolkit"

import type { GeneratedFile, ValidationResult } from "src/types/reportingType"

/**
 * What a module's production chain carries from one step to the next.
 *
 * In the Streamlit original each step read the previous one's output out of
 * `st.session_state`: ingestion parses a workbook, the rules engine checks
 * what was parsed, generation builds the filing from it, and the preview
 * edits what generation produced. The steps are separate pages here, so that
 * hand-off has to live somewhere shared — this slice is that place, keyed by
 * module so the eight chains never read each other's data.
 *
 * It is deliberately not persisted: a reload starts an empty chain, exactly
 * as restarting the Streamlit app did, and the server renders the same empty
 * state the client hydrates into.
 */
export type ChainState = {
    /** Whatever the ingestion step produced — shape is the regime's own. */
    ingestion: unknown | null
    /** The regulator's control results, as the rules engine last ran them. */
    validation: ValidationResult | null
    /** The files generation produced, content included. */
    files: GeneratedFile[]
    /**
     * The document the preview step edits. It starts as the generated file's
     * content and only replaces it when the preparer explicitly saves, so a
     * half-finished edit never becomes the official report.
     */
    edited: string | null
    /** Which of `files` the preview is editing. */
    editedKey: string | null
}

const EMPTY: ChainState = {
    ingestion: null, validation: null, files: [], edited: null, editedKey: null,
}

type ChainsState = Record<string, ChainState>

const initialState: ChainsState = {}

const chainOf = (state: ChainsState, moduleKey: string): ChainState => {
    if (!state[moduleKey]) state[moduleKey] = { ...EMPTY }
    return state[moduleKey]
}

const chainSlice = createSlice({
    name: "chains",
    initialState,
    reducers: {
        setIngestion(state, action: PayloadAction<{ module: string; data: unknown }>) {
            chainOf(state, action.payload.module).ingestion = action.payload.data
        },
        setValidation(state, action: PayloadAction<{ module: string; validation: ValidationResult }>) {
            chainOf(state, action.payload.module).validation = action.payload.validation
        },
        setGeneration(state, action: PayloadAction<{
            module: string; files: GeneratedFile[]; validation?: ValidationResult | null
        }>) {
            const chain = chainOf(state, action.payload.module)
            chain.files = action.payload.files
            if (action.payload.validation) chain.validation = action.payload.validation
            // A new generation supersedes any edit made against the old one,
            // which would otherwise be silently kept and previewed as if it
            // were the file that was just produced.
            chain.edited = action.payload.files[0]?.content ?? null
            chain.editedKey = action.payload.files[0]?.key ?? null
        },
        selectFile(state, action: PayloadAction<{ module: string; key: string }>) {
            const chain = chainOf(state, action.payload.module)
            const file = chain.files.find((candidate) => candidate.key === action.payload.key)
            if (!file) return
            chain.editedKey = file.key
            chain.edited = file.content
        },
        setEdited(state, action: PayloadAction<{ module: string; content: string }>) {
            chainOf(state, action.payload.module).edited = action.payload.content
        },
        /** Promote the edit to the official content of the selected file. */
        commitEdit(state, action: PayloadAction<{ module: string }>) {
            const chain = chainOf(state, action.payload.module)
            const file = chain.files.find((candidate) => candidate.key === chain.editedKey)
            if (file && chain.edited !== null) file.content = chain.edited
        },
        resetChain(state, action: PayloadAction<{ module: string }>) {
            state[action.payload.module] = { ...EMPTY }
        },
    },
})

export const {
    setIngestion, setValidation, setGeneration, selectFile, setEdited, commitEdit, resetChain,
} = chainSlice.actions

export const emptyChain = EMPTY

export default chainSlice.reducer
