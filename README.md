# Plinta

**Plinta** is a Django framework for building business applications on top of your own models. You register the models you already have and define who may see which rows and fields; Plinta supplies the rest through one permission engine that holds at every interface:

- screens people work in
- a REST API
- an AI assistant

Nothing to inherit from, no view or serializer per screen: an application is your models, your policies, and rows of configuration.

## Status

Design, not code. The sixteen discussions under *Documents* are the whole of it; this repository holds no package yet and nothing here installs. Build order step 1 is next. A screenshot arrives with step 4, when a page first renders.

Targets Python 3.12+ and Django 5.2+. MIT licence.

## The problem

Most business applications are built from the same parts:

- a list with filters, a form, a detail page, a dashboard, an export
- people who may see their own region and people who may see everything
- a column only managers may read
- an API for the ERP, a nightly job

Django gives you the models and the admin; the rest is written again for every model, and six months in the permission logic lives in eleven places and nobody is sure the export respects it. The tools that promise a way out each ask for something — a BI tool wants read-only SQL, a low-code platform wants your schema, an admin generator wants a base class. Plinta asks for nothing from your models, and puts the permission logic in one place that every interface goes through.

## Core — the engine

Four layers and a command line, each layer importing only what is below it. This is the product; everything else is a way of reaching it.

```
events → permissions → sources → writes
```

**events** — four signals around a write (`writing`, `written`, `deleting`, `deleted`) and a batch for many writes at once. Core emits; packages listen; nobody imports anybody. A listener that raises before the save vetoes it; one that raises after is logged and the write stands.

**permissions** — three tiers, all must hold: Django's model permission (*may they at all*), a row policy (*which rows* — a class per model, one method per action, each returning a `Q`), and field permissions (*which fields* — Django permissions, granted like any other). Imports only Django; usable on its own.

**sources** — a registered model and the fields Plinta may show of it, as rows an author edits: label, number format, whether it is editable, restricted, filterable. A field can be a path across a relation or a database expression, so a computed column sorts and filters in SQL. `rows(source, user)` and `fields(source, user)` are the only way anything above reads data, and both come back already narrowed by the user's permissions. Layouts — a source's fields in named groups — live here too, and serve forms, cards and the API alike.

**writes** — the one path by which Plinta changes your data. All of these call `write()`:

- a cell in a table
- a form
- a spreadsheet import
- a PATCH from the ERP
- "mark these as shipped" in the chat

It authorises, validates, saves, diffs and announces, in that order, every time. Three refusals — may not, cannot, invalid — with the field named. Because there is one path, "every change is attributable" is a fact about one function.

**the CLI** — `manage.py plinta rows sale --as mira`, `write … --set quantity=3`. The four functions from a terminal, always as a named user. It is how the engine is demonstrated before any interface exists, and how an operator answers "what does this user actually see?"

## Interfaces — how people and machines reach it

Every interface resolves *who is asking* at its edge and calls the same four functions. None adds to what a user may see or do; each changes how they ask. All are optional; an install enables the ones it needs.

```
   a person in a browser         a model in a chat            a machine
            │                          │                          │
        screens                   assistant · MCP               REST API
            └──────────────────────────┴──────────────────────────┘
                                       │
                 rows() · fields() · get() · write() · delete()
```

**screens** (`plinta.screens`) — pages built in the browser, no deploy.

- A page is a grid. On it you place a table, a chart, a form or a record card, each over one of your models.
- Nothing needs configuring to start: a table shows the fields the viewer may see, newest first. Everything can be configured later.
- A filter bar at the top narrows every card on the page. A filtered page is a link you can send.
- Anyone can save their own view of a table; with permission, publish it for everyone.
- Server-rendered with Bootstrap and Unpoly.

**REST API** (`plinta.api`) — for machines: an integration, a nightly job, a mobile app.

- Every registered model gets list, detail, create, update and delete under `/api/v1/`, plus a schema endpoint that says which fields the caller may see and change.
- An API key is a user. A key sees and changes exactly what that user could on a screen, nothing more.
- Filters, sorting and paging in the query string, the same way the filter bar works.
- Every call is logged; every write is audited like one from a form.

**AI assistant** (`plinta.ai`) — a chat panel on every page, acting as the person typing.

- Ask a question over your data and get an answer computed from the rows you may see.
- Describe a page — *"sales by store as a bar chart, the table below, filtered by store"* — and it exists, checked by the same validation a form runs.
- Ask for a change — *"mark these five as shipped"* — and it is prepared, shown to you, and saved only when you confirm.
- Ask why — *"why can't I see the total column?"* — and it tells you which permission you lack.
- The model never renders a page and never runs code. It writes rows; Plinta validates them. A page visit never calls a model.
- Claude by default; or a local open-source model that never leaves the building.

