# User request (verbatim)

Please improve the **Dashboard UI/UX and overall web application experience** so that it functions as a practical **daily Engineering Operating Dashboard** for my work as a **Software Engineer / Solutions Architect**.

The dashboard should not simply display lists and tables. It should help me quickly understand **what is happening, what I need to do, what is blocked, what I am learning, and how my projects are progressing**.

## 1. Dashboard Goals

Design the dashboard around these questions:

* What do I need to work on today?
* What are my highest-priority tasks?
* What projects am I currently working on?
* What is the current status of each project?
* What is blocked or at risk?
* What meetings, DSUs, and follow-ups do I have?
* What engineering work have I completed?
* What am I currently learning?
* What skills should I improve based on my actual work?
* What decisions or action items are pending?
* What incidents, tickets, or technical issues need attention?
* What is my current workflow across projects?
* What requires my attention today?
* What should I focus on next?

The dashboard should provide this information **at a glance**, while allowing me to drill down into the details.

---

# 2. Dashboard Should Be Data-Driven

Use appropriate **charts, diagrams, visualizations, timelines, progress indicators, and status summaries** instead of presenting everything as tables.

Choose the visualization based on the type of information.

For example:

### Project Overview

Use:

* Project status cards
* Progress indicators
* Project health indicators
* Milestone timelines
* Task completion charts
* Blocker indicators
* Project activity timelines

Example:

```text
Project
 ├── Progress
 ├── Tasks
 ├── Tickets
 ├── Blockers
 ├── Milestones
 ├── Recent Activity
 ├── Decisions
 └── Next Actions
```

---

# 3. Project Visualization

For each project, provide a visual overview of:

* Overall status
* Progress
* Current phase
* Active tasks
* Completed tasks
* Blocked tasks
* Open tickets
* Upcoming milestones
* Recent activity
* Recent decisions
* Related meetings
* Related documents
* Related deployments
* Related incidents
* Related learning

Consider useful visualizations such as:

* Progress bars
* Status distribution charts
* Timeline/Gantt-style views where appropriate
* Activity timelines
* Dependency diagrams
* Project relationship diagrams
* Milestone views
* Workload views

Do not use charts just for decoration.

Every visualization should help answer a real engineering question.

---

# 4. DSU / Daily Standup Dashboard

Create a dedicated **DSU / Daily Standup view**.

It should make it easy to see:

```text
Yesterday / Done
Today / Planned
Blockers
Decisions / Updates
Follow-ups
```

Visualize useful information such as:

* Completed work
* Carry-over tasks
* Blocked items
* Recurring blockers
* Work completed by project
* Work planned for today
* Outstanding follow-ups

Allow me to quickly create or update the day's DSU.

The system should connect DSU items to:

* Tasks
* Projects
* Tickets
* Meetings
* Decisions
* Follow-ups

---

# 5. Task Management

The dashboard should make daily task management extremely easy.

Provide:

* Today's tasks
* Upcoming tasks
* Overdue tasks
* High-priority tasks
* Blocked tasks
* Tasks requiring review
* Recently completed tasks
* Tasks grouped by project
* Tasks grouped by type

Useful visualizations:

* Task status distribution
* Priority distribution
* Completion trends
* Tasks by project
* Tasks by workflow stage

Use quick actions such as:

```text
+ Task
+ Ticket
+ Follow-up
+ Decision
+ Note
```

Minimize the number of clicks required for common actions.

---

# 6. Engineering Workflow Visualization

One of the most important features should be the ability to see the **current workflow**.

Support both:

### Global Workflow

Show what I am currently working on across all projects.

Example:

```text
Inbox
  ↓
Planning
  ↓
Implementation
  ↓
Testing
  ↓
Review
  ↓
Blocked / Rework
  ↓
Completed
```

### Project Workflow

Allow me to select a project and see its current workflow.

Example:

