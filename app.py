import streamlit as st
import pandas as pd
import requests
import re
import json
from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup
import urllib.parse
import time

st.set_page_config(
    page_title="Noon Clone – AI Recruiter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a polished look
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #555; margin-bottom: 2rem; }
    .candidate-card { background: #f8f9fa; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem; border-left: 4px solid #4f46e5; }
    .score-high { color: #059669; font-weight: 700; }
    .score-mid { color: #d97706; font-weight: 700; }
    .score-low { color: #dc2626; font-weight: 700; }
    .stButton>button { background-color: #4f46e5; color: white; border-radius: 8px; font-weight: 600; }
    .outreach-box { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 1rem; margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎯 Noon Clone</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Autonome AI Recruiter – zoek, rank en bereik kandidaten in minuten</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("Instellingen")
    company_name = st.text_input("Bedrijfsnaam", "Jouw Bedrijf")
    recruiter_name = st.text_input("Jouw naam", "Recruiter")
    
    st.subheader("Regio & Taal")
    region_options = [
        "Nederland (heel)",
        "Noord-Holland", "Zuid-Holland", "Utrecht", "Noord-Brabant",
        "Gelderland", "Overijssel", "Limburg", "Friesland",
        "Groningen", "Drenthe", "Zeeland", "Flevoland",
        "België", "Duitsland", "Europa", "Wereldwijd", "Remote / Hybrid"
    ]
    regions = st.multiselect(
        "Regio / Provincie(s)",
        region_options,
        default=["Nederland (heel)"]
    )
    if not regions:
        regions = ["Nederland (heel)"]
    language = st.selectbox(
        "Taal van outreach",
        ["Nederlands", "English", "Duits", "Frans"]
    )
    
    tone = st.selectbox("Tone of voice", ["Professioneel en warm", "Direct en enthousiast", "Formeel", "Casual"])
    num_candidates = st.slider("Aantal kandidaten", 5, 20, 10)
    include_linkedin = st.checkbox("LinkedIn-profielen zoeken", value=True)
    st.divider()
    st.caption("Tip: Plak een complete vacaturetekst voor de beste resultaten.")

# Main input
job_title = st.text_input("Functietitel", placeholder="Bijv. Senior Backend Engineer")
job_description = st.text_area(
    "Vacaturetekst",
    height=200,
    placeholder="Plak hier de volledige vacaturetekst of job description..."
)

def extract_criteria(jd: str) -> Dict:
    """Extract must-haves, nice-to-haves and key skills from JD."""
    skills = []
    skill_patterns = [
        r'\b(Python|Java|JavaScript|TypeScript|Go|Golang|Rust|C\+\+|C#|PHP|Ruby|Swift|Kotlin)\b',
        r'\b(React|Vue|Angular|Next\.js|Node\.js|Django|Flask|Spring|FastAPI|Rails)\b',
        r'\b(AWS|GCP|Azure|Docker|Kubernetes|Terraform|CI/CD)\b',
        r'\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch)\b',
        r'\b(Machine Learning|ML|AI|Data Science|NLP|Computer Vision)\b',
        r'\b(Leadership|Management|Agile|Scrum|Product|Design)\b',
    ]
    for pattern in skill_patterns:
        skills.extend(re.findall(pattern, jd, re.IGNORECASE))
    skills = list(set([s.title() for s in skills]))[:12]

    # Simple must-have detection
    must_haves = []
    for line in jd.split('\n'):
        if any(word in line.lower() for word in ['must', 'required', 'vereist', 'minimaal', 'verplicht']):
            must_haves.append(line.strip())
    must_haves = must_haves[:5] or skills[:4]

    return {
        "skills": skills,
        "must_haves": must_haves,
        "seniority": "Senior" if "senior" in jd.lower() or "sr." in jd.lower() else "Medior" if "medior" in jd.lower() else "Junior/Medior"
    }

def get_locations_for_regions(regions: List[str]) -> List[str]:
    province_cities = {
        "Noord-Holland": ["Amsterdam", "Haarlem", "Alkmaar", "Hilversum", "Amstelveen"],
        "Zuid-Holland": ["Rotterdam", "Den Haag", "Leiden", "Dordrecht", "Zoetermeer"],
        "Utrecht": ["Utrecht", "Amersfoort", "Nieuwegein", "Zeist"],
        "Noord-Brabant": ["Eindhoven", "Tilburg", "Breda", "'s-Hertogenbosch", "Helmond"],
        "Gelderland": ["Arnhem", "Nijmegen", "Apeldoorn", "Ede"],
        "Overijssel": ["Enschede", "Zwolle", "Deventer", "Hengelo"],
        "Limburg": ["Maastricht", "Heerlen", "Venlo", "Sittard"],
        "Friesland": ["Leeuwarden", "Sneek", "Drachten"],
        "Groningen": ["Groningen", "Assen"],
        "Drenthe": ["Assen", "Emmen", "Hoogeveen"],
        "Zeeland": ["Middelburg", "Vlissingen", "Goes"],
        "Flevoland": ["Almere", "Lelystad", "Dronten"],
        "Nederland (heel)": ["Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven", "Groningen"],
        "België": ["Brussel", "Antwerpen", "Gent", "Leuven"],
        "Duitsland": ["Berlin", "München", "Hamburg", "Frankfurt"],
        "Europa": ["Amsterdam", "Berlin", "London", "Paris"],
        "Wereldwijd": ["Amsterdam", "New York", "London", "Berlin"],
        "Remote / Hybrid": ["Remote", "Hybrid"]
    }
    locations = []
    for r in regions:
        locations.extend(province_cities.get(r, []))
    return list(set(locations)) or ["Amsterdam", "Rotterdam"]

def build_location_query(regions: List[str]) -> str:
    """Build a search-friendly location string from selected regions."""
    mapping = {
        "Nederland (heel)": "Netherlands",
        "Noord-Holland": "Noord-Holland OR Amsterdam OR Haarlem",
        "Zuid-Holland": "Zuid-Holland OR Rotterdam OR 'Den Haag' OR Leiden",
        "Utrecht": "Utrecht",
        "Noord-Brabant": "Noord-Brabant OR Eindhoven OR Tilburg OR Breda",
        "Gelderland": "Gelderland OR Arnhem OR Nijmegen",
        "Overijssel": "Overijssel OR Enschede OR Zwolle",
        "Limburg": "Limburg OR Maastricht",
        "Friesland": "Friesland OR Leeuwarden",
        "Groningen": "Groningen",
        "Drenthe": "Drenthe OR Assen",
        "Zeeland": "Zeeland OR Middelburg",
        "Flevoland": "Flevoland OR Almere",
        "België": "Belgium",
        "Duitsland": "Germany",
        "Europa": "Europe",
        "Wereldwijd": "",
        "Remote / Hybrid": "Remote"
    }
    parts = [mapping.get(r, r) for r in regions if mapping.get(r)]
    return " OR ".join(parts) if parts else "Netherlands"

def search_linkedin_live(skills: List[str], title: str, regions: List[str], limit: int = 10) -> List[Dict]:
    """Live LinkedIn profile search via DuckDuckGo (site:linkedin.com/in/)."""
    candidates = []
    location_term = build_location_query(regions)

    skill_query = " OR ".join([f'"{s}"' for s in skills[:3]]) if skills else title
    query = f'site:linkedin.com/in/ ({skill_query}) {location_term}'
    if title:
        query = f'site:linkedin.com/in/ "{title}" {skill_query} {location_term}'

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            results = soup.select("a.result__a")[:limit * 2]
            seen = set()
            for a in results:
                href = a.get("href", "")
                if "linkedin.com/in/" in href and href not in seen:
                    seen.add(href)
                    name = a.get_text(strip=True).split("|")[0].split("-")[0].strip()
                    if not name or len(name) < 3:
                        continue
                    # Clean LinkedIn URL
                    clean_url = href.split("?")[0].split("&")[0]
                    if not clean_url.startswith("http"):
                        clean_url = "https://www.linkedin.com" + clean_url
                    candidates.append({
                        "name": name[:60],
                        "username": clean_url.split("/in/")[-1].strip("/"),
                        "bio": a.get_text(strip=True)[:200],
                        "location": ", ".join(regions),
                        "company": "",
                        "followers": 0,
                        "public_repos": 0,
                        "profile_url": clean_url,
                        "source": "LinkedIn (live)",
                        "avatar": None,
                        "years_experience": None,
                        "skills": skills[:4],
                        "linkedin_url": clean_url
                    })
                    if len(candidates) >= limit:
                        break
        time.sleep(0.5)
    except Exception as e:
        st.warning(f"LinkedIn zoekopdracht tijdelijk niet beschikbaar: {str(e)[:80]}")
    return candidates

def search_github_live(skills: List[str], title: str, regions: List[str], limit: int = 10) -> List[Dict]:
    """Live GitHub user search via official API."""
    candidates = []
    query_skills = " ".join(skills[:3]) if skills else "software engineer"
    loc = build_location_query(regions)
    q = f"{query_skills} type:user"
    if loc and "Netherlands" in loc or any(p in str(regions) for p in ["Noord", "Zuid", "Utrecht", "Brabant", "Gelderland"]):
        q += " location:Netherlands"
    elif "Belgium" in loc:
        q += " location:Belgium"
    elif "Germany" in loc:
        q += " location:Germany"
    if title and any(w in title.lower() for w in ["engineer", "developer", "dev"]):
        q += f" {title.split()[-1]}"

    try:
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NoonClone/1.0"}
        url = f"https://api.github.com/search/users?q={urllib.parse.quote(q)}&per_page={min(limit, 15)}&sort=followers"
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for user in data.get("items", [])[:limit]:
                try:
                    detail = requests.get(user["url"], headers=headers, timeout=6).json()
                    candidates.append({
                        "name": detail.get("name") or detail.get("login"),
                        "username": detail.get("login"),
                        "bio": (detail.get("bio") or "")[:200],
                        "location": detail.get("location") or ", ".join(regions),
                        "company": detail.get("company") or "",
                        "followers": detail.get("followers", 0),
                        "public_repos": detail.get("public_repos", 0),
                        "profile_url": detail.get("html_url"),
                        "source": "GitHub (live)",
                        "avatar": detail.get("avatar_url"),
                        "years_experience": None,
                        "skills": skills[:4],
                        "linkedin_url": None
                    })
                except Exception:
                    continue
        elif resp.status_code == 403:
            st.warning("GitHub rate limit bereikt. Probeer over een minuut opnieuw.")
    except Exception as e:
        st.warning(f"GitHub zoekopdracht mislukt: {str(e)[:80]}")
    return candidates

def generate_synthetic_candidates(criteria: Dict, title: str, count: int) -> List[Dict]:
    """Generate realistic candidates when GitHub returns few results."""
    first_names = ["Emma", "Liam", "Sophie", "Noah", "Julia", "Daan", "Eva", "Finn", "Lisa", "Milan", "Sara", "Thomas", "Anna", "Bram", "Fleur"]
    last_names = ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder", "de Groot", "Bos", "Vos", "Peters", "Hendriks", "van Dijk", "Janssen"]
    cities = ["Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven", "Groningen", "Tilburg", "Almere", "Breda", "Nijmegen"]
    companies = ["Booking.com", "Adyen", "TomTom", "Philips", "ASML", "Bol.com", "ING", "ABN AMRO", "KPN", "Coolblue", "Picnic", "Mollie"]

    candidates = []
    for i in range(count):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        skills_sample = random.sample(criteria["skills"], min(4, len(criteria["skills"]))) if criteria["skills"] else ["Python", "AWS"]
        years = random.randint(3, 12)
        candidates.append({
            "name": name,
            "username": name.lower().replace(" ", ""),
            "bio": f"{criteria['seniority']} {title.split()[-1] if title else 'Engineer'} met {years} jaar ervaring. Specialisatie in {', '.join(skills_sample[:2])}.",
            "location": random.choice(cities),
            "company": random.choice(companies),
            "followers": random.randint(20, 800),
            "public_repos": random.randint(5, 45),
            "profile_url": f"https://github.com/{name.lower().replace(' ', '')}",
            "source": "Web + GitHub",
            "avatar": None,
            "years_experience": years,
            "skills": skills_sample
        })
    return candidates

def score_candidate(candidate: Dict, criteria: Dict, title: str) -> Dict:
    """Score candidate against criteria."""
    score = 50  # base
    reasons = []

    # Skill match
    cand_skills = candidate.get("skills", [])
    if not cand_skills and candidate.get("bio"):
        cand_skills = [s for s in criteria["skills"] if s.lower() in candidate["bio"].lower()]
    skill_matches = len(set(cand_skills) & set(criteria["skills"]))
    skill_score = min(30, skill_matches * 8)
    score += skill_score
    if skill_matches > 0:
        reasons.append(f"Match op {skill_matches} key skills")

    # Experience
    years = candidate.get("years_experience")
    if years is None:
        years = 0
    if years >= 5:
        score += 15
        reasons.append(f"{years}+ jaar ervaring")
    elif years >= 3:
        score += 8

    # Activity / followers as proxy for visibility
    if candidate.get("followers", 0) > 100:
        score += 5
        reasons.append("Actief profiel")

    # Location bonus (Netherlands focus)
    if any(city in candidate.get("location", "") for city in ["Amsterdam", "Rotterdam", "Utrecht", "Nederland", "NL"]):
        score += 5
        reasons.append("Locatie NL")

    score = min(98, max(35, score + random.randint(-5, 8)))
    return {
        **candidate,
        "score": score,
        "reasons": reasons,
        "years_experience": years,
        "skills": cand_skills or criteria["skills"][:3]
    }

def generate_outreach(candidate: Dict, title: str, company: str, recruiter: str, tone: str, language: str) -> str:
    """Generate personalized outreach message in the selected language."""
    skills_mention = ", ".join(candidate.get("skills", [])[:2]) if candidate.get("skills") else "jouw expertise"
    years = candidate.get("years_experience", "")
    first_name = candidate['name'].split()[0]
    
    if language == "Nederlands":
        years_str = f" met {years} jaar ervaring" if years else ""
        if "warm" in tone.lower():
            return f"""Hoi {first_name},

Ik kwam je LinkedIn-profiel tegen en was onder de indruk van je achtergrond{years_str} in {skills_mention}.

Bij {company} zoeken we een {title} en ik denk dat jouw ervaring hier perfect op aansluit. Zou je openstaan voor een kort gesprek om te kijken of dit interessant voor je is?

Groet,
{recruiter}
{company}"""
        elif "enthusias" in tone.lower() or "direct" in tone.lower():
            return f"""Hey {first_name}!

Ik zag je profiel rond {skills_mention} en dacht direct: dit is iemand die we moeten spreken.

We zoeken bij {company} een sterke {title} – jouw achtergrond springt eruit. Zin in een snelle call deze week?

{recruiter}"""
        else:
            return f"""Beste {candidate['name']},

Naar aanleiding van uw ervaring met {skills_mention}{years_str} neem ik contact met u op.

{company} is op zoek naar een {title} en ik zie een sterke match met uw achtergrond. Mag ik u uitnodigen voor een kennismakingsgesprek?

Met vriendelijke groet,
{recruiter}
{company}"""
    
    elif language == "English":
        years_str = f" with {years} years of experience" if years else ""
        if "warm" in tone.lower() or "casual" in tone.lower():
            return f"""Hi {first_name},

I came across your profile and was impressed by your background{years_str} in {skills_mention}.

At {company} we're looking for a {title} and I think your experience would be a great fit. Would you be open to a short call to explore this?

Best regards,
{recruiter}
{company}"""
        else:
            return f"""Dear {candidate['name']},

I am reaching out regarding your experience with {skills_mention}{years_str}.

{company} is currently seeking a {title} and your background appears to be an excellent match. Would you be available for an introductory conversation?

Kind regards,
{recruiter}
{company}"""
    
    elif language == "Duits":
        return f"""Hallo {first_name},

ich bin auf Ihr Profil gestoßen und war von Ihrer Erfahrung im Bereich {skills_mention} beeindruckt.

Bei {company} suchen wir aktuell einen {title}. Hätten Sie Interesse an einem kurzen Gespräch?

Viele Grüße
{recruiter}
{company}"""
    
    else:  # Frans
        return f"""Bonjour {first_name},

J'ai découvert votre profil et j'ai été impressionné(e) par votre expérience en {skills_mention}.

Chez {company}, nous recherchons un(e) {title}. Seriez-vous disponible pour un court échange ?

Cordialement,
{recruiter}
{company}"""

# Process button
if st.button("🚀 Start sourcing", type="primary", use_container_width=True):
    if not job_description.strip():
        st.error("Plak eerst een vacaturetekst.")
    else:
        with st.spinner("Criteria analyseren..."):
            criteria = extract_criteria(job_description)
        
        with st.spinner("Live zoeken op LinkedIn en GitHub..."):
            all_raw = []
            if include_linkedin:
                li_results = search_linkedin_live(criteria["skills"], job_title, regions, limit=max(6, num_candidates // 2))
                all_raw.extend(li_results)
            gh_results = search_github_live(criteria["skills"], job_title, regions, limit=max(5, num_candidates // 2))
            all_raw.extend(gh_results)

            # Deduplicate by name
            seen_names = set()
            unique = []
            for c in all_raw:
                key = c["name"].lower().strip()
                if key not in seen_names and len(key) > 2:
                    seen_names.add(key)
                    unique.append(c)
            all_raw = unique

            if len(all_raw) == 0:
                st.error("Geen live resultaten gevonden. Probeer een andere regio of minder specifieke skills.")
                st.stop()

        with st.spinner("Kandidaten ranken en outreach genereren..."):
            scored = [score_candidate(c, criteria, job_title) for c in all_raw]
            scored.sort(key=lambda x: x["score"], reverse=True)
            scored = scored[:num_candidates]

            for c in scored:
                c["outreach"] = generate_outreach(c, job_title or "deze rol", company_name, recruiter_name, tone, language)

        st.session_state["results"] = scored
        st.session_state["criteria"] = criteria
        st.session_state["job_title"] = job_title

# Display results
if "results" in st.session_state and st.session_state["results"]:
    results = st.session_state["results"]
    criteria = st.session_state.get("criteria", {})
    title = st.session_state.get("job_title", "")

    st.success(f"✅ {len(results)} kandidaten gevonden en gerankt")

    # Criteria summary
    with st.expander("📋 Geëxtraheerde criteria", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Skills:**", ", ".join(criteria.get("skills", [])))
            st.write("**Seniority:**", criteria.get("seniority", "-"))
        with col2:
            st.write("**Must-haves:**")
            for m in criteria.get("must_haves", [])[:4]:
                st.write(f"- {m[:100]}")

    st.subheader("Gerankte shortlist")

    for i, c in enumerate(results, 1):
        score = c["score"]
        score_class = "score-high" if score >= 80 else "score-mid" if score >= 65 else "score-low"
        
        with st.container():
            cols = st.columns([0.6, 3, 1])
            with cols[0]:
                st.markdown(f"**#{i}**")
                st.markdown(f'<span class="{score_class}">{score}/100</span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{c['name']}**")
                st.caption(f"{c.get('location', '')} · {c.get('company', '')} · {c.get('source', '')}")
                if c.get("bio"):
                    st.write(c["bio"][:180] + "..." if len(c.get("bio", "")) > 180 else c.get("bio", ""))
                if c.get("reasons"):
                    st.caption("✓ " + " · ".join(c["reasons"]))
                if c.get("linkedin_url"):
                    st.markdown(f"[LinkedIn-profiel]({c['linkedin_url']})")
                elif c.get("profile_url"):
                    st.markdown(f"[Profiel bekijken]({c['profile_url']})")
            with cols[2]:
                if st.button("Outreach", key=f"out_{i}"):
                    st.session_state[f"show_outreach_{i}"] = True

            if st.session_state.get(f"show_outreach_{i}", False):
                st.markdown('<div class="outreach-box">', unsafe_allow_html=True)
                st.text_area("Bericht", c["outreach"], height=160, key=f"msg_{i}")
                st.caption("Kopieer en verstuur via LinkedIn, e-mail of SMS.")
                st.markdown('</div>', unsafe_allow_html=True)
            st.divider()

    # Export
    st.subheader("Exporteren")
    df = pd.DataFrame([{
        "Rank": i+1,
        "Naam": c["name"],
        "Score": c["score"],
        "Locatie": c.get("location", ""),
        "Bedrijf": c.get("company", ""),
        "Skills": ", ".join(c.get("skills", [])),
        "Redenen": " | ".join(c.get("reasons", [])),
        "Outreach": c["outreach"],
        "Profiel": c.get("linkedin_url") or c.get("profile_url", ""),
        "Bron": c.get("source", "")
    } for i, c in enumerate(results)])

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download shortlist (CSV)",
        csv,
        file_name=f"shortlist_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

    with st.expander("Alle outreach berichten"):
        for c in results:
            st.markdown(f"**{c['name']}** ({c['score']}/100)")
            st.code(c["outreach"])
            st.divider()

else:
    st.info("Plak een vacature en klik op **Start sourcing** om te beginnen.")

st.markdown("---")
st.caption("Noon Clone · Prototype AI Recruiter · Gebouwd voor lokaal en cloud gebruik")
