import { CheckCircle2, Clock3, FileWarning, MessageCircleMore, Sparkles } from "lucide-react";

const clients = [
  { name: "Raj Traders", period: "April 2026", docs: "4 / 5", status: "Purchase register missing", tone: "text-amber-700 bg-amber-50" },
  { name: "ABC Electronics", period: "April 2026", docs: "5 / 5", status: "Validation review", tone: "text-blue-700 bg-blue-50" },
  { name: "Nova Services", period: "April 2026", docs: "5 / 5", status: "Ready for CA review", tone: "text-emerald-700 bg-emerald-50" },
];

export function DashboardPreview() {
  return (
    <div className="relative mx-auto mt-16 max-w-[1040px] rounded-[36px] border border-white/80 bg-white/72 p-3 shadow-[0_35px_100px_rgba(25,21,21,.18)] backdrop-blur-xl">
      <div className="overflow-hidden rounded-[27px] border border-[#ded9d4] bg-[#f8f7f5]">
        <div className="flex items-center justify-between border-b border-[#e5e2de] bg-white px-5 py-4">
          <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-[#191515]"/><span className="text-sm font-black tracking-[-.05em]">OBLIQ</span></div>
          <div className="flex items-center gap-2 rounded-full bg-[#e8f1fa] px-3 py-1.5 text-xs font-semibold"><Sparkles size={14}/> AI demo mode</div>
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-4 sm:p-6">
          {[{label:"Active GST periods",value:"5",icon:Clock3},{label:"Missing documents",value:"1",icon:FileWarning},{label:"Needs review",value:"2",icon:Sparkles},{label:"Ready for filing",value:"1",icon:CheckCircle2}].map(({label,value,icon:Icon}) => (
            <div key={label} className="rounded-[19px] border border-[#e5e2de] bg-white p-4"><Icon size={17} className="mb-4 text-[#477ca8]"/><div className="text-2xl font-bold">{value}</div><div className="mt-1 text-xs text-[#6d6764]">{label}</div></div>
          ))}
        </div>
        <div className="mx-4 mb-4 overflow-hidden rounded-[22px] border border-[#e5e2de] bg-white sm:mx-6 sm:mb-6">
          <div className="flex items-center justify-between border-b border-[#ece8e4] px-5 py-4"><div><p className="text-sm font-semibold">Client GST workspace</p><p className="text-xs text-[#77716e]">Documents, extraction and filing readiness</p></div><MessageCircleMore size={20}/></div>
          <div className="divide-y divide-[#eeeae6]">
            {clients.map((client) => <div key={client.name} className="grid gap-3 px-5 py-4 text-sm sm:grid-cols-[1.2fr_.8fr_.5fr_1.2fr] sm:items-center"><strong>{client.name}</strong><span className="text-[#6d6764]">{client.period}</span><span>{client.docs}</span><span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${client.tone}`}>{client.status}</span></div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
