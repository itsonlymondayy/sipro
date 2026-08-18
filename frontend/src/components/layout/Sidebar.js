import React from "react";
import { NavLink } from "react-router-dom";
import { Building2, Lock } from "lucide-react";
import { buildNavGroups } from "@/config/navigationConfig";
import NavMigrationDialog from "@/components/layout/NavMigrationDialog";
import { cn } from "@/lib/utils";
import { NAV, HUB } from "@/constants/testIds";

function NavItem({ item }) {
  const Icon = item.icon;
  if (item.comingSoon) {
    return (
      <div
        data-testid={`${NAV.navItemPrefix}-${item.id}`}
        data-coming-soon="true"
        aria-disabled="true"
        className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-muted-foreground/70 cursor-not-allowed"
        title={item.note ? `Segera hadir — ${item.note}` : "Segera hadir"}
      >
        <span className="flex items-center gap-2.5">
          {Icon ? <Icon className="h-4 w-4" /> : null}{item.label}
        </span>
        <Lock data-testid={HUB.navSoon} className="h-3 w-3" />
      </div>
    );
  }
  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      data-testid={`${NAV.navItemPrefix}-${item.id}`}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-foreground/80 hover:bg-secondary",
        )
      }
    >
      {Icon ? <Icon className="h-4 w-4" /> : null}
      {item.label}
    </NavLink>
  );
}

export default function Sidebar({ role, onNavigate }) {
  const groups = buildNavGroups(role);
  return (
    <aside
      data-testid={NAV.sidebar}
      className="flex h-full w-64 shrink-0 flex-col border-r bg-card"
      onClick={onNavigate}
    >
      <div className="flex items-center gap-2.5 px-5 py-4 border-b">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Building2 className="h-5 w-5" />
        </div>
        <div>
          <p className="font-heading font-bold leading-none tracking-tight">SIPRO</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">Property Development OS</p>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map((group) => {
          if (group.type === "standalone") {
            return <NavItem key={group.id} item={group} />;
          }
          return (
            <div key={group.groupId}>
              <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((it) => <NavItem key={it.id} item={it} />)}
              </div>
            </div>
          );
        })}
      </nav>
      {/* Fase 40c: pintu ke PETA MENU (lama→baru). Diletakkan di dasar sidebar karena di
          situlah pemakai mencari bantuan setelah gagal menemukan menu yang ia hafal. */}
      <div className="border-t px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
        <NavMigrationDialog />
        <p className="mt-1 text-[10px] text-muted-foreground">
          SIPRO · Property Development OS · v1.0
        </p>
      </div>
    </aside>
  );
}
