import streamlit as st
import pandas as pd
from database import (
    init_db,
    get_students,
    get_projects,
    get_investments,
    add_or_update_student,
    add_or_update_project,
    add_investment,
    migrate_from_csv,
    reset_db,
    ADMIN_PASSWORD
)

# Add caching for Firestore reads
@st.cache_data(ttl=10)
def get_students_cached():
    return get_students()

@st.cache_data(ttl=10)
def get_projects_cached():
    return get_projects()

@st.cache_data(ttl=10)
def get_investments_cached():
    return get_investments()

# Initialize the database
init_db()

# Migrate existing CSV data if this is the first run
if 'db_migrated' not in st.session_state:
    migrate_from_csv()
    st.session_state.db_migrated = True

def main():
    st.title('Final Project Investment Platform')
    page = st.sidebar.selectbox('Choose your role', ['Student', 'Admin'])
    
    if page == 'Student':
        student_page()
    else:
        admin_login()

def admin_login():
    st.header('Admin Login')
    
    # Check if already authenticated
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        password = st.text_input('Enter admin password:', type='password')
        if st.button('Login'):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error('Incorrect password!')
    else:
        admin_page()
        if st.sidebar.button('Logout'):
            st.session_state.admin_authenticated = False
            st.rerun()

def student_page():
    # Show success message after rerun if present
    if st.session_state.get('show_success'):
        st.success(st.session_state['show_success'])
        del st.session_state['show_success']
    st.header('Student Portal')
    username = st.text_input('Enter your username:')
    if not username:
        st.info('Please enter your username to continue.')
        return

    students = get_students_cached()
    projects = get_projects_cached()
    investments = get_investments_cached()

    # Check if student exists
    if username not in students['username'].values:
        st.warning('Username not found. Please contact admin to be added.')
        return

    student_row = students[students['username'] == username].iloc[0]
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Budget", value=f"${student_row['budget']}")
    with col2:
        st.metric(label="Remaining Budget", value=f"${student_row['remaining_budget']}")

    # Calculate total investment earned by this student's project(s)
    owned_projects = projects[projects['project_name'].str.split(':', n=1).str[0].str.strip().str.lower() == username.strip().lower()]
    if not owned_projects.empty:
        owned_project_ids = owned_projects['project_id'].tolist()
        earned = investments[investments['project_id'].isin(owned_project_ids)]['amount'].sum()
    else:
        earned = 0
    st.metric(label="Investment Earned (Your Project)", value=f"${earned}")

    st.subheader('Projects')
    for _, row in projects.iterrows():
        display_name = row['project_name']
        owner = display_name.split(':')[0].strip() if ':' in display_name else display_name.strip()
        
        # Hide the project if it belongs to the logged-in student
        if owner.lower() == username.strip().lower():
            continue

        st.markdown(f"**{display_name}**")
        invest_amount = st.number_input(
            f"Invest in {display_name}",
            min_value=0,
            max_value=int(student_row['remaining_budget']),
            key=f"invest_{row['project_id']}"
        )

        if st.button(f"Invest ${invest_amount}", key=f"btn_{row['project_id']}"):
            if invest_amount > 0 and invest_amount <= student_row['remaining_budget']:
                try:
                    add_investment(username, row['project_id'], invest_amount)
                    st.session_state['show_success'] = f"Invested ${invest_amount} in {display_name}!"
                    st.cache_data.clear()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.subheader('Your Investments')
    my_investments = investments[investments['username'] == username]
    if not my_investments.empty:
        merged = my_investments.merge(projects, on='project_id')
        merged[['Student', 'Project Title']] = merged['project_name'].str.split(':', n=1, expand=True)
        merged['Student'] = merged['Student'].str.strip()
        merged['Project Title'] = merged['Project Title'].str.strip()
        # Format the Invested Amount to 2 decimal places
        merged['amount'] = merged['amount'].map(lambda x: f"${x:.2f}")
        st.table(merged[['Student', 'Project Title', 'amount']].rename(columns={'amount': 'Invested Amount'}))
    else:
        st.write('No investments yet.')

