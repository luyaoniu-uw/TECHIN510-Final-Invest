import pandas as pd

EXCEL_FILE = 'TECHIN510_Sp25_Tracker.xlsx'
STUDENTS_CSV = 'students.csv'
PROJECTS_CSV = 'projects.csv'

# Read the Excel file
excel_df = pd.read_excel(EXCEL_FILE)

# Extract unique student names
students = excel_df['Client'].dropna().unique()
students_df = pd.DataFrame({
    'username': students,
    'budget': 600,
    'remaining_budget': 600
})
students_df.to_csv(STUDENTS_CSV, index=False)
print(f"Wrote {len(students)} students to {STUDENTS_CSV}")

# Extract projects as 'Student Name: Project Title'
projects_df = excel_df[['Client', 'Project Title']].dropna()
projects_df = projects_df[(projects_df['Client'].str.strip() != '') & (projects_df['Project Title'].str.strip() != '')]
projects_df['project_name'] = projects_df['Client'].str.strip() + ': ' + projects_df['Project Title'].str.strip()
projects_df = projects_df.drop_duplicates('project_name')
projects_df = projects_df.reset_index(drop=True)
projects_df['project_id'] = [f'P{i+1}' for i in range(len(projects_df))]
projects_csv = projects_df[['project_id', 'project_name']]
projects_csv.to_csv(PROJECTS_CSV, index=False)
print(f"Wrote {len(projects_csv)} projects to {PROJECTS_CSV}") 