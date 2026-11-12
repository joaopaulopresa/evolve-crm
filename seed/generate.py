"""Generate the synthetic demo dataset and write it to seed/data.json.

The language model (through OpenRouter) invents the text: company names, people, deal titles and
activity notes. Everything numeric (stages, values, dates, owners) is drawn here from a fixed
random seed, and dates are stored as offsets from "today" so the demo never goes stale.

    OPENROUTER_API_KEY=... LLM_MODEL=... python seed/generate.py

The result is committed, so running the product never needs an API key. Everything is fictional.
"""

import json
import os
import random
import re
import urllib.request
from pathlib import Path

OUTPUT = Path(__file__).with_name("data.json")
SEED = 42
MODEL = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")

USERS = [
    {"email": "admin@evolve.test", "name": "Morgan Reyes", "role": "admin"},
    {"email": "priya@evolve.test", "name": "Priya Raman", "role": "user"},
    {"email": "daniel@evolve.test", "name": "Daniel Costa", "role": "user"},
    {"email": "hannah@evolve.test", "name": "Hannah Weiss", "role": "user"},
    {"email": "tomas@evolve.test", "name": "Tomas Lindqvist", "role": "user"},
]

RULES = (
    "Everything must be fictional: no real companies, brands, products or public figures. "
    "Reply with JSON only, no commentary."
)


def ask(prompt: str) -> dict:
    """One chat completion that must return a JSON object."""
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(
            {
                "model": MODEL,
                "seed": SEED,
                "temperature": 0.9,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": RULES},
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "X-Title": "Evolve CRM seed generator",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.load(response)
    usage = body.get("usage", {})
    print(f"  {usage.get('prompt_tokens')} in / {usage.get('completion_tokens')} out tokens")
    content = body["choices"][0]["message"]["content"]
    return json.loads(re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def generate() -> dict:
    rng = random.Random(SEED)

    print("companies")
    companies = ask(
        "Invent 40 small and mid-sized B2B companies that could be customers of a software and "
        "services vendor. Mix industries (logistics, healthcare, retail, manufacturing, finance, "
        "education, energy, hospitality, construction, media) and countries. "
        'Return {"companies": [{"name", "industry", "city", "country"}]}. '
        "Industry is one or two words, title case."
    )["companies"][:40]
    for company in companies:
        company["website"] = f"https://{slug(company['name'])}.example"

    print("contacts")
    names = "\n".join(f"{index}. {c['name']} ({c['country']})" for index, c in enumerate(companies))
    people = ask(
        "For each company below invent 3 to 5 employees a salesperson would talk to, with names "
        "that fit the country, 150 people in total. "
        'Return {"contacts": [{"company": <number>, "first_name", "last_name", "job_title"}]}.\n'
        + names
    )["contacts"]
    contacts = []
    for person in people[:150]:
        if not 0 <= person["company"] < len(companies):
            continue
        domain = slug(companies[person["company"]]["name"])
        contacts.append(
            {
                "company": person["company"],
                "first_name": person["first_name"],
                "last_name": person["last_name"],
                "job_title": person["job_title"],
                "email": f"{slug(person['first_name'])}.{slug(person['last_name'])}@{domain}.example",
                "phone": f"+1 555 01{rng.randrange(100):02d}",
            }
        )

    print("deals")
    titles = ask(
        "Invent 80 sales deal titles for a vendor that sells business software, onboarding, "
        "support plans and consulting. Each is 3 to 6 words, for example 'Warehouse analytics "
        "rollout' or 'Annual support renewal'. Do not include company names. "
        'Return {"titles": [<string>]}.'
    )["titles"][:80]

    print("activities")
    snippets = ask(
        "Write CRM activity entries a salesperson would log, 40 of each type: note, call, "
        "meeting, task. Each has a short subject (3 to 7 words) and a body of one or two "
        "sentences. Keep them generic enough to fit any customer: no names of people or "
        "companies. Tasks are things still to do, such as 'Send revised quote'. "
        'Return {"note": [{"subject", "body"}], "call": [...], "meeting": [...], "task": [...]}.'
    )

    sales = [index for index, user in enumerate(USERS) if user["role"] == "user"]
    by_company: dict[int, list[int]] = {}
    for index, contact in enumerate(contacts):
        by_company.setdefault(contact["company"], []).append(index)

    stages = ["lead"] * 14 + ["qualified"] * 12 + ["proposal"] * 11 + ["negotiation"] * 8
    stages += ["won"] * 25 + ["lost"] * 10
    rng.shuffle(stages)
    deals = []
    for title, stage in zip(titles, stages, strict=False):
        company = rng.choice(list(by_company))
        created = rng.randrange(5, 200)
        closed = stage in ("won", "lost")
        deals.append(
            {
                "title": title,
                "company": company,
                "contact": rng.choice(by_company[company]),
                # Skewed on purpose so "who closed the most" has a clear answer.
                "owner": rng.choices(sales, weights=[4, 3, 2, 2])[0],
                "stage": stage,
                "value": rng.choice([4, 6, 8, 12, 15, 18, 24, 30, 45, 60, 85]) * 1000
                + rng.randrange(10) * 100,
                "created_days_ago": created,
                "closed_days_ago": rng.randrange(0, min(created, 150)) if closed else None,
                "expected_close_in_days": None if closed else rng.randrange(-10, 75),
            }
        )

    activities = []
    for _ in range(400):
        kind = rng.choices(["note", "call", "meeting", "task"], weights=[3, 3, 2, 2])[0]
        text = rng.choice(snippets[kind])
        deal_index = rng.randrange(len(deals))
        deal = deals[deal_index]
        occurred = rng.randrange(0, deal["created_days_ago"] + 1)
        entry = {
            "type": kind,
            "subject": text["subject"],
            "body": text["body"],
            "deal": deal_index if rng.random() < 0.8 else None,
            "contact": deal["contact"],
            "owner": deal["owner"],
            "occurred_days_ago": occurred,
            "due_in_days": None,
            "completed": False,
        }
        if kind == "task":
            entry["due_in_days"] = rng.randrange(-occurred, 15) if occurred else rng.randrange(1, 15)
            # Most past-due tasks were done; a few stay open so the dashboard has something to show.
            entry["completed"] = entry["due_in_days"] < 0 and rng.random() < 0.85
        activities.append(entry)

    return {
        "generated_with": MODEL,
        "seed": SEED,
        "users": USERS,
        "companies": companies,
        "contacts": contacts,
        "deals": deals,
        "activities": activities,
    }


if __name__ == "__main__":
    data = generate()
    OUTPUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print({key: len(value) for key, value in data.items() if isinstance(value, list)})