**MCP** (`plinta.mcp`) — the assistant's tools for hosts outside Plinta.

- Claude Desktop, a Copilot agent in Teams, or an agent you run yourself connects to `/mcp/` and uses Plinta as the signed-in user.
- Sign in once through Plinta's own login page; a token maps to a user, and the user's permissions decide everything after.
- Writes go through the same pipeline, with the host's approval prompt in place of the panel's confirm button. A deployment can leave the write tools out.

## Cards — what goes on a page

Each component is an app; list the ones you need. A third party's is registered the same way.

- **plinta.table** — Tabulator: sort, header filters, paging, inline edit, row selection for actions. Can spread a related model across columns — an order's steps, a production order's operations.
- **plinta.card** — one record, laid out the way an author arranged it in the browser.
- **plinta.form** — one record's editable fields, on a page or in a dialog.
- **plinta.chart** — Plotly: a field, an aggregate, bar or line, over the rows the viewer may see.
- **plinta.kpi** — one number.
- **plinta.pivot** — rows by one field, columns by another, an aggregate in the cells, totals; Flexmonster over the viewer's rows, licence supplied by the install. A pivot over another library registers the same way.
- **plinta.kanban** — cards in columns by a field's value; drag to change it.
- **plinta.matrix** — rows from one model, columns from another, cells from a third: books × stores × stock, machines × days × a note, a line of balance.
- **plinta.content** — text, alert, button, accordion: no data, just the page.

## Packages — what plugs in

Everything else is an app: listed in `INSTALLED_APPS` or not, nothing in core changed either way. Each plugs in the way a third party would — a policy, a listener, an action, a registration — and each is reachable from every interface the day it is installed: its models are sources, so screens, the API and the assistant see them.

**plinta.audit** — every write recorded: who, what changed, through which interface. Two listeners on the write signals and nothing else; uninstall it and writes carry on unaudited. Sensitive fields are redacted, not dropped. The log is a page, an export and an API endpoint, scoped so nobody sees an entry for a row they could not see.

**plinta.notifications** — in-app notifications with a bell, a list, mark-read and per-person preferences. Built entirely as listeners: a write, a comment, a workflow transition become a notification without any of those packages knowing. Email is a second channel.

**plinta.workflow** — states and transitions per model, as data authored in the browser. A transition is a button, a permission of its own, and a guard that also refuses the same change from the API. A state can lock fields — *rate cannot change once an order is closed* — with a permission a manager may hold to override. Approvals are two transitions and a state; nothing about them is code.

**plinta.automation** — "when this happens, do that", as a row: a model, an event, a filter, one effect. Effects are what other packages register — notify a group, post a webhook, run a transition, set a field — so a business user composes the rule and a developer wrote none of it. One trigger, one effect, no flow editor; anything with a branch is a listener.

**plinta.comments** — threaded comments on any record, with @mentions. Scoped by the record's own policy: you may comment on what you may see.

**plinta.organization** — company, site, business unit, and which of them a user belongs to. One policy helper — `InOrg(user, "store__site")` — scopes any model to the user's units. That is the whole of tenancy; core has no idea of a company.

**plinta.attachments** — files on any record, scoped by the record's policy. A count in a table, a list on a card, an upload on a form.

**plinta.import** — rows from a spreadsheet, each through `write()`: validated, permission-checked, audited, with a result per row.

**plinta.export** — the same rows a card shows as an Excel file, with real numbers and the field's number format. A button on a card, a command, or a schedule.

**plinta.reports** — an export on a schedule: a model, its fields, a filter, a cron, and recipients. Each recipient gets it as themselves — their stores, not the sender's — unless the sender holds the permission to send their own view. Delivered by notifications; runs are rows, so "did Monday's report go out" is a filter.

**plinta.webhooks** — the API in reverse. Subscribe a URL to a model's writes and receive a signed POST for each one, with retries and a delivery log. An ERP learns a sale changed without polling.

## What it is not

- **Not a BI tool.** It renders registered models, not SQL. Metabase does dashboards better.
- **Not no-code.** Developers own models, migrations and policies; admins own grants and rules; users own the screens.
- **Not a public website.** Every page is behind a login.
- **Not multi-tenant by default.** Tenancy is a package with one policy helper.

## Packaging

One wheel, one version:

```
pip install plinta                 # everything
pip install plinta[api,ai]         # extras pull the heavy dependencies: django-ninja, anthropic, mcp, openpyxl
```

```python
INSTALLED_APPS = [
    "plinta.events", "plinta.permissions", "plinta.sources", "plinta.writes",   # the engine
    "plinta.screens", "plinta.table", "plinta.chart",                            # an interface and two components
    "plinta.audit", "plinta.api",                                                # what this install wants
]
```

