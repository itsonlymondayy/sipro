import React from "react";
import { BookOpen } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import CoAPanel from "@/components/gl/CoAPanel";
import JournalPanel from "@/components/gl/JournalPanel";
import LedgerPanel from "@/components/gl/LedgerPanel";
import TrialBalancePanel from "@/components/gl/TrialBalancePanel";
import { GL } from "@/constants/testIds";

export default function AccountingPage() {
  return (
    <div data-testid={GL.accountingPage} className="space-y-5">
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Buku Besar & Jurnal</h1>
      </div>
      <Tabs defaultValue="journal">
        <TabsList>
          <TabsTrigger data-testid={GL.journalTab} value="journal">Jurnal Umum</TabsTrigger>
          <TabsTrigger data-testid={GL.ledgerTab} value="ledger">Buku Besar</TabsTrigger>
          <TabsTrigger data-testid={GL.tbTab} value="tb">Neraca Saldo</TabsTrigger>
          <TabsTrigger data-testid={GL.coaTab} value="coa">Bagan Akun</TabsTrigger>
        </TabsList>
        <TabsContent value="journal" className="mt-4"><JournalPanel /></TabsContent>
        <TabsContent value="ledger" className="mt-4"><LedgerPanel /></TabsContent>
        <TabsContent value="tb" className="mt-4"><TrialBalancePanel /></TabsContent>
        <TabsContent value="coa" className="mt-4"><CoAPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
