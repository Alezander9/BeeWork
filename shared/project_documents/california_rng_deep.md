# California Renewable Gas Industry

## Objective

Build an in depth knowledge base on the California renewable gas (RNG) industry. Cover all the major companies, their role in the industry, key regulations, and market dynamics. You should use the web search tool after your initial research to find specific information.

## Knowledgebase Structure
This is a rough sketch of what the knowledge base structure shuold look like. You can modify it as needed.

```
knowledgebase/
  README.md
  companies/
    <company-name>.md
  industry_overview/
  regulations/
```

## Research Requirements

For each company: brief overview, what they do, key projects in California, and any regulatory involvement.

Regulations should include data about different regulatory programs. 

It is important that their is a mix of specific citeable information as well as broad summaries.

## Scope

Create research tasks: For each file in the knowledge base, create 3–10 separate research tasms. Each task should target the same file but cover a different subtopic and use a different website as its source. Do NOT create only one task per file — a single source produces shallow, one-sided content. For example, for a company file like knowledgebase/companies/socalgas.md, you would spawn separate agents that target the same file but use different websites as their source, or try to find different information on the same website:

- Agent 1 (company's own site): --topic "SoCalGas overview" --websites "https://www.socalgas.com"
- Agent 2 (regulator): --topic "SoCalGas regulatory filings" --websites "https://www.cpuc.ca.gov"
- Agent 3 (news): --topic "SoCalGas RNG news" --websites "https://www.reuters.com"

