import { Bell, Bot, ChevronDown, Grid2X2, Home, LayoutList, Settings, ShieldCheck, Table2, UsersRound } from 'lucide-react'

import type { Workspace } from './api'

export type AppShellRoute = 'home' | 'bases'

type AppShellProps = { workspace: Workspace; workspaces: Workspace[]; onWorkspaceChange: (workspaceId: string) => void; activeRoute: AppShellRoute; onNavigate: (route: AppShellRoute) => void; onOpenGovernance?: (trigger: HTMLElement) => void; children: React.ReactNode }
type ManagementItem = { label: string; icon: typeof UsersRound; onClick?: (trigger: HTMLElement) => void }

const primaryItems = [
  { label: '工作区', icon: Home, route: 'home' as const }, { label: '消息', icon: Bell },
  { label: 'Base', icon: Table2, route: 'bases' as const }, { label: '视图', icon: LayoutList },
  { label: '自动化', icon: Grid2X2 }, { label: '机器人', icon: Bot },
]

export function AppShell({ workspace, workspaces, onWorkspaceChange, activeRoute, onNavigate, onOpenGovernance, children }: AppShellProps) {
  const managementItems: ManagementItem[] = [
    workspace.capabilities.can_manage_workspace ? { label: '成员与权限', icon: UsersRound, onClick: onOpenGovernance } : null,
    workspace.capabilities.can_manage_schema ? { label: '设置', icon: Settings } : null,
  ].filter((item): item is ManagementItem => item !== null)

  return <div className="app-shell">
    <aside className="desktop-sidebar" aria-label="主导航">
      <div className="brand-mark" aria-label="Workspace"><span /></div>
      <nav className="primary-nav">
        {primaryItems.map(({ label, icon: Icon, route }) => route
          ? <button className={activeRoute === route ? 'nav-item active' : 'nav-item'} type="button" aria-current={activeRoute === route ? 'page' : undefined} onClick={() => onNavigate(route)} key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></button>
          : <a className="nav-item" href="#home" key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></a>)}
        {managementItems.length > 0 && <div className="nav-divider" />}
        {managementItems.map(({ label, icon: Icon, onClick }) => onClick
          ? <button className="nav-item" type="button" aria-label="打开治理工作台" onClick={(event) => onClick(event.currentTarget)} key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></button>
          : <a className="nav-item" href="#management" key={label}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{label}</span></a>)}
      </nav>
      <label className="sidebar-profile"><span className="profile-avatar">{workspace.name.slice(0, 1)}</span><span className="workspace-select-wrap"><strong>{workspace.role}</strong><select aria-label="切换工作区（桌面）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></span><ChevronDown aria-hidden="true" size={16} /></label>
    </aside>
    <div className="app-content"><header className="mobile-header"><span className="brand-mark compact" aria-hidden="true"><span /></span><label className="workspace-switcher"><select aria-label="切换工作区（移动）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><ChevronDown aria-hidden="true" size={16} /></label></header>{children}</div>
    <nav className="mobile-nav" aria-label="移动导航"><button className={activeRoute === 'home' ? 'mobile-nav-item active' : 'mobile-nav-item'} type="button" aria-current={activeRoute === 'home' ? 'page' : undefined} onClick={() => onNavigate('home')}><Home size={19} /><span>Home</span></button><button className={activeRoute === 'bases' ? 'mobile-nav-item active' : 'mobile-nav-item'} type="button" aria-current={activeRoute === 'bases' ? 'page' : undefined} onClick={() => onNavigate('bases')}><Table2 size={19} /><span>Bases</span></button><a className="mobile-nav-item" href="#bots"><Bot size={19} /><span>Bots</span></a>{workspace.capabilities.can_manage_workspace && onOpenGovernance ? <button className="mobile-nav-item" type="button" aria-label="打开治理工作台（移动端）" onClick={(event) => onOpenGovernance(event.currentTarget)}><ShieldCheck size={19} /><span>更多</span></button> : <a className="mobile-nav-item" href="#more"><ShieldCheck size={19} /><span>更多</span></a>}</nav>
  </div>
}
