"""
Initial content for Gloria Learner Support, transcribed from the WP2
"Proposed website structure" document (D2.1 mapping of the 8 partners).

It is only used to create data.json the first time the app starts (data.json
is gitignored, like every other app's). Every seeded service starts as a
*draft* so each university's content managers can check it and publish it;
the document's "Link" entries had no URLs, so those links start empty.
"""

import datetime
import uuid

SEED_AUTHOR = "seed: Proposed website structure (WP2)"


def _id() -> str:
    return uuid.uuid4().hex[:12]


TYPES = [
    ("academic", "Academic Support",
     "Services directly related to learning processes, study progression and skills development."),
    ("non_academic", "Non-Academic Support",
     "Psychosocial, administrative, financial and well-being services."),
    ("mixed", "Mixed Support",
     "Services that combine both dimensions, such as peer-learning groups, mentoring, career support or mobility guidance."),
]

LEARNER_GROUPS = [
    ("starters", "Starters", "Newly enrolled learners building fundamental study skills.", "#1e88e5"),
    ("pros", "Pros", "Advanced learners balancing studies with work or family, or overcoming specific learning challenges.", "#2e9d5b"),
    ("graduates", "Graduates", "Master's, PhD candidates and alumni working on theses, research and career transitions.", "#e69500"),
]

TARGET_GROUPS = [
    ("international", "International"),
    ("national", "National"),
    ("both", "Both"),
]

ALLIANCE_ROOMS = [
    ("central_support_room", "Central Support Room",
     "A single space providing Alliance-wide guidance on IT infrastructure and digital tools, financial aid and "
     "scholarships, stress management and psychological well-being, knowledge management and digital literacy, and "
     "administrative procedures relevant across all study levels. Specialised support (e.g. Dyslexia, ADHD) is also available."),
    ("language_confidence", "Language Confidence",
     "UNINOVIS Language Confidence addresses the linguistic dimension of learning across the Alliance: academic writing "
     "in English and in the language of your Excellence Hub, workshops, writing groups, individual sessions, and language "
     "cafés & tandem programmes pairing local and international learners."),
    ("starters_room", "Starters Support Room",
     "Level-specific support for newly enrolled learners: orientation resources, study skills, tutoring and well-being "
     "resources — accessible asynchronously and complemented by live sessions at each Excellence Hub."),
    ("pros_room", "Pros Support Room",
     "Level-specific support for advanced learners: study skills, tutoring, career guidance and well-being resources — "
     "accessible asynchronously and complemented by live sessions at each Excellence Hub."),
    ("graduates_room", "Graduates Support Room",
     "Level-specific support for Master's and PhD candidates and alumni: thesis and research support, career guidance and "
     "well-being resources — accessible asynchronously and complemented by live sessions at each Excellence Hub."),
]


def S(type_id, name, description="", target="", languages="", contact_email="", groups=()):
    return {
        "type_id": type_id, "name": name, "description": description, "target_group_id": target,
        "languages": languages, "contact_email": contact_email, "learner_group_ids": list(groups),
    }


A, N, M = "academic", "non_academic", "mixed"

