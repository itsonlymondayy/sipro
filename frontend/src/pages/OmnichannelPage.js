import React, { useCallback, useEffect, useState } from "react";
import { Workflow } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import StatusPill from "@/components/patterns/StatusPill";
import RulesPanel from "@/components/omni/RulesPanel";
import TemplatesPanel from "@/components/omni/TemplatesPanel";
import BroadcastPanel from "@/components/omni/BroadcastPanel";
import ChannelsPanel from "@/components/omni/ChannelsPanel";
import PlaybookPanel from "@/components/omni/PlaybookPanel";
import CaptureFailuresPanel from "@/components/omni/CaptureFailuresPanel";
import api from "@/services/apiClient";
import { OMNI } from "@/constants/testIds";

export default function OmnichannelPage() {
  const [held, setHeld] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadBadge = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/capture/failures/summary");
      setHeld(res.data?.data?.open || 0);
    } catch (e) {
      setError("Ringkasan antrean lead gagal masuk tidak bisa dimuat.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadBadge(); }, [loadBadge]);

  return (
    <div data-testid={OMNI.page} className="space-y-4">
      <div className="flex items-center gap-2">
        <Workflow className="h-5 w-5 text-primary" />
        <h1 className="font-heading text-xl font-semibold">Automasi &amp; Channel</h1>
        <StatusPill status="simulation" />
      </div>
      <p className="text-sm text-muted-foreground">
        Conversational engine omnichannel: aturan otomasi, template WhatsApp, akun channel,
        dan antrean penyelamatan lead yang gagal masuk. Atribusi lead ke kampanye &amp; event
        CAPI pindah ke menu <strong>Marketing → Atribusi &amp; CAPI</strong> (satu urusan satu
        pintu) karena di sana angkanya bisa dipertemukan dengan biaya iklan.
        {loading ? " Memuat ringkasan…" : ""}
        {error ? ` ${error}` : ""}
        {!loading && !error && held === 0
          ? " Belum ada lead yang tertahan di antrean gagal masuk." : ""}
      </p>

      <Tabs defaultValue="rules" className="w-full">
        <TabsList>
          <TabsTrigger data-testid={OMNI.tabRules} value="rules">Automasi</TabsTrigger>
          <TabsTrigger data-testid={OMNI.tabTemplates} value="templates">Template WA</TabsTrigger>
          <TabsTrigger data-testid={OMNI.tabBroadcast} value="broadcast">Broadcast</TabsTrigger>
          <TabsTrigger data-testid={OMNI.tabPlaybook} value="playbook">Playbook WA</TabsTrigger>
          <TabsTrigger data-testid={OMNI.tabChannels} value="channels">Channel</TabsTrigger>
          <TabsTrigger data-testid={OMNI.tabCapture} value="capture">
            Gagal Masuk
            {held > 0 ? (
              <span data-testid={OMNI.captureBadge}
                className="ml-1.5 rounded-full bg-rose-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                {held}
              </span>
            ) : null}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="rules" className="mt-4"><RulesPanel /></TabsContent>
        <TabsContent value="templates" className="mt-4"><TemplatesPanel /></TabsContent>
        <TabsContent value="broadcast" className="mt-4"><BroadcastPanel /></TabsContent>
        <TabsContent value="playbook" className="mt-4"><PlaybookPanel /></TabsContent>
        <TabsContent value="channels" className="mt-4"><ChannelsPanel /></TabsContent>
        <TabsContent value="capture" className="mt-4">
          <CaptureFailuresPanel onCountChange={setHeld} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
