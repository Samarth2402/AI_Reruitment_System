resume_records = []

def save_resume(name, skills):
    resume_records.append({
        "name": name,
        "skills": skills
    })

def get_all_resumes():
    return resume_records