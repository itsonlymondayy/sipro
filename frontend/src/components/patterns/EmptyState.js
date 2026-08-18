import React from "react";
import { Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WORK } from "@/constants/testIds";

export default function EmptyState({ icon: Icon = Inbox, title, description, actionLabel, onAction }) {
  return (
    <div data-testid={WORK.emptyState} className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/50 px-6 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
        <Icon className="h-6 w-6" />
      </div>
      <p className="mt-3 font-medium">{title}</p>
      {description ? <p className="mt-1 text-sm text-muted-foreground max-w-sm">{description}</p> : null}
      {actionLabel ? <Button className="mt-4" onClick={onAction}>{actionLabel}</Button> : null}
    </div>
  );
}
