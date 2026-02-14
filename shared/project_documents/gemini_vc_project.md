This Project Requirements Document (PRD) is designed to structure your "Killer Demo." It focuses on Browserbase, a real, hyped developer tool startup (Headless Browsers for AI Agents). This target is perfect because it appeals to VCs (it's AI infra) and requires "deep" research (it's technical).

Project Name: Due Diligence "Red Flag" Report: Browserbase
Target Audience: Venture Capital Associates & Partners
Objective: Determine if Browserbase is a "Unicorn" or a "Wrapper" by verifying their team, tech, and traction claims using stealth agents.

1. Core Research Modules
These are the specific "buckets" of information the Knowledgebase must populate.

A. The "Real" Team Directory (Stealth & Auth)
The VC Question: "Is this an engineering-led company, or a sales-led company? Do they actually have AI talent?"

Source: LinkedIn (requires login/stealth).

Agent Task:

Search for all employees listing "Browserbase" as current employer.

Categorize them: Engineering vs. Sales/Marketing.

Red Flag Check: Flag if the "Head of AI" has less than 2 years of experience or if >50% of the company is Sales.

Output: "Detected 18 employees. 12 Engineers, 4 Sales. 3 PhDs on staff. Verdict: Heavy Engineering Culture."

B. Competitive Landscape (Skepticism)
The VC Question: "Who else is doing this? Why will they lose?"

Sources: Reddit (r/webscraping, r/saas), Hacker News (Algolia search), G2.

Agent Task:

Search for "Browserbase alternatives" or "Browserbase vs".

Identify key competitors (e.g., Browserless, Hyperbrowser, Apify).

Sentiment Analysis: Find comments with negative sentiment or "switching" stories.

Output: "Main competitor: Browserless. Reddit users complain Browserbase is 'expensive for hobbyists' but 'better for anti-bot.' Moat risk: High pricing."

C. "Hype" vs. Reality (Speed)
The VC Question: "Is the buzz organic or paid?"

Sources: Product Hunt, Twitter/X, GitHub.

Agent Task:

Product Hunt: Check upvotes vs. comment quality (are comments generic "Great job!" or specific technical questions?).

Twitter: Search for "$BROWSERBASE" or mentions by key tech influencers (e.g., Guillermo Rauch, Vercel dev rels).

Output: "Launch Day: #1 Product of the Day. 500+ Upvotes. Endorsed by Vercel VP on Twitter. Hype: Organic & High."

D. Corporate & IP (Navigation)
The VC Question: "Do they own their IP? Is the entity clean?"

Sources: USPTO (United States Patent and Trademark Office), Crunchbase, Y Combinator Directory (if applicable).

Agent Task:

USPTO: Search for assignee "Browserbase Inc" or founders' names.

Crunchbase: Verify funding rounds (Series A? Seed?).

Output: "0 Patents Found (Common for early-stage software). Raised $6.5M Seed led by [VC Name]. IP Status: Unprotected/Trade Secret."

2. The "VC Alpha" Searches (The Killer Features)
These are the "Cool Searches" that will make a VC sit up and say "Wait, you can check that?" These demonstrate your unique browser capabilities.

A. The "Ghost Town" Check (GitHub & NPM Stats)
Why: VCs need to know if developers are actually using the tool, not just talking about it.

Agent Task:

Go to NPM (Node Package Manager). Search for the browserbase package.

Extract: Weekly Downloads chart.

Reviewer Skepticism: Compare the download graph to the "Funding Announcement" date. Did usage drop off after the PR blitz?

Display:

Insight: "Downloads spiked in Nov, but have flatlined at 2k/week. Warning: Retention risk."

B. The "Discord Lurker" (Auth & Stealth)
Why: The truest source of customer headaches is the support channel.

Agent Task:

Locate the "Join our Discord" link on their footer.

Auth: Log in with a burner Discord account.

Navigate: Go to the #bugs or #support channel.

Count: Measure the volume of messages in the last 24 hours.

Insight: "Active Community: 50+ messages in #support today. 3 users complaining about 'Timeout Errors'. Technical Stability: Moderate."

C. The "Status Page" History (Deep Navigation)
Why: Startups hide their downtime. VCs want to know if the product breaks.

Agent Task:

Find status.browserbase.com (or similar).

Scroll/Click: Navigate back 90 days.

Count: Number of "Major Outages."

Insight: "99.9% Uptime claimed, but Status Page shows 4 'Partial Outages' in the last month. Reliability: Questionable."

3. Demo Flow Script
User Prompt: "Perform due diligence on Browserbase. I want to know if their 'Headless Browser' tech is defensible and if devs are actually using it."

Step 1 (Stealth): Agent quietly maps the team on LinkedIn.

System Log: "Bypassed LinkedIn auth wall. Parsed 22 profiles."

Step 2 (Traction): Agent checks NPM and GitHub.

System Log: "Accessed NPM Registry. Weekly downloads: 4,500. Growth: +10% WoW."

Step 3 (Skepticism): Agent scans Reddit for "Browserbase expensive".

System Log: "Found 3 threads. Summary: Users love the feature set but are switching to 'Stagehand' for cost."

Final Report: A clean dashboard showing Team Quality (A), Traction (B+), Defensibility (C).

4. Next Step for You
Would you like me to write the JSON schema or Prompt Templates for the agents to execute these specific tasks? (This would be the code you feed into your system).