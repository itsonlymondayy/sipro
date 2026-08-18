import React from "react";
import { Wrench } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import SubcontractorsPanel from "@/components/subcon/SubcontractorsPanel";
import SPKPanel from "@/components/subcon/SPKPanel";
import ClaimsPanel from "@/components/subcon/ClaimsPanel";
import { PROCUREMENT, CLAIMS } from "@/constants/testIds";

export default function SubconPage() {
  return (
    <div data-testid={PROCUREMENT.subconPage} className="space-y-5">
      <div className="flex items-center gap-2">
        <Wrench className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Subkontraktor & SPK</h1>
      </div>
      <Tabs defaultValue="subs">
        <TabsList>
          <TabsTrigger data-testid={PROCUREMENT.subTab} value="subs">Subkontraktor</TabsTrigger>
          <TabsTrigger data-testid={PROCUREMENT.spkTab} value="spk">SPK (Perintah Kerja)</TabsTrigger>
          <TabsTrigger data-testid={CLAIMS.tab} value="claims">Progress & Termin</TabsTrigger>
        </TabsList>
        <TabsContent value="subs" className="mt-4"><SubcontractorsPanel /></TabsContent>
        <TabsContent value="spk" className="mt-4"><SPKPanel /></TabsContent>
        <TabsContent value="claims" className="mt-4"><ClaimsPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
