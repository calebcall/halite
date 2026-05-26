import {
  Activity,
  FileClock,
  Key,
  Server,
  Shield,
  Terminal,
  Users,
} from "lucide-react";

import { BrandMark } from "@/app/layout/BrandMark";
import { MustChangePassword } from "@/features/auth/guards";

export function AboutPage() {
  return (
    <MustChangePassword>
      <AboutPageInner />
    </MustChangePassword>
  );
}

function AboutPageInner() {
  return (
    <div className="flex flex-col gap-14 pb-12">
      <Hero />
      <Divider />
      <TheName />
      <Divider />
      <TheMarks />
      <Divider />
      <Capabilities />
      <Divider />
      <Palette />
      <Divider />
      <BuiltWith />
    </div>
  );
}

/* ---------- Hero ---------- */

function Hero() {
  return (
    <header className="relative flex flex-col items-center gap-5 pt-4 text-center">
      {/* Soft amber halo behind the mark — matches the login screen treatment. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 flex justify-center"
      >
        <div className="h-56 w-80 rounded-full bg-primary/15 blur-3xl" />
      </div>
      <BrandMark className="h-24 w-24" />
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
        About
      </p>
      <h1 className="text-5xl font-semibold tracking-tight">halite</h1>
      <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
        A modern operations console for SaltStack infrastructure. Built around
        the same lattice that gives rock salt its crystalline form.
      </p>
    </header>
  );
}

/* ---------- The Name ---------- */

function TheName() {
  return (
    <section className="flex flex-col gap-6">
      <SectionEyebrow>The Name</SectionEyebrow>
      <h2 className="text-3xl font-semibold tracking-tight">
        Why <span className="text-primary">halite</span>?
      </h2>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
          <p>
            <strong className="font-medium text-foreground">Halite</strong>{" "}
            <span className="font-mono text-[12px]">(/ˈheɪlaɪt/)</span> is the
            mineralogical name for rock salt — sodium chloride in its natural,
            crystalline form. The mineral grows in perfect cubes, with sodium
            and chloride ions locked in a regular three-dimensional lattice.
          </p>
          <p>
            That structure happens to mirror the topology of a SaltStack
            deployment almost exactly: a master node at the center,
            orchestrating a constellation of minions arranged across the
            network. The same diagram you&apos;d draw for an NaCl unit cell is
            the diagram you&apos;d draw for a Salt master surrounded by its
            minions.
          </p>
          <p>
            The dual meaning —{" "}
            <span className="text-foreground">Salt → halite</span>,{" "}
            <span className="text-foreground">lattice → master/minions</span> —
            felt too good to pass up. Every piece of the brand carries it: the
            mark is a 3×3 lattice; the secondary marks are cubes and crystal
            aggregates.
          </p>
        </div>
        <FactCard />
      </div>
    </section>
  );
}

function FactCard() {
  const rows: Array<[string, React.ReactNode]> = [
    ["Mineral", <span key="m">Halite</span>],
    [
      "Formula",
      <span key="f" className="font-mono text-primary">
        NaCl
      </span>,
    ],
    ["Crystal system", <span key="c">Isometric · cubic</span>],
    ["Cleavage", <span key="cl">Perfect, three directions</span>],
    [
      "Mohs hardness",
      <span key="h" className="tabular-nums">
        2 – 2.5
      </span>,
    ],
    ["Color", <span key="co">Colorless to white; amber when impure</span>],
  ];
  return (
    <aside className="flex flex-col rounded-lg border border-border/80 bg-card text-sm">
      <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Mineral data
        </span>
        <span className="font-mono text-[11px] text-primary">NaCl</span>
      </div>
      <dl className="divide-y divide-border/60">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-center justify-between px-5 py-2.5"
          >
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-xs font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

/* ---------- The Marks ---------- */

function TheMarks() {
  return (
    <section className="flex flex-col gap-6">
      <SectionEyebrow>The Marks</SectionEyebrow>
      <h2 className="text-3xl font-semibold tracking-tight">
        Three crystals, one story
      </h2>
      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
        The brand kit ships three icon families. Each one is the same mineral
        viewed from a different angle.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MarkCard
          title="The Lattice"
          subtitle="Primary mark"
          description="3×3 grid. The most semantically dense — diagrams both halite's atomic lattice and the SaltStack master+minion topology. This is the app icon."
        >
          <MarkLattice />
        </MarkCard>
        <MarkCard
          title="The Salt Cube"
          subtitle="Hero mark"
          description="Single isometric cube — the literal cubic crystal habit of halite (NaCl). Used in marketing and merchandise."
        >
          <MarkCube />
        </MarkCard>
        <MarkCard
          title="The Triple Stack"
          subtitle="Accent mark"
          description="Three crystals piled into a small aggregate. A compact sculpture for section dividers and secondary moments."
        >
          <MarkStack />
        </MarkCard>
      </div>
    </section>
  );
}

function MarkCard({
  title,
  subtitle,
  description,
  children,
}: {
  title: string;
  subtitle: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <article className="flex flex-col rounded-lg border border-border/80 bg-card">
      <div className="flex h-44 items-center justify-center px-6 py-6">
        {children}
      </div>
      <div className="flex flex-col gap-1 border-t border-border/60 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
            {subtitle}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
    </article>
  );
}

/** Inline mini-renderings of the three brand marks. Source SVGs live in
 *  logos/brand/{lattice,cube,stack}/icon.svg — these are kept in sync by hand. */
function MarkLattice() {
  return <BrandMark className="h-24 w-24" />;
}

function MarkCube() {
  return (
    <svg viewBox="0 0 512 512" className="h-24 w-24" aria-hidden role="img">
      <polygon points="256,56 429,156 256,256 83,156" fill="#f5b938" />
      <polygon points="429,156 429,356 256,456 256,256" fill="#e5a00d" />
      <polygon points="83,156 256,256 256,456 83,356" fill="#a77100" />
    </svg>
  );
}

function MarkStack() {
  return (
    <svg viewBox="0 0 512 512" className="h-24 w-24" aria-hidden role="img">
      <g fill="#e5a00d">
        <rect x="201" y="122" width="110" height="110" rx="18" />
        <rect x="108" y="248" width="140" height="140" rx="24" />
        <rect x="264" y="248" width="140" height="140" rx="24" />
      </g>
    </svg>
  );
}

/* ---------- Capabilities ---------- */

function Capabilities() {
  const items = [
    {
      icon: Server,
      title: "Minions",
      description:
        "Live status of every connected minion, grains drilled down on demand.",
    },
    {
      icon: Key,
      title: "Keys",
      description:
        "Approve, reject, or delete minion keys without leaving the console.",
    },
    {
      icon: Activity,
      title: "Jobs",
      description:
        "Browse recent jobs, inspect results, and kill runs mid-flight.",
    },
    {
      icon: Terminal,
      title: "Run",
      description: "Dispatch any Salt execution module against any target.",
    },
    {
      icon: Users,
      title: "Users & Roles",
      description:
        "Permission-driven access — pair console accounts with role policies.",
    },
    {
      icon: Shield,
      title: "Audit",
      description:
        "Every decision the policy engine made, in a queryable trail.",
    },
    {
      icon: FileClock,
      title: "Inventory",
      description:
        "Installed packages across the fleet, searchable and exportable.",
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      <SectionEyebrow>What it does</SectionEyebrow>
      <h2 className="text-3xl font-semibold tracking-tight">
        A console for the whole control plane
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(({ icon: Icon, title, description }) => (
          <div
            key={title}
            className="flex flex-col gap-3 rounded-lg border border-border/80 bg-card p-4"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 ring-1 ring-primary/25 text-primary">
              <Icon className="h-4 w-4" />
            </span>
            <div className="flex flex-col gap-1">
              <h3 className="text-sm font-semibold text-foreground">{title}</h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------- Palette ---------- */

function Palette() {
  const colors: Array<{
    name: string;
    hex: string;
    note?: string;
    light?: boolean;
  }> = [
    { name: "amber", hex: "#e5a00d", note: "Primary brand color" },
    { name: "amber-light", hex: "#f5b938", note: "Cube top face / highlight" },
    { name: "amber-dark", hex: "#a77100", note: "Cube shadow / pressed" },
    { name: "black", hex: "#0e0e0e", note: "Deepest background" },
    { name: "graphite", hex: "#141414", note: "Body background" },
    { name: "onyx", hex: "#1f1f1f", note: "Card surface" },
    { name: "slate", hex: "#2a2a2a", note: "Borders / elevated" },
    { name: "fog", hex: "#999999", note: "Muted text", light: true },
    { name: "bone", hex: "#ebebeb", note: "Primary text on dark", light: true },
  ];
  return (
    <section className="flex flex-col gap-6">
      <SectionEyebrow>The Palette</SectionEyebrow>
      <h2 className="text-3xl font-semibold tracking-tight">
        One amber, on deep neutrals
      </h2>
      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
        Halite's color is built on a single signature amber — the same{" "}
        <code className="rounded bg-muted px-1 font-mono text-[11px] text-foreground">
          #e5a00d
        </code>{" "}
        the marks render in — sitting on a stack of dark surfaces.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {colors.map((c) => (
          <div
            key={c.name}
            className="overflow-hidden rounded-md border border-border/80"
          >
            <div
              className="h-16"
              style={{
                backgroundColor: c.hex,
                // outline the lightest swatches against the dark card backdrop
                boxShadow: c.light
                  ? "inset 0 0 0 1px hsl(var(--border))"
                  : undefined,
              }}
            />
            <div className="bg-card px-3 py-2.5">
              <div className="text-xs font-medium text-foreground">
                {c.name}
              </div>
              <div className="font-mono text-[10.5px] text-muted-foreground">
                {c.hex}
              </div>
              {c.note && (
                <div className="mt-1 text-[10px] text-muted-foreground/80">
                  {c.note}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------- Built with ---------- */

function BuiltWith() {
  const credits = [
    [
      "SaltStack",
      "The underlying execution layer — Halite is a console on top of it.",
    ],
    ["Inter", "Wordmark and UI typeface, by Rasmus Andersson."],
    ["React + TanStack Router", "Frontend application layer."],
    ["FastAPI + Pydantic", "Backend HTTP layer."],
    ["shadcn/ui + Tailwind", "Component primitives and tokenized styling."],
    ["Lucide", "Icon set."],
    ["Recharts", "Charting layer for the Overview metrics."],
  ];
  return (
    <section className="flex flex-col gap-6">
      <SectionEyebrow>Built with</SectionEyebrow>
      <h2 className="text-3xl font-semibold tracking-tight">
        Standing on shoulders
      </h2>
      <ul className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2 max-w-3xl">
        {credits.map(([name, blurb]) => (
          <li key={name} className="flex items-start gap-3 text-sm">
            <span
              aria-hidden
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
            />
            <div>
              <span className="font-medium text-foreground">{name}</span>
              <span className="text-muted-foreground"> — {blurb}</span>
            </div>
          </li>
        ))}
      </ul>
      <p className="pt-6 text-xs text-muted-foreground">
        Halite is open infrastructure tooling — built for sysadmins and DevOps
        engineers who love a good console.
      </p>
    </section>
  );
}

/* ---------- Shared bits ---------- */

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
      {children}
    </p>
  );
}

function Divider() {
  return (
    <div
      aria-hidden
      className="mx-auto h-px w-full max-w-3xl bg-gradient-to-r from-transparent via-border to-transparent"
    />
  );
}