An app not listed contributes no models, URLs or listeners. Import paths are `plinta.<app>`, never `plinta.contrib.<app>`, and each app imports only what the layering allows — so the day one needs its own release cycle it becomes its own package with the same import path. A third party's app is its own package from the start.

## From install to a screen

What the build order makes true, in order — the sequence step 1 and step 4 are tested against.

```python
# settings.py
INSTALLED_APPS += ["plinta.events", "plinta.permissions", "plinta.sources", "plinta.writes", "plinta.screens", "plinta.table"]

# urls.py
urlpatterns += [path("", include("plinta.screens.urls"))]

# catalog/policies.py — who sees which sales
@register_policy(Sale)
class SalePolicy:
    def view(self, user):   return Q(store__in=user.stores.all())
    def change(self, user): return Q(store__in=user.stores.all())
```

```
$ manage.py migrate
$ manage.py runserver
```

Then in the browser: `/manage/sources/` → *Register* → `catalog | Sale`; `/manage/pages/new/` → *Place* a table over it. Or in the chat panel: *"a Sales page with the table."* Either way, `mira` opens `/p/sales/` and sees her store's rows; `noor` sees hers.

```
$ manage.py plinta rows sale --as mira        # the same rows, in a terminal
```

## Documents

Each part of the design is a discussion thread — read it, question it, propose changes in the thread. A code block in a thread is the intended implementation, not pseudo-code; a body left out is marked `...  # ~N lines`.

| layer | what it owns | discussion |
|---|---|---|
| 1. events | four write signals, `emit()`, `batch()`; contrib listens, core never imports contrib | [1-EVENTS.md](https://github.com/plinta-framework/plinta/discussions/1) |
| 2. permissions | model permission · row policy (`Q` per action) · field permission, minted from restricted fields · per-row field rules; imports only Django | [2-PERMISSIONS.md](https://github.com/plinta-framework/plinta/discussions/2) |
| 3. sources | a registered model and its fields as rows; `rows()` / `fields()` / `get()` already narrowed; annotations, renderers, placeholders, ranges, resolvers; layouts | [3-SOURCES.md](https://github.com/plinta-framework/plinta/discussions/3) |
| 4. writes | the one pipeline: authorise → validate → save → diff → emit; `Refused(403 | 405 | 422)`; the CLI | [4-WRITES.md](https://github.com/plinta-framework/plinta/discussions/4) |
| screens (an interface) | pages, placements, filters, saved views, the shell; the base class and registry a component plugs into; `plinta.screens`, imports the engine, nothing imports it | [5.1](https://github.com/plinta-framework/plinta/discussions/5) · [5.2](https://github.com/plinta-framework/plinta/discussions/6) · [5.3](https://github.com/plinta-framework/plinta/discussions/7) · [5.4](https://github.com/plinta-framework/plinta/discussions/8) · [5.5](https://github.com/plinta-framework/plinta/discussions/9) · [5.6](https://github.com/plinta-framework/plinta/discussions/10) · [6-COMPONENTS.md](https://github.com/plinta-framework/plinta/discussions/11) |
| packages | audit, ai, api, mcp in full; the rest one paragraph each | [7](https://github.com/plinta-framework/plinta/discussions/12) · [8](https://github.com/plinta-framework/plinta/discussions/13) · [9](https://github.com/plinta-framework/plinta/discussions/14) · [10](https://github.com/plinta-framework/plinta/discussions/15) · [11](https://github.com/plinta-framework/plinta/discussions/16) |

## Build order

Each step ends with the demo running and a test for its "done when".

| # | build | done when |
|---|---|---|
| 1 | `events`, `permissions`, `sources`, `writes`, the CLI, `as_user()` | a test writes a Sale as `mira` and `rows(source, noor)` does not return it; `manage.py plinta rows sale --as mira` prints it |
| 2 | `plinta.ai` with the data tools; `plinta.api` | *"what did Hale Street sell this month?"* answered in a terminal as `mira`, and `noor` gets Marsh Lane's number; the same over `/api/v1/` with a key |
| 3 | `plinta.screens` models only: Page, PageBlock, PageFilter, SavedView, FilterSet, Menu; the assistant's page tools | *"a Sales page with the table and a chart by store"* becomes rows that pass `clean()` — nothing renders yet |
| 4 | rendering: shell, `/p/` and `/b/`, filter bar, forms, saved views, detail pages, actions; `plinta.table`, `plinta.chart`, `plinta.form`, `plinta.card`, `plinta.content` | the page from step 3 opens in a browser; `mira` and `noor` see different rows; a filter narrows every card; a row opens a form, 422 re-renders, save reloads |
| 5 | composer, sources screen, layout editor; `plinta.audit`, `plinta.mcp` | `ada` builds a page by hand; the audit log shows what `mira` changed from the chat, the API and the form; Claude Desktop lists the same sources |