```text
Requirements
      ↓
Architecture
      ↓
Planning
      ↓
Implementation
      ↓
Testing
      ↓
Code Review
      ↓
Deployment
      ↓
Validation
      ↓
Complete
```

Clearly show:

* Current stage
* Completed stages
* Blocked stages
* Failed stages
* Rework loops
* Pending approvals
* Next action

The visualization should reflect the **closed-loop engineering workflow** defined in the master plan.

For example:

```text
Implementation
      ↓
Testing
      ↓
Test Failed
      ↓
Analyze Failure
      ↓
Implementation
      ↓
Testing
```

or:

```text
Code Review
      ↓
Review Failed
      ↓
Replan
      ↓
Implementation
      ↓
Testing
      ↓
Review
```

This should help me understand **where work is stuck and why**.

---

# 7. Learning / Upskilling Dashboard

Create a dedicated **Engineering Upskilling** section.

It should show:

* Current learning topics
* Skills being developed
* Current learning goals
* Practice activities
* Skills applied to real projects
* Recently learned topics
* Identified skill gaps
* Recommended next learning activities
* Progress against my existing 4-month roadmap

Visualize:

* Learning progress
* Skills by category
* Learning activity over time
* Skill gaps
* Skills applied to projects

Example relationship:

```text
Production Problem
       ↓
Skill Gap
       ↓
Learning Topic
       ↓
Practice
       ↓
Apply to Project
       ↓
Review
       ↓
Lesson Learned
```

The system should connect learning to **actual engineering work** rather than treating learning as a separate to-do list.

---

# 8. Engineering Activity Timeline

Create a unified timeline showing important engineering activity.

Potential events:

* Task created
* Task completed
* Jira ticket updated
* Meeting
* DSU
* Commit
* Pull Request / Merge Request
* Code review
* Deployment
* Incident
* Architecture decision
* Document created
* Learning activity
* Knowledge captured

Allow filtering by:

* Project
* Date
* Activity type
* Source
* Person
* Status

This should provide a useful historical view of how work progressed.

---

# 9. Project Health

Provide a simple project health overview.

Possible indicators:

* On Track
* At Risk
* Blocked
* Delayed
* Completed

Use supporting information such as:

* Open blockers
* Overdue tasks
* Outstanding tickets
* Failed tests
* Pending reviews
* Pending approvals
* Upcoming deadlines
* Recent incidents

Do not create arbitrary health scores without explaining how they are calculated.

If health cannot be confidently determined, display:

**Unknown / Insufficient Data**

rather than guessing.

---

# 10. Technical / Architecture Visualization

Since this dashboard is also for my Solutions Architect responsibilities, include useful technical visualizations where appropriate.

Examples:

* System architecture diagrams
* Service relationships
* API relationships
* Integration maps
* Data flow diagrams
* Project dependencies
* Infrastructure relationships
* Deployment flow
* Environment overview

Keep diagrams readable.

Avoid:

* Spaghetti diagrams
* Excessively long arrows
* Overcrowded nodes
* Unnecessary technical details

Allow users to drill down from a high-level diagram into more detailed information.

---

# 11. Documents and Knowledge

Provide quick visibility into:

### Documents

* Draft documents
* Documents requiring review
* Recently completed documents
* Change Requests
* Proposals
* Architecture Documents
* Technical Designs
* Incident Reports
* Status Reports

### Knowledge

* Recently captured knowledge
* Lessons learned
* Architecture decisions
* Troubleshooting notes
* Engineering patterns
* Frequently referenced knowledge

Allow relationships between:

```text
Project
 ↓
Task
 ↓
Ticket
 ↓
Document
 ↓
Decision
 ↓
Knowledge
```

---

# 12. Daily Focus

The dashboard should have a prominent **Today's Focus** section.

It should intelligently summarize:

* Top priorities
* Important meetings
* Blockers
* Tasks requiring attention
* Pending reviews
* Pending approvals
* Follow-ups
* Learning focus

Keep this concise.

I should be able to open the dashboard and understand what matters **within a few seconds**.

---

