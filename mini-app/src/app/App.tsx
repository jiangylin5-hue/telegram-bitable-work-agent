import { useEffect, useState } from 'react'

import { ApiError, api, type BootstrapResponse, type WorkspaceHome } from './api'
import { AppShell } from './AppShell'
import { WorkspaceHome as WorkspaceHomeView } from './WorkspaceHome'

type AppState =
  | { status: 'loading' }
  | { status: 'denied' }
  | { status: 'error' }
  | { status: 'ready'; bootstrap: BootstrapResponse; home: WorkspaceHome }

export function App() {
  const [state, setState] = useState<AppState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const bootstrap = await api.bootstrap()
        const workspace = bootstrap.workspaces[0]
        if (!workspace) {
          if (active) setState({ status: 'denied' })
          return
        }
        const home = await api.workspaceHome(workspace.id)
        if (active) setState({ status: 'ready', bootstrap, home })
      } catch (error) {
        if (!active) return
        setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
      }
    }
    void load()
    return () => { active = false }
  }, [])

  if (state.status === 'loading') return <main className="app-state" aria-label="正在加载工作区">正在加载工作区…</main>
  if (state.status === 'denied') return <main className="app-state" aria-label="无工作区访问权限">当前身份没有可访问的工作区。</main>
  if (state.status === 'error') return <main className="app-state" aria-label="网络错误">暂时无法加载工作区，请稍后重试。</main>

  const readyState = state
  const workspace = readyState.bootstrap.workspaces[0]
  async function selectWorkspace(workspaceId: string) {
    if (workspaceId === workspace.id) return
    setState({ status: 'loading' })
    try {
      const home = await api.workspaceHome(workspaceId)
      setState({ status: 'ready', bootstrap: readyState.bootstrap, home })
    } catch (error) {
      setState({ status: error instanceof ApiError && error.status === 403 ? 'denied' : 'error' })
    }
  }

  const selectedWorkspace = readyState.bootstrap.workspaces.find((item) => item.id === readyState.home.workspace_id) ?? workspace
  return <AppShell workspace={selectedWorkspace} workspaces={readyState.bootstrap.workspaces} onWorkspaceChange={selectWorkspace}><WorkspaceHomeView home={readyState.home} workspace={selectedWorkspace} /></AppShell>
}
