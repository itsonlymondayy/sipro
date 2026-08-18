import React from "react";
import { ShoppingCart } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import POPanel from "@/components/procurement/POPanel";
import ThreeWayPanel from "@/components/procurement/ThreeWayPanel";
import { PROCUREMENT } from "@/constants/testIds";

export default function ProcurementPage() {
  return (
    <div data-testid={PROCUREMENT.procPage} className="space-y-5">
      <div className="flex items-center gap-2">
        <ShoppingCart className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Pengadaan & 3-Way Match</h1>
      </div>
      <Tabs defaultValue="po">
        <TabsList>
          <TabsTrigger data-testid={PROCUREMENT.poTab} value="po">Purchase Order</TabsTrigger>
          <TabsTrigger data-testid={PROCUREMENT.threewayTab} value="threeway">3-Way Match</TabsTrigger>
        </TabsList>
        <TabsContent value="po" className="mt-4"><POPanel /></TabsContent>
        <TabsContent value="threeway" className="mt-4"><ThreeWayPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