# 13. Quick Actions

Make common actions easily accessible.

Examples:

```text
+ Task
+ Ticket
+ Project
+ DSU
+ Meeting Note
+ Decision
+ Incident
+ Document
+ Knowledge
+ Learning
```

Also provide context-aware actions.

For example, when viewing a Jira ticket:

```text
Create Task
Create Note
Create Decision
Create Follow-up
Link to Project
Start Implementation
```

---

# 14. Global vs Project Context

The dashboard should support two levels of context.

## Global View

Shows:

* All projects
* All tasks
* Overall workload
* Current workflow
* Learning
* Blockers
* Meetings
* Engineering activity
* Claude usage

## Project View

Shows only information related to the selected project:

```text
Project
├── Overview
├── Tasks
├── Tickets
├── Workflow
├── Timeline
├── Architecture
├── Documents
├── Decisions
├── Incidents
├── Deployments
├── Knowledge
└── Learning
```

Switching between global and project context should be effortless.

---

# 15. Search

Provide powerful global search across:

* Obsidian
* Projects
* Tasks
* Tickets
* Documents
* Knowledge
* Decisions
* Meetings
* External integrations

Clearly indicate the source of each result.

---

# 16. UI/UX Requirements

The application should feel like a **professional engineering tool**, not a generic productivity dashboard.

Prioritize:

* Clean interface
* Clear hierarchy
* Fast navigation
* Minimal clicks
* Strong search
* Keyboard-friendly workflows
* Responsive layout
* Consistent components
* Clear status indicators
* Useful empty states
* Useful loading states
* Clear error states
* Accessible interactions

Avoid excessive:

* Cards
* Gradients
* Decorative charts
* Animations
* Modals
* Nested navigation
* Visual clutter

The dashboard should prioritize **information density without sacrificing readability**.

---

# 17. Information Hierarchy

Prioritize information in this order:

### Level 1: What needs my attention?

* Blockers
* High-priority tasks
* Overdue items
* Pending reviews
* Pending approvals
* Critical incidents

### Level 2: What am I working on?

* Active projects
* Current workflow
* Today's tasks
* Upcoming meetings

### Level 3: What is happening?

* Activity
* Project progress
* Tickets
* Deployments
* Documents

### Level 4: How am I improving?

* Learning
* Skill gaps
* Practice
* Lessons
* Engineering improvements

---

# 18. Dashboard Layout

Create a practical default layout similar to:

```text
┌──────────────────────────────────────────────────────┐
│ Header / Search / Quick Actions / Profile            │
├──────────────────────────────────────────────────────┤
│ TODAY                                                │
│ Focus | Blockers | Meetings | Pending Reviews        │
├──────────────────────────────────────────────────────┤
│ TASKS                    │ PROJECTS                  │
│ Today's Tasks            │ Active Projects           │
│ Overdue                  │ Project Health             │
│ Blocked                  │ Progress                   │
├──────────────────────────┴───────────────────────────┤
│ ENGINEERING WORKFLOW                                  │
│ Global Workflow / Current Work / Blocked / Rework    │
├──────────────────────────────────────────────────────┤
│ PROJECT ACTIVITY / TIMELINE                           │
├──────────────────────────────────────────────────────┤
│ LEARNING & UPSKILLING                                 │
│ Skills | Learning | Practice | Roadmap               │
├──────────────────────────────────────────────────────┤
│ KNOWLEDGE / DECISIONS / DOCUMENTS                     │
├──────────────────────────────────────────────────────┤
│ CLAUDE USAGE / SYSTEM / INTEGRATIONS                  │
└──────────────────────────────────────────────────────┘
```

Do not treat this exact layout as mandatory.

Use it as a starting point and improve it based on usability.

---

# 19. VISUALIZATION PRINCIPLES

Every chart or diagram must answer a question.

Examples:

### Good

"How many tasks are currently blocked?"

→ Status distribution chart.

"Which projects require the most attention?"

→ Project workload/status view.

