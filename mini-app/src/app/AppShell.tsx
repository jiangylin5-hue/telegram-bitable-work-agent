import { Bell, Bot, ChevronDown, Grid2X2, Home, LayoutList, Settings, ShieldCheck, Table2, UsersRound } from 'lucide-react'

import type { Workspace } from './api'
import { WorkspaceLaunchControls } from './WorkspaceLaunchControls'
import type { TelegramFullscreenState } from './telegram-mini-app'

export type AppShellRoute = 'home' | 'bases'

type NavigationAvailability = 'available' | 'planned'
type NavigationItem = { label: string; description: string; icon: typeof UsersRound; onClick?: (trigger: HTMLElement) => void; availability: NavigationAvailability; route?: AppShellRoute }
type AppShellProps = { workspace: Workspace; workspaces: Workspace[]; onWorkspaceChange: (workspaceId: string) => void; activeRoute: AppShellRoute; onNavigate: (route: AppShellRoute) => void; onOpenDraftHub?: (trigger: HTMLElement) => void; onOpenTeamBot?: (trigger: HTMLElement) => void; onOpenGovernance?: (trigger: HTMLElement) => void; telegramState?: TelegramFullscreenState | null; onOpenBrowser?: () => void; children: React.ReactNode }

function NavigationButton({ item, activeRoute, className }: { item: NavigationItem; activeRoute?: AppShellRoute; className: string }) {
  const { icon: Icon } = item
  const enabled = item.availability === 'available' && Boolean(item.onClick)
  const hint = item.availability === 'planned' ? '即将上线' : item.description
  const label = `${item.label}：${hint}`

  return <button className={`${className}${item.route === activeRoute ? ' active' : ''}${item.availability === 'planned' ? ' planned' : ''}`} type="button" aria-current={item.route === activeRoute ? 'page' : undefined} aria-label={label} title={label} data-nav-hint={hint} data-availability={item.availability} disabled={!enabled} onClick={enabled ? (event) => item.onClick?.(event.currentTarget) : undefined}><Icon aria-hidden="true" size={18} strokeWidth={1.8} /><span>{item.label}</span>{item.availability === 'planned' && <small aria-hidden="true">即将上线</small>}</button>
}

export function AppShell({ workspace, workspaces, onWorkspaceChange, activeRoute, onNavigate, onOpenDraftHub, onOpenTeamBot, onOpenGovernance, telegramState, onOpenBrowser, children }: AppShellProps) {
  const primaryItems: NavigationItem[] = [
    { label: '工作区', description: '查看今日事项', icon: Home, route: 'home', availability: 'available', onClick: () => onNavigate('home') },
    { label: '待确认', description: '查看待处理草稿', icon: Bell, availability: onOpenDraftHub ? 'available' : 'planned', onClick: onOpenDraftHub },
    { label: 'Bases', description: '浏览和打开多维表格', icon: Table2, route: 'bases', availability: 'available', onClick: () => onNavigate('bases') },
    { label: '团队 Bot', description: '使用已授权团队助手', icon: Bot, availability: onOpenTeamBot ? 'available' : 'planned', onClick: onOpenTeamBot },
    { label: '消息', description: '即将上线', icon: Bell, availability: 'planned' },
    { label: '视图', description: '即将上线', icon: LayoutList, availability: 'planned' },
    { label: '自动化', description: '即将上线', icon: Grid2X2, availability: 'planned' },
  ]
  const managementItems: NavigationItem[] = [
    workspace.capabilities.can_manage_workspace ? { label: '成员与权限', description: '管理成员与权限', icon: UsersRound, availability: onOpenGovernance ? 'available' : 'planned', onClick: onOpenGovernance } : null,
    workspace.capabilities.can_manage_schema ? { label: '设置', description: '即将上线', icon: Settings, availability: 'planned' } : null,
  ].filter((item): item is NavigationItem => item !== null)

  return <div className="app-shell">
    <aside className="desktop-sidebar" aria-label="主导航" data-visual-system="stage07-workbench">
      <div className="brand-mark" aria-label="Workspace"><span /></div>
      <nav className="primary-nav" data-visual-system="stage07-workbench">
        {primaryItems.map((item) => <NavigationButton item={item} activeRoute={activeRoute} className="nav-item" key={item.label} />)}
        {managementItems.length > 0 && <div className="nav-divider" />}
        {managementItems.map((item) => <NavigationButton item={item} className="nav-item" key={item.label} />)}
      </nav>
      <label className="sidebar-profile"><span className="profile-avatar">{workspace.name.slice(0, 1)}</span><span className="workspace-select-wrap"><strong>{workspace.role}</strong><select aria-label="切换工作区（桌面）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></span><ChevronDown aria-hidden="true" size={16} /></label>
    </aside>
    <div className="app-content"><header className="mobile-header"><span className="brand-mark compact" aria-hidden="true"><span /></span><label className="workspace-switcher"><select aria-label="切换工作区（移动）" value={workspace.id} onChange={(event) => onWorkspaceChange(event.target.value)}>{workspaces.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><ChevronDown aria-hidden="true" size={16} /></label></header><WorkspaceLaunchControls telegramState={telegramState ?? null} onOpenBrowser={onOpenBrowser} />{children}</div>
    <nav className="mobile-nav" aria-label="移动导航">{primaryItems.slice(0, 4).map((item) => <NavigationButton item={item} activeRoute={activeRoute} className="mobile-nav-item" key={item.label} />)}<NavigationButton item={{ label: '更多', description: '管理成员与权限', icon: ShieldCheck, availability: workspace.capabilities.can_manage_workspace && onOpenGovernance ? 'available' : 'planned', onClick: onOpenGovernance }} className="mobile-nav-item" key="更多" /></nav>
  </div>
}
