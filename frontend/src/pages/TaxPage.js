import React from "react";
import { Landmark } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import TaxSummaryPanel from "@/components/tax/TaxSummaryPanel";
import FakturPanel from "@/components/tax/FakturPanel";
import TaxRecordsPanel from "@/components/tax/TaxRecordsPanel";
import { TAX } from "@/constants/testIds";

// Satu route (/tax) dengan Tabs internal; tiap panel memuat datanya sendiri
// (loading/empty/error) agar file tetap ramping dan lulus guardrails.
export default function TaxPage() {
  return (
    <div data-testid={TAX.page} className="space-y-5">
      <div className="flex items-center gap-2">
        <Landmark className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Perpajakan</h1>
      </div>

      <Tabs defaultValue="summary">
        <TabsList className="flex-wrap">
          <TabsTrigger data-testid={TAX.tabSummary} value="summary">Ringkasan &amp; SPT PPN</TabsTrigger>
          <TabsTrigger data-testid={TAX.tabFaktur} value="faktur">Faktur Pajak</TabsTrigger>
          <TabsTrigger data-testid={TAX.tabRecords} value="records">Catatan Pajak</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="mt-4"><TaxSummaryPanel /></TabsContent>
        <TabsContent value="faktur" className="mt-4"><FakturPanel /></TabsContent>
        <TabsContent value="records" className="mt-4"><TaxRecordsPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