PARTNERS = {
    "THWS": {
        "tagline": "A comprehensive, well-established support landscape combining academic guidance, administrative assistance and well-being services.",
        "intro": "At THWS, learners benefit from central support units offering guidance for international students, mobility "
                 "programmes and general study administration. Academic tutoring, consultations with lecturers, and library "
                 "services support students in their coursework and research. THWS also maintains strong structures for student "
                 "well-being — psychological support, diversity and inclusion services, and advisory units for students with "
                 "disabilities or specific learning needs — complemented by the Fit4Germany project offering career workshops "
                 "and networking with employers.",
        "excellence_hub": "",
        "services": [
            S(A, "Academic advisors for exchange students", "Faculty-based support tailored to different study courses.", "international"),
            S(N, "Psychological Counselling — \"Study healthily\"", "Free confidential counselling in English/German.", languages="English, German"),
            S(N, "Psychological Counselling — Studierendenwerk Würzburg", "External state-run counselling service."),
            S(N, "Scholarship advice & emergency fund", "Via International Office (international) and central services (both).", "both"),
            S(N, "Legal advice", "Help with visa and housing contracts.", "international"),
            S(N, "Disability Support / Accessibility Office", "Coordination of accommodations."),
            S(N, "University sports programme"),
            S(N, "Support for students with children", "Via Studierendenwerk Würzburg."),
            S(M, "Fit4Germany — Career Services", "Subject tutorials + employer networking."),
            S(M, "National career service & job platform"),
            S(M, "International internship programme", "Internship programme for international students.", "international"),
            S(M, "Buddy Programme & Welcome Week", "Cultural integration.", contact_email="welcome@thws.de"),
            S(M, "Language Centre", "German and English courses."),
        ],
    },
    "THUAS": {
        "tagline": "A broad and integrated system spanning academic, personal and administrative domains.",
        "intro": "THUAS offers extensive tutoring and coaching, study-career guidance and a well-developed digital infrastructure — "
                 "including the Brightspace learning platform and Osiris study administration system. Support for students with "
                 "disabilities or specific circumstances is a core component, ensuring inclusive access to learning. Additional "
                 "services include specialised writing coaching (Language Point), diversity and inclusion services, psychological "
                 "support, community networks, legal protection and dedicated support for professional athletes.",
        "excellence_hub": "",
        "services": [
            S(A, "Brightspace learning environment"),
            S(A, "Osiris", "Registration of results & progress."),
            S(A, "Regular study coaching", "Via study programmes."),
            S(A, "Special Educational Needs", "Support for disability or special circumstances."),
            S(A, "THUAS Library", "Physical and online access, study spaces."),
            S(N, "Student counsellor / psychologist services"),
            S(N, "Legal Protection Desk", "Objections, appeals, complaints."),
            S(N, "Diversity & Inclusion Office"),
            S(N, "Financial support for professional athletes"),
            S(N, "Sports & Fitness", "Main campus fitness centre, group classes, Zuiderpark sports halls."),
            S(N, "Support for students with children"),
            S(M, "Language Point — Writing Coaching"),
            S(M, "Community Support Networks", "Social counselling for international students.", "international"),
        ],
    },
    "TAMK": {
        "tagline": "A highly accessible, low-threshold support system integrating academic guidance, wellbeing services and extensive digital tools.",
        "intro": "TAMK's individual counselling is provided by wellbeing advisors, special education teachers and student counsellors, "
                 "complemented by dedicated support for international students. The \"Service Street\" model centralises student "
                 "services, while multiprofessional collaboration ensures a coherent support network. TAMK's \"Parvi\" concept "
                 "promotes student well-being through workshops and peer tutoring, and Moodle serves as the central digital hub for "
                 "course management, communication and assessment. TAMK's guidance culture emphasises early use of AI tools and "
                 "continuous development.",
        "excellence_hub": "",
        "services": [
            S(A, "Study ability counsellors", "Wellbeing services and schools."),
            S(A, "Special needs teachers", "TAMK Schools."),
            S(A, "TAMK counsellors", "Guidance and counselling services."),
            S(N, "Campus chaplains / School pastor", "Psychological support."),
            S(N, "KELA", "National financial support for students.", "national"),
            S(N, "TAMK Foundation", "Institutional financial support."),
            S(N, "Security services", "Legal/safety advice."),
            S(N, "SportUni", "Sports and exercise programme."),
            S(N, "TAMK Parvi & partners' wellbeing services"),
            S(N, "Support for students with children", "Via study ability counsellors."),
            S(M, "TAMK Career Services"),
            S(M, "TAMKO Student Union", "Cultural support, CLINT club international."),
            S(M, "Social counselling for international students", target="international"),
            S(M, "Mobility Services", "International Office + TAMKO for exchange and international tutoring.", "international"),
            S(M, "Language & Communications Team", "Language courses across the curriculum."),
        ],
    },
    "USPN": {
        "tagline": "A comprehensive offering of academic and non-academic support tailored to diverse student needs.",
        "intro": "USPN provides tutoring, writing support, library services and guidance on study skills and research activities. "
                 "Student services and international offices offer targeted administrative assistance and academic orientation. "
                 "International students benefit from structured mobility support, and USPN places strong emphasis on student "
                 "well-being and inclusion through psychological counselling, disability support, financial aid and accommodation "
                 "assistance. Digital platforms ensure efficient and consistent access to information throughout the student journey.",
        "coordinator": "To be appointed",
        "excellence_hub": "Paris (Villetaneuse)",
        "services": [
            S(A, "University Libraries", "Three campus libraries with extended hours."),
            S(A, "Student tutoring", "First-year peer tutoring, faculty-based.", groups=["starters"]),
            S(N, "Health Service", "Nursing, prevention, screenings, dietary consultations, first aid training."),
            S(N, "Support Service for Students with Disabilities"),
            S(N, "Cultural Department", "Live shows, workshops, free theatre and cinema tickets."),
            S(N, "Sports Department", "c. 40 activities across campuses."),
            S(N, "Student Associations", "32 associations, incl. 4 for international integration."),
            S(N, "Scholarship Department", "Via CROUS."),
            S(N, "Student Housing", "CROUS and USPN reserved places."),
            S(N, "FSDIE Fund", "Financial support for student-led projects."),
            S(N, "Monitoring of Eiffel scholarship recipients", target="international"),
            S(M, "Welcome Desk", "Reception centre for international students.", "international"),
            S(M, "Welcome & Integration Week", "Semester start integration by International Relations."),
            S(M, "Language Support", "Courses in 8+ languages, CEFRL, certifications (TOEFL, TOEIC, CLES, DELF)."),
            S(M, "French as a Foreign Language (FLE)", "Intensive courses + \"Passerelle\" certificate for students in exile."),
            S(M, "Tandem Programme", "Pairing students with different mother tongues."),
            S(M, "Career Guidance & Integration Service"),
            S(M, "Career Observatory — Galileo Institute", "5-year alumni follow-up.", groups=["graduates"]),
            S(M, "Student Entrepreneurship Support", "Incubator, Student Entrepreneur Diploma."),
        ],
    },
    "UMA": {
        "tagline": "An extensive support ecosystem combining academic, financial, administrative and well-being services.",
        "intro": "UMA offers scholarship programmes, financial aid and targeted support for doctoral candidates. International "
                 "mobility is facilitated by the International Hub, providing guidance on exchanges, internships abroad and buddy "
                 "pairing. Digital learning support is available through UMA's virtual learning platforms and micro-credential "
                 "offerings. Non-academic support includes social assistance, accommodation services (including intergenerational "
                 "housing) and resources for student well-being.",
        "excellence_hub": "",
        "services": [
            S(N, "Collaborating Student Grant for special needs", "€150/month funding a peer helper."),
            S(N, "Social Cohesion Grants", "Tuition, residence, dining hall costs."),
            S(N, "Official Master's Grant", groups=["graduates"]),
            S(N, "Cultural & educational promotion grants", "For extracurricular activities."),
            S(N, "Housing — \"Living with older people\"", "Intergenerational accommodation."),
            S(N, "Housing — \"Alberto Jiménez Fraud\" residence", "Affordable places via Junta de Andalucía."),
            S(N, "Housing — subsidised university accommodation", "Undergraduate, master's, PhD."),
            S(N, "Housing — International Hub platform", target="international"),
            S(M, "Buddy Programme", "I-Buddy + e-Buddy for international integration (up to 4 credits).", "international"),
            S(M, "Doctoral Mentoring Programme", "Alumni and senior PhD candidates mentor new doctoral students.", groups=["graduates"]),
            S(M, "Micro-credentials & short courses", "Up-to-date skills and specialisation."),
        ],
    },
    "UDCLV": {
        "tagline": "A comprehensive set of services supporting learners academically, socially and administratively.",
        "intro": "Core areas include inclusion and disability services (CID Centre), language support (Rosetta Stone, Italian courses "
                 "via the Italian Academy of Salerno), academic tutoring, psychological counselling, and extensive digital learning "
                 "infrastructure through the university's e-learning system. Students benefit from library resources, structured "
                 "study plans and study-abroad opportunities, while additional services such as JOB365 and Office 365 support "
                 "academic progression and employability. UDCLV also offers financial aid schemes, subsidies and a university "
                 "day-care centre for learners with family responsibilities.",
        "excellence_hub": "",
        "services": [
            S(A, "MathWorks / MATLAB / Simulink & Wolfram Mathematica", "Free academic licences."),
            S(A, "University E-Learning System"),
            S(A, "University Libraries"),
            S(A, "Online Study Plans"),
            S(N, "CID — Centre for Inclusion of Students with Disabilities & SLD", "Peer tutoring, guidance."),
            S(N, "SAPS — Student Psychological Support Service", "Italian & English clinical consultations.", languages="Italian, English"),
            S(N, "Study grants & subsidies"),
            S(N, "University Day-Care Centre", "Via \"Il Monello\" cooperative."),
            S(N, "CUS Caserta — University Sports Centre"),
            S(N, "ADISUR Campania — Right to University Education"),
            S(N, "Caserta Residential Centre — National School of Administration"),
            S(N, "University Insurance coverage"),
            S(M, "Language Support — Rosetta Stone + free Italian courses", "Rosetta Stone (25 languages) + free Italian courses for foreign students and Erasmus incoming."),
            S(M, "Erasmus+ Study Abroad"),
            S(M, "JOB365 — Career orientation & placement", "For undergrads, graduates, PhDs."),
            S(M, "Buddy Project — International Welcome Desk & outgoing support", "60 part-time Buddy contracts.", "international"),
            S(M, "Office 365 ProPlus", "Up to 5 devices per student."),
            S(M, "V:erysoon — student transport platform", "Car sharing + shuttle."),
            S(M, "Press review service"),
        ],
    },
    "KK": {
        "tagline": "A comprehensive system of academic and non-academic support spanning the entire student lifecycle.",
        "intro": "Academic support at KK includes structured onboarding for first-year students, ongoing consultations with lecturers, "
                 "group tutors, internship supervisors and thesis advisors, as well as a well-resourced Library and Scientific "
                 "Communication Centre. International students receive targeted administrative, academic and social assistance "
                 "through the International Relations Unit and student mentors. Non-academic support covers financial aid schemes, "
                 "accommodation, leisure and sports, and psychological counselling. Support for students with disabilities or "
                 "specific learning needs combines infrastructure adaptation, specialised equipment, individual study plans and "
                 "tailored learning arrangements.",
        "excellence_hub": "",
        "services": [
            S(A, "First-year integration & admission consultations", "Memorandum, introductory meetings.", groups=["starters"]),
            S(A, "Academic advising", "Lecturers, group tutors, internship supervisors, thesis advisors, international coordinators, Head of Studies."),
            S(A, "Library & Scientific Communication Centre", "Remote training and consultations."),
            S(N, "State Studies Foundation", "Loans, study & social scholarships."),
            S(N, "KK Scholarships", "Incentive, one-off, Nominal Director's Scholarship."),
            S(N, "Support for students with disabilities / learning difficulties", "Individual consultations, Individual Study Plan, free class attendance, special equipment."),
            S(N, "Accommodation coordination"),
            S(N, "Wellness & Sports Centre", "Events, workouts, leisure activities."),
            S(N, "Psychological Counselling", "Free, confidential counselling.", languages="Lithuanian, English"),
            S(N, "Advertising & Media Centre", "Publishing advice."),
            S(M, "Career Services", "Individual consultations, entrepreneurship guidance, Career Days."),
            S(M, "Assistance for international students", "ISIC, bank account, health, Survival Guide, student mentors.", "international"),
            S(M, "Language Centre", "Optional language courses, OLS Test, Lithuanian language courses."),
        ],
    },
    "UT": {
        "tagline": "A broad framework of student support services addressing academic, administrative and personal needs.",
        "intro": "Services at UT are accessible to national and international students, offered by units across the institution. Core "
                 "services include academic guidance, access to central study information, and assistance with navigating "
                 "university procedures. Students can rely on institutional support structures to address individual queries, "
                 "receive orientation and obtain help related to their studies. Beyond academic support, UT offers resources aimed "
                 "at promoting students' well-being and integration into university life.",
        "excellence_hub": "",
        "services": [
            S(A, "General academic information", "International Relations Office, fields of study and courses."),
            S(A, "Academic Vice-Deans for exchange students", "Faculty-based.", "international"),
            S(N, "Psychologist's office", "Faculty-based consultations for students and staff."),
            S(N, "Government scholarship", "For students in financial difficulty.", "national"),
            S(N, "University Sports Centre", "Sport activities (centralised)."),
            S(M, "Career office", "Labour market information, labour fair.", "national"),
            S(M, "Foreign Language Centre / Faculty of Foreign Languages", "Paid language courses."),
            S(M, "Intensive Albanian Language courses", "Department of Linguistics.", "international"),
        ],
    },
}


