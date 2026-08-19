"use client";
import Link from "next/link";
import { ArrowRight, Search, UserPlus } from "lucide-react";
import { useEffect,useMemo,useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { Loading } from "@/components/ui/loading";
import { apiFetch } from "@/lib/api";
import type { Client,GSTApplication } from "@/lib/types";

export default function ClientsPage(){const [clients,setClients]=useState<Client[]>([]);const [apps,setApps]=useState<GSTApplication[]>([]);const [query,setQuery]=useState("");const [loading,setLoading]=useState(true);useEffect(()=>{Promise.all([apiFetch<Client[]>("/clients"),apiFetch<GSTApplication[]>("/applications")]).then(([c,a])=>{setClients(c);setApps(a)}).catch(e=>toast.error(e.message)).finally(()=>setLoading(false))},[]);const filtered=useMemo(()=>clients.filter(c=>`${c.business_name} ${c.gstin} ${c.state}`.toLowerCase().includes(query.toLowerCase())),[clients,query]);if(loading)return <Loading/>;return <><PageHeader eyebrow="CLIENT DIRECTORY" title="Clients" description="Manage GST profiles, contacts, filing frequency and active compliance periods." actions={<Link href="/dashboard/clients/new" className="inline-flex items-center gap-2 rounded-full bg-[#191515] px-5 py-3 text-sm font-semibold text-white"><UserPlus size={17}/>Add client</Link>}/><div className="relative mb-5 max-w-md"><Search className="absolute left-3.5 top-3 text-[#77716e]" size={18}/><Input className="w-full pl-10" placeholder="Search business, GSTIN or state" value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="grid gap-4 lg:grid-cols-2">{filtered.map(client=>{const app=apps.find(item=>item.client_id===client.id);return <Link key={client.id} href={`/dashboard/clients/${client.id}`}><Card className="h-full p-5 transition hover:-translate-y-0.5 hover:shadow-lg"><div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-bold">{client.business_name}</h2><p className="mt-1 text-xs text-[#77716e]">{client.gstin} · {client.state}</p></div>{app&&<Badge value={app.status}/>}</div><p className="mt-6 text-sm text-[#625d5a]">{client.contact_name} · {client.whatsapp_phone}</p><div className="mt-5 flex items-center justify-between border-t border-[#eeeae6] pt-4 text-xs text-[#77716e]"><span>{client.filing_frequency} GST · {client.demo_scenario||"New client"}</span><ArrowRight size={17}/></div></Card></Link>})}</div>{!filtered.length&&<Card className="p-12 text-center text-sm text-[#77716e]">No clients match your search.</Card>}</>}
