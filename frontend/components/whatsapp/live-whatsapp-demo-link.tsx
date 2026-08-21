import Link from "next/link";
import {MessageCircleMore} from "lucide-react";

export function LiveWhatsAppDemoLink({applicationId}: {applicationId: string}) {
  return <Link href={`/dashboard/applications/${applicationId}/whatsapp-demo`} className="inline-flex items-center gap-2 rounded-full bg-[#191515] px-5 py-3 text-sm font-semibold text-white">
    <MessageCircleMore size={17}/>Open Live WhatsApp Demo
  </Link>;
}
