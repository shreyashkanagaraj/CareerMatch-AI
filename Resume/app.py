import os
import re
import io
import time
import base64

import streamlit as st

from pdfminer.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

st.set_page_config(page_title="Student Internship Readiness Dashboard", layout="wide", page_icon="🎓")

# ---------------- TOP BANNER ----------------
st.markdown(
    """
    <style>
        .main-title-box {
            text-align:center;
            margin-top:8px;
            margin-bottom:18px;
        }
        .main-title {
            display:inline-block;
            background:linear-gradient(135deg,#000000,#1f2937);
            padding:10px 38px;
            border-radius:8px;
            box-shadow:0px 5px 18px rgba(0,0,0,0.25);
        }
        .main-title span {
            font-size:62px;
            font-weight:500;
            color:#FFFAFA;
            letter-spacing:7px;
            font-family:Orbitron, sans-serif;
        }
        .hero-card {
            background:linear-gradient(135deg,#eef6ff,#ffffff);
            border:1px solid #dbeafe;
            padding:24px;
            border-radius:18px;
            margin-bottom:24px;
            box-shadow:0px 4px 20px rgba(15,23,42,0.08);
        }
        .hero-card h2 {
            color:#0f172a;
            margin-bottom:8px;
        }
        .hero-card p {
            color:#334155;
            font-size:17px;
        }
        .section-card {
            padding:18px;
            border-radius:14px;
            background:#ffffff;
            border:1px solid #e5e7eb;
            box-shadow:0px 3px 12px rgba(0,0,0,0.04);
        }
    </style>
    <div class="main-title-box">
        <div class="main-title"><span>RESUME</span></div>
    </div>
    <div class="hero-card">
        <h2>🎓 Student Internship Readiness Dashboard</h2>
        <p>Upload your resume, add internship/company requirements, and get a clear skill-match score, missing-skill roadmap, and learning resources.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- PDF HELPERS ----------------
def pdf_reader(file_path):
    try:
        resource_manager = PDFResourceManager()
        fake_file_handle = io.StringIO()
        converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
        page_interpreter = PDFPageInterpreter(resource_manager, converter)

        with open(file_path, "rb") as fh:
            for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                page_interpreter.process_page(page)

        text = fake_file_handle.getvalue()
        converter.close()
        fake_file_handle.close()
        return text
    except Exception as e:
        st.error(f"Resume PDF reading failed: {e}")
        return ""


def count_pdf_pages(file_path):
    try:
        with open(file_path, "rb") as fh:
            return sum(1 for _ in PDFPage.get_pages(fh, caching=True, check_extractable=True))
    except Exception:
        return 0


def show_pdf_small(file_path):
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"PDF preview could not be shown: {e}")

# ---------------- EXTRACTORS ----------------
def extract_email(text):
    match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text or "")
    return match.group(0) if match else "Not found"


def extract_mobile(text):
    patterns = [r"(?:\+91[\-\s]?)?[6-9]\d{9}", r"(?:\+\d{1,3}[\-\s]?)?\d{10,12}"]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(0)
    return "Not found"


def extract_name(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    ignore_words = ["resume", "curriculum", "vitae", "email", "phone", "mobile", "contact", "github", "linkedin"]
    for line in lines[:10]:
        clean = re.sub(r"[^A-Za-z\s.]", "", line).strip()
        words = clean.split()
        if 2 <= len(words) <= 4 and not any(w.lower() in ignore_words for w in words):
            return clean
    return "Not found"


def skill_bank():
    return [
        "python", "java", "c", "c++", "html", "css", "javascript", "typescript", "react", "node js",
        "django", "flask", "fastapi", "streamlit", "sql", "mysql", "mongodb", "postgresql",
        "machine learning", "deep learning", "tensorflow", "keras", "pytorch", "scikit-learn",
        "pandas", "numpy", "data science", "data analysis", "power bi", "tableau", "excel",
        "android", "flutter", "kotlin", "swift", "ios", "ui", "ux", "figma", "adobe xd",
        "photoshop", "git", "github", "linux", "aws", "azure", "docker", "rest api", "api",
        "firebase", "opencv", "nlp", "natural language processing", "statistics", "matplotlib",
        "plotly", "beautifulsoup", "selenium", "bootstrap", "tailwind", "communication",
        "problem solving", "teamwork", "leadership", "analytics", "data visualization"
    ]


def extract_skills(text):
    text_lower = (text or "").lower()
    found = []
    for skill in skill_bank():
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill.title())
    return sorted(set(found))


def parse_resume(file_path):
    text = pdf_reader(file_path)
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "mobile_number": extract_mobile(text),
        "skills": extract_skills(text),
        "no_of_pages": count_pdf_pages(file_path),
        "text": text,
    }

# ---------------- INTERNSHIP TEXT ----------------
def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def scrape_website_light(url):
    # Safe lightweight scraper. If it fails, app continues.
    if requests is None or BeautifulSoup is None:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=4)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        return clean_text(soup.get_text(" "))[:6000]
    except Exception:
        return ""


def extract_text_from_uploaded_pdf(uploaded_pdf):
    if uploaded_pdf is None:
        return ""
    try:
        os.makedirs("Uploaded_Internships", exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_pdf.name)
        save_path = os.path.join("Uploaded_Internships", safe_name)
        with open(save_path, "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        return clean_text(pdf_reader(save_path))
    except Exception:
        return ""


def get_internship_text(source_type, url, pdf_file, manual_text):
    manual_text = clean_text(manual_text)
    if manual_text:
        return manual_text

    if source_type == "Website Link":
        return scrape_website_light(url)

    if source_type == "PDF Upload":
        return extract_text_from_uploaded_pdf(pdf_file)

    return ""

# ---------------- SCORING ----------------
def calculate_match(resume_skills, internship_text):
    required_skills = extract_skills(internship_text)
    resume_set = {s.lower() for s in resume_skills}
    required_set = {s.lower() for s in required_skills}

    matched = sorted(resume_set.intersection(required_set))
    missing = sorted(required_set.difference(resume_set))
    score = round((len(matched) / len(required_set)) * 100, 2) if required_set else 0

    return score, [s.title() for s in matched], [s.title() for s in missing], required_skills


def calculate_resume_score(resume_text):
    checks = ["objective", "declaration", "achievements", "projects", "certifications"]
    score = 0
    results = []
    for item in checks:
        found = item in (resume_text or "").lower()
        if found:
            score += 20
        results.append((item.title(), found))
    return min(score, 100), results


def roadmap(skill):
    data = {
        "Python": "Add a Python project with GitHub link.",
        "Machine Learning": "Add one ML project with dataset, model, and accuracy.",
        "Sql": "Add a database project or SQL query practice certificate.",
        "React": "Add a small frontend project or portfolio.",
        "Nlp": "Build sentiment analysis or chatbot project.",
        "Tensorflow": "Add an image classification or prediction project.",
        "Git": "Add GitHub project links in resume.",
        "Power Bi": "Create a dashboard and mention insights.",
    }
    return data.get(skill, f"Learn {skill} and add a small project/certificate as proof.")


def show_chip_list(title, items, empty_message):
    st.subheader(title)
    if not items:
        st.info(empty_message)
        return
    text = " ".join([f"`{item}`" for item in items])
    st.markdown(text)



# ---------------- COURSE.PY INTEGRATION ----------------
# Keep your course lists in a separate file named either course.py or Courses.py
# and place it in the same folder as this app.py file.
try:
    from course import (
        ds_course,
        web_course,
        android_course,
        ios_course,
        uiux_course,
        resume_videos,
        interview_videos,
    )
except Exception:
    try:
        from Courses import (
            ds_course,
            web_course,
            android_course,
            ios_course,
            uiux_course,
            resume_videos,
            interview_videos,
        )
    except Exception:
        ds_course = []
        web_course = []
        android_course = []
        ios_course = []
        uiux_course = []
        resume_videos = []
        interview_videos = []


def course_categories_for_skill(skill):
    """Connect missing skills to your course.py categories."""
    skill = (skill or "").lower()

    data_science_skills = [
        "python", "machine learning", "deep learning", "tensorflow", "keras", "pytorch",
        "scikit-learn", "pandas", "numpy", "data science", "data analysis", "statistics",
        "nlp", "natural language processing", "matplotlib", "plotly", "power bi", "tableau",
        "excel", "opencv", "analytics", "data visualization"
    ]

    web_skills = [
        "html", "css", "javascript", "typescript", "react", "node js", "django", "flask",
        "fastapi", "streamlit", "sql", "mysql", "mongodb", "postgresql", "rest api",
        "api", "beautifulsoup", "selenium", "bootstrap", "tailwind", "git", "github", "docker"
    ]

    android_skills = ["android", "flutter", "kotlin", "firebase"]
    ios_skills = ["ios", "swift"]
    uiux_skills = ["ui", "ux", "figma", "adobe xd", "photoshop"]

    categories = []
    if skill in data_science_skills:
        categories.append(("Data Science / AI", ds_course))
    if skill in web_skills:
        categories.append(("Web Development", web_course))
    if skill in android_skills:
        categories.append(("Android Development", android_course))
    if skill in ios_skills:
        categories.append(("iOS Development", ios_course))
    if skill in uiux_skills:
        categories.append(("UI/UX Design", uiux_course))

    return categories


def recommend_missing_skill_courses(missing_skills):
    st.header("Recommended Courses For Missing Skills 🎯")

    if not missing_skills:
        st.success("No missing technical skills detected. Focus on improving projects and interview preparation.")
        return

    shown_any = False
    already_shown_categories = set()

    for skill in missing_skills:
        categories = course_categories_for_skill(skill)

        if not categories:
            with st.expander(f"{skill} - Learning Suggestion", expanded=False):
                st.markdown(f"- Learn **{skill}** using a beginner-friendly course.")
                st.markdown(f"- Add a small **{skill}** project or certificate to your resume.")
            continue

        for category_name, course_list in categories:
            # Avoid repeating the same full category many times.
            unique_key = (category_name, tuple([skill]))
            with st.expander(f"{skill} → {category_name} Resources", expanded=True):
                if course_list:
                    shown_any = True
                    for index, (course_name, course_link) in enumerate(course_list[:5], start=1):
                        st.markdown(f"{index}. [{course_name}]({course_link})")
                else:
                    st.warning("No courses found. Check that course.py is in the same folder as app.py.")

    if shown_any:
        st.info("Tip: After completing a course, add it under Certifications or Projects in your resume.")
    else:
        st.warning("Could not load course links. Make sure your file is named course.py or Courses.py and is in the same folder.")


def show_support_videos():
    st.header("Helpful Videos 🎥")
    video_col1, video_col2 = st.columns(2)

    with video_col1:
        st.subheader("Resume Building")
        if resume_videos:
            st.video(resume_videos[0])
            with st.expander("More Resume Videos"):
                for link in resume_videos[1:]:
                    st.markdown(f"- [Open video]({link})")
        else:
            st.info("Resume videos not loaded. Check course.py.")

    with video_col2:
        st.subheader("Interview Preparation")
        if interview_videos:
            st.video(interview_videos[0])
            with st.expander("More Interview Videos"):
                for link in interview_videos[1:]:
                    st.markdown(f"- [Open video]({link})")
        else:
            st.info("Interview videos not loaded. Check course.py.")

# ---------------- MAIN APP ----------------
def run():
    st.subheader("AI Resume Analyser & Internship Matcher")
    st.sidebar.markdown("# Dashboard")
    st.sidebar.selectbox("Choose among the given options:", ["Student"])
    st.sidebar.markdown("Student Dashboard - Resume vs Internship")

    st.markdown(
        """<h5 style='text-align:left; color:#021659;'>Compare your resume with internship or company requirements before applying.</h5>""",
        unsafe_allow_html=True,
    )

    upload_col, internship_col = st.columns(2)

    with upload_col:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("📄 1. Upload Student Resume")
        pdf_file = st.file_uploader("Choose your Resume PDF", type=["pdf"], key="resume_upload")
        st.caption("Upload a text-based PDF resume for best result.")
        st.markdown("</div>", unsafe_allow_html=True)

    with internship_col:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("🏢 2. Add Internship / Company Details")
        internship_source = st.selectbox(
            "Choose internship input method",
            ["Paste Text", "Website Link", "PDF Upload"],
            index=0,
        )

        internship_url = ""
        internship_pdf = None
        internship_manual_text = ""

        if internship_source == "Paste Text":
            st.info("Best option for demo: copy internship skills/requirements and paste here.")
            internship_manual_text = st.text_area("Paste internship description / requirements here", height=180)

        elif internship_source == "Website Link":
            st.warning("Some sites block scraping. Paste requirements in backup box for guaranteed result.")
            internship_url = st.text_input("Paste internship website/link here")
            internship_manual_text = st.text_area("Backup: paste internship requirements here", height=130)

        else:
            internship_pdf = st.file_uploader("Upload internship/company PDF", type=["pdf"], key="internship_pdf")
            internship_manual_text = st.text_area("Backup: paste internship requirements here", height=130)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    submit = st.button("🚀 Submit & Compare", use_container_width=True)

    if not submit:
        st.info("Upload your resume and add internship details, then click **Submit & Compare**.")
        return

    try:
        if pdf_file is None:
            st.error("Please upload your resume PDF.")
            return

        if internship_source == "Paste Text" and not internship_manual_text.strip():
            st.error("Please paste the internship requirements.")
            return

        if internship_source == "Website Link" and not internship_url.strip() and not internship_manual_text.strip():
            st.error("Please paste the internship link or paste requirements in backup box.")
            return

        if internship_source == "PDF Upload" and internship_pdf is None and not internship_manual_text.strip():
            st.error("Please upload an internship PDF or paste requirements in backup box.")
            return

        st.success("✅ Uploading complete and comparing begins...")
        st.balloons()
        time.sleep(1)

        with st.spinner("Reading resume and extracting student skills..."):
            os.makedirs("Uploaded_Resumes", exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", pdf_file.name)
            save_resume_path = os.path.join("Uploaded_Resumes", safe_name)
            with open(save_resume_path, "wb") as f:
                f.write(pdf_file.getbuffer())
            resume_data = parse_resume(save_resume_path)

        if not resume_data["text"].strip():
            st.error("Resume text could not be extracted. Try another PDF or a text-based PDF.")
            return

        with st.spinner("Reading internship/company details and finding required skills..."):
            internship_text = get_internship_text(internship_source, internship_url, internship_pdf, internship_manual_text)

        if not internship_text or len(internship_text.strip()) < 20:
            st.error("Could not read internship details. Use Paste Text or fill the backup requirements box.")
            return

        current_skills = resume_data["skills"]
        match_score, matched_skills, missing_skills, required_skills = calculate_match(current_skills, internship_text)
        resume_score, resume_checks = calculate_resume_score(resume_data["text"])
        overall_score = round((resume_score + match_score) / 2, 2)
        candidate_level = "Fresher" if resume_data["no_of_pages"] <= 1 else "Intermediate" if resume_data["no_of_pages"] == 2 else "Experienced"

        with st.expander("View Resume PDF Preview", expanded=False):
            show_pdf_small(save_resume_path)


        st.header("📊 Student Internship Readiness Dashboard")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("ATS Score", f"{resume_score}%")
        m2.metric("Internship Match", f"{match_score}%")
        m3.metric("Overall Readiness", f"{overall_score}%")
        m4.metric("Candidate Level", candidate_level)
        st.progress(min(max(int(overall_score), 0), 100))

        if match_score >= 80:
            st.success("Highly Suitable Candidate ✅ Ready to Apply")
        elif match_score >= 60:
            st.warning("Moderately Suitable Candidate ⚠️ Improve a few missing skills")
        else:
            st.error("Low Match ❌ Upskilling Recommended Before Applying")

        st.header("👤 Resume Analysis")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Name", resume_data["name"])
        c2.metric("Email", resume_data["email"])
        c3.metric("Contact", resume_data["mobile_number"])
        c4.metric("Pages", resume_data["no_of_pages"])

        show_chip_list("Your Current Skills", current_skills, "No major skills detected from resume.")

        st.header("🏢 Internship / Company Requirement Analysis")
        show_chip_list("Skills Required For This Internship", required_skills, "No technical skills detected from internship details.")

        col1, col2 = st.columns(2)
        with col1:
            show_chip_list("Matching Skills ✅", matched_skills, "No matching skills detected.")
        with col2:
            show_chip_list("Missing Skills To Improve ⚠️", missing_skills, "No major missing skills detected.")

        st.subheader("🧭 Skill Gap Roadmap")
        if missing_skills:
            for skill in missing_skills:
                st.markdown(f"- **{skill}** → {roadmap(skill)}")
        else:
            st.success("Your resume covers the detected internship skill requirements.")

        recommend_missing_skill_courses(missing_skills)
        show_support_videos()

        st.header("💡 Resume Review Checklist")
        r1, r2 = st.columns(2)
        with r1:
            for name, found in resume_checks[:3]:
                st.markdown(f"{'✅' if found else '❌'} {name} {'found' if found else 'missing'}")
        with r2:
            for name, found in resume_checks[3:]:
                st.markdown(f"{'✅' if found else '❌'} {name} {'found' if found else 'missing'}")

        st.header("📌 Final Summary")
        st.write("This dashboard compares the student's resume with the selected internship/company requirements and recommends improvements before applying.")
        st.write("Resume Writing Score:", resume_score)
        st.write("Internship Match Score:", match_score)
        st.write("Overall Student Readiness:", overall_score)


    except Exception as e:
        st.error("The app crashed while processing. Exact error is shown below:")
        st.exception(e)


run()