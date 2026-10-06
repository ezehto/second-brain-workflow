# User request: the web app as a daily tool (verbatim, 2026-10-06)

I want you to improve the existing **Second Brain web app** so that it becomes a practical tool I can use every day for my work as a **Software Engineer and Solutions Architect**.

The goal is not to build a complicated productivity platform. The web app should make my daily work easier by helping me **organize, understand, execute, and improve my work**.

## Core Purpose

The Second Brain web app should help me:

1. **Help me decide**

   * Show important decisions that need attention.
   * Surface blockers, risks, pending approvals, and unresolved issues.
   * Provide enough context to make informed decisions.
   * Help me understand trade-offs when there are multiple options.

2. **Help me prioritize**

   * Show what needs my attention today.
   * Surface high-priority, overdue, blocked, and time-sensitive tasks.
   * Help me distinguish urgent work from important work.
   * Show priorities across projects, tasks, tickets, incidents, and follow-ups.

3. **Help me execute**

   * Track my daily tasks and ongoing work.
   * Track projects, tickets, milestones, and action items.
   * Show the current workflow or stage of each project.
   * Make it easy to update task status and record progress.
   * Provide quick actions for common activities.

4. **Help me understand**

   * Keep related project information, decisions, architecture, documents, incidents, and technical knowledge connected.
   * Show relationships between projects, tasks, tickets, documents, decisions, and activities.
   * Provide timelines and visual context where useful.
   * Make it easy to understand the current state of a project or problem.

5. **Help me learn**

   * Track my learning and upskilling activities.
   * Connect real work problems to skill gaps and learning topics.
   * Track what I am currently learning, practicing, and applying.
   * Help me identify areas where I should improve based on my actual work.

6. **Help me remember**

   * Record important decisions, lessons learned, technical findings, and useful knowledge.
   * Keep historical context for projects and tasks.
   * Make previous information easy to find through search, links, tags, and relationships.
   * Avoid requiring me to remember where information was stored.

7. **Help me improve**

   * Track recurring problems, mistakes, blockers, and lessons learned.
   * Identify patterns in my work and workflow.
   * Help me improve my engineering practices and productivity.
   * Support continuous improvement of both my skills and my workflow.

---

# Daily Use

The application should be designed around my **day-to-day workflow**, not just as a dashboard for displaying information.

When I open the application, I should immediately be able to understand:

* What should I work on today?
* What is my highest priority?
* What is blocked?
* What requires my attention?
* What meetings or DSU activities do I have?
* What projects are currently active?
* What is the current status of each project?
* What tasks are in progress?
* What decisions are pending?
* What follow-ups do I need to make?
* What did I accomplish recently?
* What am I currently learning?
* What should I improve next?

The application should help me move naturally from:

**Understand → Decide → Prioritize → Execute → Record → Learn → Improve**

---

# DSU / Daily Standup

The application should make recording and reviewing DSU updates very easy.

A DSU should support:

* Done
* Today
* Blockers
* Decisions / Updates
* Follow-ups
* Related projects
* Related tasks/tickets

It should also allow me to look back at previous DSUs and identify:

* Completed work
* Carry-over tasks
* Recurring blockers
* Repeated issues
* Progress by project
* Major decisions and updates

---

# Projects and Tasks

The application should provide both:

### Global View

Show my overall engineering workload across all projects.

### Project View

When I open a project, I should be able to see everything relevant to that project, including:

* Project status
* Current workflow/stage
* Tasks
* Tickets
* Blockers
* Milestones
* Decisions
* Meetings
* DSU updates
* Documents
* Architecture
* Incidents
* Deployments
* Activity timeline
* Related learning

The project view should make it possible to understand the project without searching through multiple unrelated pages.

---

# Visualizations

Use charts, diagrams, timelines, progress indicators, and other visualizations where they provide useful information.

Examples:

* Project progress
* Task status distribution
* Workload by project
* Completed vs pending work
* Blockers and risks
* Project timeline
* Engineering workflow
* Learning progress
* Skill gaps
* Activity trends
* Recurring issues

Do not add charts simply to make the dashboard look impressive.

**Every visualization should answer a useful question or help me make a decision.**

---

# UX / UI Requirements

The application should be **very easy and comfortable to use**.

Prioritize:

* Clear information hierarchy
* Simple navigation
* Minimal clicks
* Fast access to frequently used actions
* Readable typography
* Comfortable spacing
* Consistent components
* Clear status indicators
* Good visual grouping
* Easy scanning
* Responsive interactions
* Accessible design

The overall visual design should be **professional, modern, clean, and easy on the eyes**.

### Layout

Because this is a web application:

* Use the available screen space effectively.
* The application should feel like a complete desktop application rather than a narrow webpage.
* Avoid large unnecessary empty white spaces.
* Use responsive layouts that adapt naturally to different screen sizes.
* The desktop layout should take advantage of wide screens.
* The layout must remain usable on tablets and mobile devices.
* Do not simply shrink the desktop UI for mobile. Reorganize content when necessary.

### Typography

Fonts should be:

* Highly readable
* Comfortable for long periods of use
* Consistent throughout the application
* Properly sized for hierarchy and information density

### Colors

Use a restrained and professional color system.

Colors should primarily communicate:

* Status
* Priority
* Severity
* Success
* Warning
* Error
* Information

Avoid excessive colors, gradients, visual noise, or decorative styling.

### Information Density

The application should provide **high information density without becoming cluttered**.

Avoid:

* Excessive cards
* Huge headings
* Excessive whitespace
* Decorative charts
* Unnecessary animations
* Too many modals
* Deeply nested navigation
* Repetitive information
* Visual clutter

---

# Responsive Design

Design the application with responsive behavior from the beginning.

Desktop should support:

* Multi-column layouts
* Side navigation
* Dense project/task views
* Charts and diagrams
* Timelines
* Multiple information panels

Mobile should prioritize:

* Today's tasks
* Priorities
* Blockers
* DSU
* Quick actions
* Project status
* Important notifications/updates

Use responsive navigation and reorganize content when necessary instead of simply compressing the desktop layout.

---

# Important Implementation Rule

Before making major UI changes, **inspect the existing Second Brain web app first**.

Review:

* Existing pages
* Components
* Layouts
* Navigation
* Design system
* Fonts
* Colors
* Data models
* Existing functionality
* Current dashboard
* Responsive behavior
* Existing UX patterns

Reuse good existing components and patterns where appropriate.

Do not rebuild or replace working functionality without a clear reason.

Identify:

1. What is already working well
2. What is difficult to use
3. What is missing
4. What can be simplified
5. What should be redesigned
6. What should remain unchanged

Then propose the improvements before implementing major structural changes.

---

# Design Goal

The final web app should feel like my **personal Engineering Command Center**.

It should not simply store information.

It should actively help me:

**Decide → Prioritize → Execute → Understand → Learn → Remember → Improve**

The most important requirement is:

> **When I open the Second Brain, I should immediately know what matters, what I need to do, why it matters, what is blocked, what I have accomplished, and what I should improve next.**

Keep the implementation practical, maintainable, and aligned with the existing Second Brain architecture. Avoid over-engineering and unnecessary complexity.
