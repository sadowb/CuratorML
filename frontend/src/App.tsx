import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import CreateProject from "./pages/CreateProject";
import MangaEditor from "./pages/MangaEditor";
import ProjectsDashboard from "./pages/ProjectsDashboard";
import UploadPages from "./pages/UploadPages";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
        <div className="grid grid-rows-1 w-full h-screen bg-brand-surface-bg font-sans text-brand-text overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<ProjectsDashboard />} />
            <Route path="/create" element={<CreateProject />} />
            <Route
              path="/projects/:projectId/upload"
              element={<UploadPages />}
            />
            <Route
              path="/editor/:projectId/:pageId"
              element={<MangaEditor />}
            />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
      </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