def admin_page():
    st.header('Admin Dashboard')
    
    # Add database reset functionality
    st.sidebar.markdown('---')
    st.sidebar.subheader('Database Management')
    if st.sidebar.button('Reset Database', type='primary'):
        if st.sidebar.checkbox('I understand this will delete all data'):
            reset_db()
            st.session_state.db_migrated = False  # Allow re-migration of CSV if they exist
            st.sidebar.success('Database has been reset!')
            st.rerun()
        else:
            st.sidebar.warning('Please confirm that you want to reset the database')

    # Add button to clear only investments and reset student budgets
    if st.sidebar.button('Clear All Investments'):
        from database import investments_ref, students_ref
        # Delete all docs in investments collection
        for doc in investments_ref().stream():
            doc.reference.delete()
        # Reset all students' remaining_budget to their budget
        for student_doc in students_ref().stream():
            student = student_doc.to_dict()
            if student and 'budget' in student:
                student_doc.reference.update({'remaining_budget': student['budget']})
        st.sidebar.success('All investments have been cleared and student budgets reset!')
        st.cache_data.clear()
        st.rerun()

    students = get_students_cached()
    projects = get_projects_cached()
    investments = get_investments_cached()

    st.subheader('Add/Edit Students')
    with st.form('add_student'):
        new_username = st.text_input('Student Username')
        new_budget = st.number_input('Budget', min_value=0, value=2000)
        submitted = st.form_submit_button('Add/Update Student')
        if submitted and new_username:
            add_or_update_student(new_username, new_budget)
            st.success('Student added/updated!')
            st.rerun()

    st.dataframe(students)

    st.subheader('Add/Edit Projects')
    with st.form('add_project'):
        project_id = st.text_input('Project ID')
        project_name = st.text_input('Project Name (format: student name: Project title)')
        submitted = st.form_submit_button('Add/Update Project')
        if submitted and project_id and project_name:
            add_or_update_project(project_id, project_name)
            st.success('Project added/updated!')
            st.rerun()

    if not projects.empty:
        projects_display = projects.copy()
        projects_display[['Student', 'Project Title']] = projects_display['project_name'].str.split(':', n=1, expand=True)
        projects_display['Student'] = projects_display['Student'].str.strip()
        projects_display['Project Title'] = projects_display['Project Title'].str.strip()
        st.dataframe(projects_display[['project_id', 'Student', 'Project Title']])
    else:
        st.write('No projects yet.')

    st.subheader('All Investments')
    if not investments.empty:
        merged = investments.merge(projects, on='project_id').merge(students, on='username')
        merged[['Student', 'Project Title']] = merged['project_name'].str.split(':', n=1, expand=True)
        merged['Student'] = merged['Student'].str.strip()
        merged['Project Title'] = merged['Project Title'].str.strip()
        # Format timestamp and display investments
        display_df = merged[['username', 'Student', 'Project Title', 'amount', 'timestamp']].copy()
        display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df.columns = ['Investor', 'Student', 'Project Title', 'Invested Amount', 'Timestamp']
        st.dataframe(display_df, hide_index=True)
    else:
        st.write('No investments yet.')

    st.subheader('Project Earnings')
    if not investments.empty:
        earnings = investments.groupby('project_id')['amount'].sum().reset_index()
        earnings = earnings.merge(projects, on='project_id')
        earnings[['Student', 'Project Title']] = earnings['project_name'].str.split(':', n=1, expand=True)
        earnings['Student'] = earnings['Student'].str.strip()
        earnings['Project Title'] = earnings['Project Title'].str.strip()
        st.table(earnings[['Student', 'Project Title', 'amount']].rename(columns={'amount': 'Total Investment'}))
    else:
        st.write('No investments yet.')

if __name__ == '__main__':
    main() 