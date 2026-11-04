# CLAUDE.md: Cosmic Mart Returns Dashboard

This file is persistent context for Claude Code. Read it fully before writing or changing any code in this workspace.

## 1. Ground rules

- **Do not invent anything.** Do not make up business rules, field values, metrics, units, branding, or company facts. If something is not in this file or in files in the workspace, ask the user.
- **Stay in scope.** Build only the dashboard described in Section 3. Do not add pages, features, or integrations that are not listed.
- **Use the Anthropic Frontend Design skill** for all visual and UI work. If it is not available in this environment, tell the user and ask how to proceed before designing.
- **Ask before assuming.** Section 9 lists open items. Ask the user about an open item before implementing anything that depends on it.

## 2. Client context: Cosmic Mart

Source: *Cosmic Mart Business Case v1* (Accenture case study). Only facts from that document are listed here.

- Cosmic Mart is a retail company founded in 2001 by Taylor Hillman and Riley Lopez. It launched on Earth in 2021.
- It serves 144 million customers across 10 core markets on Earth.
- It sells through an online platform, a mobile app, and physical stores (omnichannel).
- Earth-based product offerings: technological gadgets, fashion and apparel, and home and lifestyle.
- It states a commitment to eco-friendly practices, including sustainable shipping and environmentally conscious product sourcing.
- Its strategic priorities are: (1) Innovation and technology through Gen AI adoption, (2) Cost optimization through AI-driven supply chain management, (3) Sustainability and responsibility leveraging AI, and (4) Customer-centric engagement.
- The case study notes carbon emissions as an opportunity for improvement relative to peers.
- A "complicated return policy" appears among the negative customer topics in the case study's Voice of Customer section.
- Revenue figures in the case study are in USD. This does not confirm the currency for this dashboard (see Section 9).

The business case does **not** contain return data, return fields, approval rules, or report metrics. Everything about returns in this file comes from the user, not the case study.

## 3. My scope (what this project is)

I am responsible for one part of a larger Cosmic Mart presentation: an **HTML dashboard that Cosmic Mart employees use to manage returned items**.

An AI agent produces a recommendation for each returned item. An employee reviews each recommendation and **confirms it**. The dashboard supports that human review.

The dashboard has three tabs:

1. **Return Queue**
2. **Approved Returns**
3. **Quarterly Reports**

## 4. Files and structure

Build exactly these files in the project root:

```
/
├── CLAUDE.md
├── index.html      # Markup and tab structure
├── styles.css      # All styling
├── script.js       # All behavior and state
└── queue.json      # Local data source (named "queue")
└── quarterly_report.json      # Local quarterly report data source
```

- Use plain HTML, CSS, and JavaScript. Do not add a framework or build step unless the user approves.
- Whether external libraries (for example a chart library) are allowed has **not** been decided. Ask before adding any (see Section 9).
- Load data from `queue.json` and `quarterly_report.json` in `script.js`. Browsers usually block `fetch` of local files when `index.html` is opened directly from disk, so tell the user if a local server is needed.

## 5. Tab requirements

### 5.1 Return Queue

Shows returned items waiting for human confirmation of the agent's recommendation.

The user can:

