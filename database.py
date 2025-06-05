import os
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime

# Constants
ADMIN_PASSWORD = 'admin123'  # Change as needed
CREDENTIALS_FILE = 'firestore_creds.json'

# Firestore setup
creds = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE)
db = firestore.Client(credentials=creds)

# Helper: Firestore collection references
def students_ref():
    return db.collection('students')
def projects_ref():
    return db.collection('projects')
def investments_ref():
    return db.collection('investments')

# Database API
def init_db():
    # Firestore is schemaless, so nothing to do here
    pass

def get_students():
    docs = students_ref().stream()
    data = [doc.to_dict() | {'username': doc.id} for doc in docs]
    return pd.DataFrame(data)

def get_projects():
    docs = projects_ref().stream()
    data = [doc.to_dict() | {'project_id': doc.id} for doc in docs]
    return pd.DataFrame(data)

def get_investments():
    docs = investments_ref().stream()
    data = [doc.to_dict() | {'id': doc.id} for doc in docs]
    df = pd.DataFrame(data)
    # Ensure columns exist even if empty
    for col in ['username', 'project_id', 'amount', 'timestamp']:
        if col not in df.columns:
            df[col] = []
    return df

def add_or_update_student(username, budget):
    doc = students_ref().document(username)
    student = doc.get().to_dict()
    if student:
        # Update budget and adjust remaining_budget by the difference
        diff = budget - student.get('budget', 0)
        new_remaining = student.get('remaining_budget', budget) + diff
        doc.set({'budget': budget, 'remaining_budget': new_remaining}, merge=True)
    else:
        doc.set({'budget': budget, 'remaining_budget': budget})

def add_or_update_project(project_id, project_name):
    doc = projects_ref().document(project_id)
    doc.set({'project_name': project_name})

def add_investment(username, project_id, amount):
    # Transaction to ensure atomic update
    @firestore.transactional
    def invest_transaction(transaction):
        student_doc = students_ref().document(username)
        snapshot = student_doc.get(transaction=transaction)
        student = snapshot.to_dict()
        if not student:
            raise ValueError('Student not found')
        if student['remaining_budget'] < amount:
            raise ValueError('Insufficient budget')
        # Update remaining budget
        transaction.update(student_doc, {'remaining_budget': student['remaining_budget'] - amount})
        # Add investment
        investments_ref().add({
            'username': username,
            'project_id': project_id,
            'amount': amount,
            'timestamp': datetime.now().isoformat()
        })
    invest_transaction(db.transaction())

def migrate_from_csv():
    if not os.path.exists('projects.csv'):
        return
    df = pd.read_csv('projects.csv', encoding='utf-8')
    # Extract students and projects
    students = []
    projects = []
    for _, row in df.iterrows():
        project_id = row['project_id']
        project_name = row['project_name']
        if ':' in project_name:
            student_name, project_title = project_name.split(':', 1)
            student_name = student_name.strip()
            project_title = project_title.strip()
        else:
            student_name = project_name.strip()
            project_title = ''
        students.append(student_name)
        projects.append({'project_id': project_id, 'project_name': f'{student_name}: {project_title}'})
    students = list(set(students))
    # Add students and projects to Firestore
    for s in students:
        students_ref().document(s).set({'budget': 100, 'remaining_budget': 100})
    for p in projects:
        projects_ref().document(p['project_id']).set({'project_name': p['project_name']})

def reset_db():
    # Delete all docs in each collection
    for ref in [students_ref(), projects_ref(), investments_ref()]:
        docs = ref.stream()
        for doc in docs:
            doc.reference.delete() 