import re as _re

countries = [
    "japan",
    "india",
    "uae",
    "uk",
    "usa",
    "us",
    "united arab emirates",
    "united kingdom",
    "united states",
    "china",
    "canada",
    "germany",
    "france",
    "australia",
    "singapore",
    "spain",
    "italy",
    "brazil",
    "mexico",
]
content_lower = "my name is alextest15501. i want to buy a sony playstation"

matched = []
for c in countries:
    if _re.search(r"\b" + _re.escape(c) + r"\b", content_lower):
        matched.append(c)

print("Matched countries:", matched)
