import { useOutletContext } from "react-router-dom"
import { useDispatch, useSelector } from "react-redux"

import type { ModuleNav } from "@config/navigation"
import type { AppDispatch, RootState } from "@store/store"
import { emptyChain, type ChainState } from "@store/chainSlice"

/** The module whose chain the current step belongs to, from ChainLayout. */
export function useModule(): ModuleNav {
    return useOutletContext<ModuleNav>()
}

/**
 * What the earlier steps of this module's chain have produced, plus the
 * dispatcher to add to it. Reading through a default keeps every step page
 * free of null checks on a chain that has simply not been started yet.
 */
export function useChain(moduleKey: string): { chain: ChainState; dispatch: AppDispatch } {
    const chain = useSelector((state: RootState) => state.chains[moduleKey] ?? emptyChain)
    const dispatch = useDispatch<AppDispatch>()
    return { chain, dispatch }
}
