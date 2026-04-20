# Error Audit Report
## Frontend Errors

During a full project audit, the following critical ("pinnacle") errors and build-breaking issues were identified in the frontend application. 

### 1. `frontend/src/components/studios/LegalStudio/ReportPreview.tsx`
**Error:** `error TS2740: Type '{ audit: string; summary: string; analysis: string; }' is missing the following properties from type 'Record<ReportType, string>': financial_analysis, ifrs, cash_flow, mis, and 6 more.`
**Description:** A TypeScript compilation error preventing a successful build. An object is declared as `Record<ReportType, string>`, but it lacks several keys that are required by the `ReportType` definition.
**Solution:** Change the type to `Partial<Record<ReportType, string>>` instead of `Record<ReportType, string>`, or explicitly provide all missing keys with default fallback values (like `""`).

### 2. `frontend/src/App.tsx`
**Error:** `ESLint: Error: Cannot access refs during render (react-hooks/refs)` at line 95.
**Description:** Accessing `newKeyRef.current` inside the functional component's render body. Reading `ref.current` during render can lead to unexpected behaviors and breaks React's rules, as refs are mutable and should not participate in data flow.
**Solution:** Do not use a ref for the key prop if it's updated manually during render. Either derive the key from a `useState` value, or only read/update the ref inside event handlers or `useEffect` hooks.

### 3. `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
**Error:** `ESLint: Error: Cannot update ref during render (react-hooks/refs)` at line 326.
**Description:** The component updates `activeSourcesRef.current = activeSources;` synchronously within the render cycle. This causes the component properties to mutate before the render commits, which breaks React concurrent mode guarantees.
**Solution:** Move the assignment into a `useEffect` hook so that it only updates after the main render loop is finished:
```typescript
useEffect(() => {
  activeSourcesRef.current = activeSources;
}, [activeSources]);
```

### 4. `frontend/src/components/studios/LegalStudio/PreviewPane.tsx`
**Error:** `ESLint: Error: Calling setState synchronously within an effect can trigger cascading renders` at line 18.
**Description:** `setUrl(null)` is called directly and unconditionally in a way that causes cascading renders under some scenarios.
**Solution:** Either initialize the state variable cleanly based on props at declaration time if possible, or clear the state conditionally without looping dependencies.

## Backend Errors
The Python backend's test suite array was executed with no failures (`337 passed, 2 skipped`). Therefore, no pinnacle code errors were blocking in the backend scripts during the audit.