def build_seed_data() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    stamp = {"updated_at": now, "updated_by": SEED_AUTHOR}

    services = []
    for code, partner in PARTNERS.items():
        for order, s in enumerate(partner["services"]):
            services.append({
                "id": _id(), "scope": code, "room_id": "", "order": order,
                "link": "", "contact_name": "", "contact_phone": "",
                "access": "own", "status": "draft",
                **s, **stamp,
            })

    return {
        "types": [{"id": i, "name": n, "description": d, "order": k} for k, (i, n, d) in enumerate(TYPES)],
        "learner_groups": [
            {"id": i, "name": n, "description": d, "color": c, "order": k}
            for k, (i, n, d, c) in enumerate(LEARNER_GROUPS)
        ],
        "target_groups": [{"id": i, "name": n, "description": "", "order": k} for k, (i, n) in enumerate(TARGET_GROUPS)],
        "rooms": [{"id": i, "name": n, "intro": d, "order": k, **stamp} for k, (i, n, d) in enumerate(ALLIANCE_ROOMS)],
        "partners": {
            code: {
                "tagline": p["tagline"], "intro": p["intro"],
                "coordinator": p.get("coordinator", ""), "coordinator_email": "",
                "excellence_hub": p.get("excellence_hub", ""), "excellence_hub_email": "",
                **stamp,
            }
            for code, p in PARTNERS.items()
        },
        "services": services,
    }
