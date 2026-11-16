/**
 * Role:   Route table of the web client.
 * Input:  The browser location provided by BrowserRouter.
 * Output: The Layout shell with the page matching the current path.
 * Flow:   Maps every path onto its page component; unknown paths and / redirect to /chat.
 */
import { Navigate, Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { ChatPage } from './pages/ChatPage'
import { CorpusPage } from './pages/CorpusPage'
import { EvalPage } from './pages/EvalPage'
import { GraphPage } from './pages/GraphPage'
import { LabPage } from './pages/LabPage'
import { RetrievalPage } from './pages/RetrievalPage'
import { StatusPage } from './pages/StatusPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="corpus" element={<CorpusPage />} />
        <Route path="corpus/:course/:slug" element={<LabPage />} />
        <Route path="retrieval" element={<RetrievalPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="eval" element={<EvalPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Route>
    </Routes>
  )
}