- **View** the list of returns in the queue
- **Search** returns
- **Filter** returns
- **Sort** returns
- **Open details** for a return
- **Approve** a return (confirms the agent's recommendation). Approving moves the return to Approved Returns.
- **Edit** a return

### 5.2 Approved Returns

Shows returns that have been approved.

The user can:

- **View** approved returns
- **Search and filter** approved returns
- **Reopen** a return. Reopening **sends the return back into the Return Queue**.

### 5.3 Quarterly Reports

The user can view:

- **KPIs**
- **Charts**
- **Tables**

The report covers three metrics:

1. **Money saved**
2. **Carbon emissions reduced**
3. **Pounds of waste disposed**

Each metric is **compared to previous quarters** to show improvement. Comparison is by **quarter, not by month**.

## 6. Return data model

Every return record has **all** of the following fields. These are the fields the user confirmed:

| Field | Notes |
|---|---|
| Return ID | |
| Product | |
| Category | |
| Return reason | |
| Condition | |
| Date received | |
| Status | Queue vs. approved. No other status values are defined. |
| Recommended disposition | The agent's recommendation. The employee confirms it. |
| Expected recovery value | |
| Carbon impact | |
| Risk or confidence flag | |

Rules:

- Do not invent allowed values for any field (for example a list of dispositions, conditions, or categories). Use only values the user provides. If sample data needs values and none are provided, ask.
- Do not invent a recovery-value, carbon, or risk calculation. These values come from the data.

## 7. Workflow and behavior

- The agent recommends. The **human employee confirms**.
- **Approve:** Queue → Approved Returns.
- **Reopen:** Approved Returns → Queue.
- Every button must work. Do not ship placeholder controls.
- Counts, lists, and any numbers that depend on queue/approved state must update immediately when a return moves between tabs.
- **Persistence:** `queue.json` is a local file and cannot be written to from the browser. For now, keep changes in browser state. Whether changes should survive a page reload is **undefined** (see Section 9). Do not add `localStorage` or a backend without asking.

## 8. Design requirements

Use the **Anthropic Frontend Design skill** for all visual work.

### Color

- **White:** primary background
- **Purple:** branding (headers, active tab, primary buttons, accents)
- **Black:** text
- **Green:** allowed to show **improvement**
- **Red:** allowed to show **urgency**
- Do not introduce other colors without asking. Exact hex values were not provided. Choose them during design and tell the user which you used.

### Experience

- **Responsive for screens of any size**, from small phones to large desktops. Check tables and charts on narrow screens.
- **Clean and professional.** Interaction points (buttons, tabs, search, filters, sorting, detail views, edit controls) should feel polished and consistent.
- **No over-the-top animations.** Keep any motion minimal (for example subtle hover or transition states).
- No logo, font, or brand assets were provided. Do not invent a Cosmic Mart logo. Ask whether any exist.

## 9. Open items: ask the user before implementing

1. **Editable fields.** Which fields can be changed when the user clicks Edit on a return?
2. **Search, filter, and sort fields.** Which fields should be searchable, filterable, and sortable?
3. **Units and currency.** What currency applies to money saved and expected recovery value? What unit applies to carbon (for example kg or lbs CO₂e)? Waste disposed is in pounds.
4. **Direction of improvement for waste.** Confirm that a *lower* pounds-of-waste-disposed figure counts as improvement, while higher money saved and higher carbon reduced count as improvement.
5. **Quarterly data source.** Where does the historical quarterly data for the reports come from? Is it in `queue.json`, a separate file, or derived from approved returns? How many past quarters, and which quarters, should be shown?
6. **Sample data.** Will the user provide `queue.json` content? If not, ask what sample data to create. Label any synthetic data as sample data.
7. **Persistence.** Should approvals, reopens, and edits survive a page reload?
8. **External libraries.** Are chart libraries or icon libraries allowed?
9. **Branding assets.** Are there any logos, fonts, or exact color values?
10. **Browser, accessibility, and testing expectations.** None were specified. Ask what the target is.

## 10. Definition of done

The dashboard is done when:

- [ ] `index.html`, `styles.css`, `script.js`, and `queue.json` exist and work together.
- [ ] All three tabs render and switch cleanly.
- [ ] The Return Queue supports view, search, filter, sort, details, approve, and edit.
- [ ] Approved Returns supports view, search/filter, and reopen, and reopening returns the item to the queue.
- [ ] Quarterly Reports shows KPIs, charts, and tables for money saved, carbon emissions reduced, and pounds of waste disposed, each compared to previous quarters.
- [ ] Every return record contains all fields in Section 6.
- [ ] Color usage follows Section 8, and the layout works at any screen size.
- [ ] Every button and control works, and no animations are excessive.
- [ ] No invented business facts. All assumptions were confirmed with the user or listed in the final summary.
