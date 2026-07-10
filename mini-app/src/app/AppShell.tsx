import { Bell, Bot, ChevronDown, Grid2X2, Home, LayoutList, Settings, ShieldCheck, Table2, UsersRound } from 'lucide-react'

import type { Workspace } from './api'

type AppShellProps = { workspace: Workspace; workspaces: Workspace[]; onWorkspaceChange: (workspaceId: string) => void; children: React.ReactNode }

const primaryItems = [
  { label: '工作区', icon: Home, active: true }, { label: '消息', icon: Bell },
  { label: 'Base', icon: Table2 }, { label: '视图', icon: LayoutList },
  { label: '自动化', icon: Grid2X2 }, { label: '机器人', icon: Bot },
]

export function AppShell({ workspace, workspaces, onWorkspaceChange, children }: AppShellProps) {
  const managementItems = [
    workspace.capabilities.can_manage_workspace ? { label: '成员与权限', icon: UsersRound } : null,
    workspace.capabilities.can_manage_schema ? { label: '设置', icon: Settings } : null,
  ].filter(Boolean) as { label: string; icon: typeof UsersRound }[]

  return <div className="app-shell">
    <aside className="desktop-sidebar" aria-label="主导航">
      <div className="brand-mark" aria-label="Workspace"><span /></div>
      <nav className="primary-nav">
        {primaryItems.map(({ label, icon: Icon, active }) => <a className={active ? 'nav-item active' : 'nav-item'} href="#home" key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></a>)}
        {managementItems.length > 0 && <div className="nav-divider" />}
        {managementItems.map(({ label, icon: Icon }) => <a className="nav-item" href="#management" key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></a>)}
      </nav>
      <label className="sidebar-profile"><span className="profile-avatar">{workspace.name.slice(0, 1)}</span><span className="workspace-select-wrap"><strong>{workspace.role}</strong><select aria-label="切换工作区（桌面）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></span><ChevronDown aria-hidden="true" size={16} /></label>
    </aside>
    <div className="app-content"><header className="mobile-header"><span className="brand-mark compact" aria-hidden="true"><span /></span><label className="workspace-switcher"><select aria-label="切换工作区（移动）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><ChevronDown aria-hidden="true" size={16} /></label></header>{children}</div>
    <nav className="mobile-nav" aria-label="移动导航"><a className="mobile-nav-item active" href="#home"><Home size={19} /><span>Home</span></a><a className="mobile-nav-item" href="#bases"><Table2 size={19} /><span>Bases</span></a><a className="mobile-nav-item" href="#bots"><Bot size={19} /><span>Bots</span></a><a className="mobile-nav-item" href="#more"><ShieldCheck size={19} /><span>更多</span></a></nav>
  </div>
}
