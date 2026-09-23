/**
 * The uploaded workbook a chain is still working from.
 *
 * FATCA classifies at one step and generates at the next, and both need the
 * workbook itself — the API is stateless, so the file has to be sent again.
 * A `File` is not serialisable, so it cannot live in the Redux store without
 * breaking it; it is held here instead, in module scope, deliberately
 * outside the state the store is responsible for.
 *
 * This is per-tab memory, not storage: a reload empties it, and the step
 * that needs a file says so rather than assuming one is there.
 */
const vault = new Map<string, File>()

export const keepFile = (moduleKey: string, file: File): void => {
    vault.set(moduleKey, file)
}

export const takeFile = (moduleKey: string): File | undefined => vault.get(moduleKey)

export const forgetFile = (moduleKey: string): void => {
    vault.delete(moduleKey)
}
