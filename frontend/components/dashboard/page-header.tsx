export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end"><div>{eyebrow&&<p className="mb-2 text-xs font-bold tracking-[.14em] text-[#477ca8]">{eyebrow}</p>}<h1 className="text-3xl font-bold tracking-[-.04em] sm:text-4xl">{title}</h1>{description&&<p className="mt-2 max-w-2xl text-sm leading-6 text-[#6b6562]">{description}</p>}</div>{actions&&<div className="flex flex-wrap gap-2">{actions}</div>}</div>;
}