"Where am I spending engineering effort?"

→ Work distribution visualization.

"What skills am I actively developing?"

→ Skills/learning visualization.

"Where is this project stuck?"

→ Workflow diagram.

"What happened to this project over time?"

→ Activity timeline.

### Avoid

Charts that exist only because the dashboard needs to look impressive.

Do not add visualizations that do not provide actionable information.

---

# 20. CLOSED-LOOP WORKFLOW VISUALIZATION

The UI must make the engineering feedback loop visible.

A workflow item should be able to move:

```text
PLANNING
   ↓
IMPLEMENTATION
   ↓
TESTING
   ↓
REVIEW
   ↓
COMPLETE
```

But it can also move backward:

```text
TEST FAILED
   ↓
IMPLEMENTATION
```

```text
REVIEW FAILED
   ↓
IMPLEMENTATION
```

```text
DESIGN ISSUE
   ↓
PLANNING
```

```text
REQUIREMENT ISSUE
   ↓
UNDERSTANDING
```

The UI should visually communicate:

* Current stage
* Previous stage
* Next stage
* Failure reason
* Rework count
* Blocker
* Owner
* Required action

This should work both globally and within each project.

---

# 21. DAILY WORKFLOW

The application should support a simple daily flow:

```text
START DAY
   ↓
Review Dashboard
   ↓
Review DSU
   ↓
Review Meetings
   ↓
Review Blockers
   ↓
Select Today's Focus
   ↓
Work
   ↓
Capture Tasks / Decisions / Knowledge
   ↓
Update Workflows
   ↓
Review
   ↓
EOD
   ↓
Update Second Brain
```

The dashboard should make this workflow easy to follow without forcing unnecessary process.

---

# 22. DESIGN FOR MY ACTUAL ROLE

The UI must support both sides of my role:

## Software Engineer

I need to manage:

* Coding
* Debugging
* Testing
* Code review
* Tickets
* Deployments
* Incidents
* Technical debt
* Performance
* Security
* APIs
* Databases

## Solutions Architect

I need to manage:

* Architecture
* System design
* Technical proposals
* Solution designs
* Change requests
* Integration design
* Technical decisions
* Project dependencies
* Stakeholder communication
* Technical risks
* Implementation planning

The dashboard should make switching between these contexts easy.

---

# 23. OBSIDIAN INTEGRATION

Remember:

> **Obsidian is the canonical Second Brain.**

The dashboard should visualize and manage information stored in Obsidian without making the web app the primary source of truth.

The web app may:

* Index
* Search
* Visualize
* Aggregate
* Analyze
* Provide convenient editing
* Provide dashboards
* Provide analytics

But knowledge must remain usable from the Obsidian vault independently.

---

# 24. IMPLEMENTATION APPROACH

Before implementing the dashboard:

1. Inspect the existing project.
2. Inspect the existing master plan.
3. Inspect the existing Obsidian structure.
4. Inspect existing data models.
5. Inspect existing UI components.
6. Inspect existing design system.
7. Identify reusable components.
8. Identify missing functionality.
9. Design the dashboard information architecture.
10. Design the navigation.
11. Design the project/global context model.
12. Design visualization requirements.
13. Identify data dependencies.
14. Identify unknowns.
15. Identify decisions requiring approval.
16. Then implement incrementally.

Do not rebuild existing functionality unnecessarily.

---

# 25. IMPORTANT

Do not turn the dashboard into a complicated project-management system.

The goal is:

> **A simple, powerful engineering command center that helps me understand my work and take action quickly.**

Every feature should satisfy at least one of these goals:

* Help me decide
* Help me prioritize
* Help me execute
* Help me understand
* Help me learn
* Help me remember
* Help me improve

If a feature does not provide meaningful value, do not add it.

The final UI/UX should feel like a **personal Engineering Command Center** for my daily work as a Software Engineer and Solutions Architect, with **Obsidian as the underlying Second Brain and Claude Code as the intelligence/workflow engine**.
