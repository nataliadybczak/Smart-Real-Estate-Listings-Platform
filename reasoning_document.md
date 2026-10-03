# Reasoning document

## SmartListings - Search the way you think

Some of us know exactly what our perfect flat looks like and can easily turn it into filters. Others can't quite define what they want and would happily get suggestions based on their situation. And some of us struggle to choose between similar offers and are tired of juggling a dozen open tabs. SmartListings has a solution for each of them - a platform built to help people find their dream place in the most comfortable way:

- **Filters beyond price and area** - you can filter by facts hidden in sellers' descriptions: elevator, balcony, parking, condition.
- **A chat that understands your life** - you can describe your situation (e.g. "We are a couple of programmers and need separate rooms for our home offices") and receive offers that fit, together with the reasoning.
- **Compare instead of switching tabs** - you can open any offer and compare it side by side with similar ones, with the best parameters highlighted.

## Why I decided to use Python

I built it in Python instead of TypeScript, mainly because it's the language I feel most fluent in - with a suggested 6-hour limit, that meant cleaner code and better control. As data processing was a substantial part of the task, Python fit more naturally than TypeScript, so I could use httpx and selectolax for scraping and Pydantic for validation. Also, FastAPI keeps the type safety I would get from TypeScript and generates API documentation automatically. SQLAlchemy with Alembic gave me versioned MySQL migrations, so the local and production databases share one schema.

## What data I extracted and why

First, I did quick research on how listing data is structured on different real-estate platforms. Direct requests to Otodom returned HTTP 403, while Sprzedajemy.pl was accessible without browser automation so I decided it would be a better choice for this task. Its robots.txt allows listing pages, and its data is realistically messy, which was supposed to be the challenge of this task. I scraped 150 offers from Kraków, a margin in case some turned out to be of poor quality. I kept price, area, rooms, floor, market, year built, location, building type and ownership, which are present in most offers. Rare fields (e.g. heating in 19% of offers, roof type in 3%) go into one JSON column shown only on the detail page.

## How I handled unstructured or low-quality data

I flagged suspicious offers instead of assuming they were wrong. Of 150 listings, 146 were unique and 141 clean enough for statistics. Flagged values, such as 47 m² for 5.8M PLN or a share of a flat instead of the whole flat, stay visible with a warning but are excluded from medians. Free-text locations were matched to Kraków's 18 districts. For duplicates, similar text wasn't enough, because one developer reused a description for about 15 different flats. A duplicate also needs matching rooms, floor, area and price.

## Where and why I used AI

**In the product:** I noticed that important details that may matter for buyers (e.g. elevator, balcony, monthly fee) exist only in free-text descriptions and keywords can fail on meaning ("winda" also matches "brak windy", no elevator). In my project a Gemini model extracts them into a fixed JSON schema, validated with Pydantic, with "unknown" instead of guessing if something is not mentioned explicitly. It also writes short English summaries. In the chat search the model parses the user's sentence into a schema. Deterministic rules decide what it means in our data ("about 40 m²" → 35–45 m², "cheap" → cheapest 25% by price per m²).

**In the development process:** I used AI tools for source research, assessment of data, coding, reviewing edge cases and writing tests.

## Key assumption

I assumed the seller's description is the best available source for features without a structured field. In my project I decided that silence means "unknown", not "no". A flat whose listing doesn't mention an elevator is not shown as having none. It just doesn't match that filter. I believe in this case it was sensible to trade recall for trust.

## Success metric for the product

What I consider a success metric for the product would be contact rate per listing view (the share of listing page visits that end with a click on “Contact the seller” button. A real-estate portal brings value when a buyer and a seller actually connect and this is what this metric can capture. If there are properly structured facts and filters, buyers do not open listings that don’t fit so each visit is more likely to lead to contact.

## Limitation of my approach

The data is a one-time snapshot from a single source: prices change, flats sell, and a redesign of the source site would break the scraper. The free LLM tier was also sometimes overloaded (503). The enrichment job retries and resumes, and browsing never depends on the LLM, but the process can be delayed.

## What I would improve

I think I would add a daily scrape that detects sold listings and price drops, which is also a useful alert feature for users. With data collected over time, the platform could also show market statistics - how prices per m² change in each district and how long flats stay on the market - so buyers know whether an offer is really a good deal. I would also extend the AI search with neighbourhood context, so a user could ask for "a quiet area, good for a family with kids". To keep the same principle as with "cheap", this would be based on real data (e.g. schools, kindergartens and parks nearby from OpenStreetMap, or the city's noise map).
