export default function Loading() {
  return (
    <main id="main-content" className="shell" aria-busy="true">
      <header className="catalog-heading">
        <div className="catalog-heading-copy">
          <span className="h-4 w-28 animate-pulse rounded bg-[color:var(--subtle)]" />
          <span className="mt-4 block h-12 w-3/4 animate-pulse rounded bg-[color:var(--subtle)]" />
          <span className="mt-4 block h-5 w-full max-w-3xl animate-pulse rounded bg-[color:var(--subtle)]" />
        </div>
      </header>
      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        {[1, 2, 3].map((item) => <span key={item} className="h-24 animate-pulse rounded-[9px] bg-[color:var(--subtle)]" />)}
      </section>
      <section className="mt-8 grid gap-3">
        {[1, 2, 3, 4].map((item) => <span key={item} className="h-20 animate-pulse rounded-[9px] bg-[color:var(--subtle)]" />)}
      </section>
    </main>
  );
}
