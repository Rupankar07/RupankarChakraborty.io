import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import openai

# =============================================================================
# 1. GLOBAL CONSTANTS & CONFIGURATION
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# BENGALI HOLIDAYS 2026
BENGALI_HOLIDAYS = {
    "2026-01-14": "Poush Sankranti",
    "2026-03-27": "Holi / Dol Jatra",
    "2026-04-14": "Poila Baisakh (Bengali New Year)",
    "2026-08-15": "Independence Day",
    "2026-10-20": "Durga Puja",
    "2026-10-22": "Bijoya Dashami",
    "2026-11-08": "Kali Puja",
    "2026-12-25": "Christmas"
}

# GLOBAL CSS - Defined here to prevent any NameError in setup_templates()
DARK_VIOLET_CSS = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
    body { background: radial-gradient(circle at center, #1a0b2e, #05020a); min-height: 100vh; font-family: 'Outfit', sans-serif !important; color: #e0d5ff; }
    .glass-card { background: rgba(30, 10, 50, 0.6); backdrop-filter: blur(20px); border: 1px solid rgba(159, 122, 234, 0.3); border-radius: 24px; transition: 0.3s ease; }
    .btn-violet { background: linear-gradient(45deg, #7c3aed, #9f7aea); color: white; border-radius: 12px; border: none; font-weight: 600; transition: 0.3s; }
    .btn-violet:hover { filter: brightness(1.2); transform: scale(1.05); color: white; }
    .form-control, .form-select { background: #1a0b2e !important; border: 1px solid rgba(159, 122, 234, 0.3) !important; color: white !important; border-radius: 12px; }
    .form-select option { background: #1a0b2e !important; color: white !important; }
    .nav-link-custom { color: #c084fc; text-decoration: none; font-weight: 600; margin-right: 20px; transition: 0.3s; }
    .nav-link-custom:hover { color: white; text-shadow: 0 0 10px #9f7aea; }
    .blink { animation: blinker 1.5s linear infinite; background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
    @keyframes blinker { 50% { opacity: 0; } }
    .stat-value { font-size: 2.2rem; font-weight: 800; background: linear-gradient(to right, #c084fc, #e879f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .news-container { height: 400px; overflow-y: auto; padding-right: 10px; }
    .label-title { font-size: 0.85rem; color: #b0a0ff; margin-bottom: 5px; display: block; font-weight: 600; }
    .search-results { position: absolute; z-index: 1000; width: 100%; background: #1a0b2e; border: 1px solid #9f7aea; border-radius: 10px; max-height: 200px; overflow-y: auto; }
    .search-item { padding: 10px; cursor: pointer; border-bottom: 1px solid rgba(159, 122, 234, 0.2); color: white; }
    .search-item:hover { background: #3b1a6b; }
</style>
"""

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.config['SECRET_KEY'] = 'rupankar_industrial_v20_final'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'enterprise_v20.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

openai.api_key = "YOUR_OPENAI_API_KEY"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# =============================================================================
# 2. DATABASE MODELS
# =============================================================================
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    revenue = db.Column(db.Float, default=0.0)
    expenses = db.Column(db.Float, default=0.0)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default="Employee") 
    salary = db.Column(db.Float, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    skills = db.Column(db.String(200))
    experience = db.Column(db.String(50)) 
    qualification = db.Column(db.String(100))
    qual_other = db.Column(db.String(100))

    @property
    def formatted_id(self):
        return f"5{self.id:04d}"

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    type = db.Column(db.String(50)) 
    status = db.Column(db.String(20), default="Approved") 
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    media_url = db.Column(db.String(500)) 
    is_new = db.Column(db.Boolean, default=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_name = db.Column(db.String(100))
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Pending")

class TimeSheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.String(20))
    hours = db.Column(db.Float)
    task = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Pending")

class OffboardRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="Pending")

class ITIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_sn = db.Column(db.String(10), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    issue_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Open")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =============================================================================
# 3. UI GENERATOR
# =============================================================================
def setup_templates():
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)

    templates = {
        "login.html": """
        <html><head>[[CSS]]</head>
        <body class="d-flex align-items-center justify-content-center">
            <div class="container" style="max-width: 900px;">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <div class="glass-card p-5 shadow text-center">
                            <h1 class="fw-bold" style="font-size: 1.8rem;">RupankarChakraborty<span style="color:#9f7aea">.io</span></h1>
                            <p class="opacity-50 mb-4">Enterprise Cloud Access</p>
                            <form method="POST">
                                <div class="mb-3 text-start"><span class="label-title">Username</span><input type="text" name="username" class="form-control py-3" required></div>
                                <div class="mb-4 text-start"><span class="label-title">Password</span><input type="password" name="password" class="form-control py-3" required></div>
                                <button class="btn btn-violet w-100 py-3">Authenticate</button>
                            </form>
                        </div>
                    </div>
                    <div class="col-md-6 ps-md-5">
                        <div class="glass-card p-4">
                            <h4><i class="bi bi-person-badge"></i> Session Information</h4>
                            <p class="small opacity-75 mt-3">Secure RBAC access for RupankarChakraborty.io.</p>
                        </div>
                    </div>
                </div>
            </div>
        </body></html>""",

        "admin_dashboard.html": """
        <html><head>[[CSS]]</head>
        <body>
            <nav class="navbar navbar-dark px-4 py-3 mb-4 sticky-top" style="background: rgba(10,5,20,0.9); backdrop-filter: blur(10px);">
                <div class="d-flex align-items-center">
                    <a href="/" class="nav-link-custom">Dashboard</a>
                    <a href="/leave" class="nav-link-custom">Leaves</a>
                    <a href="/timesheets" class="nav-link-custom">Time Sheets</a>
                    <a href="/offboard_requests" class="nav-link-custom">Offboarding</a>
                </div>
                <div class="ms-auto d-flex align-items-center">
                    <div class="text-end me-3">
                        <div class="fw-bold">{{ current_user.name }}</div>
                        <div class="small opacity-50">{{ current_user.role }} | {{ current_user.formatted_id }}</div>
                    </div>
                    <a href="/logout" class="btn btn-danger btn-sm">Logout</a>
                </div>
            </nav>
            <div class="container-fluid px-5">
                <div class="row mb-4">
                    <div class="col-md-3"><div class="glass-card p-4 text-center"><h6>Total Revenue</h6><div class="stat-value">${{ total_rev }}</div></div></div>
                    <div class="col-md-3"><div class="glass-card p-4 text-center"><h6>Net Profit</h6><div class="stat-value">{{ total_prof }}</div></div></div>
                    <div class="col-md-3"><div class="glass-card p-4 text-center"><h6>Active Projects</h6><div class="stat-value">{{ proj_count }}</div></div></div>
                    <div class="col-md-3"><div class="glass-card p-4 text-center"><h6>Staff Count</h6><div class="stat-value">{{ user_count }}</div></div></div>
                </div>
                <div class="row">
                    <div class="col-md-8">
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="glass-card p-4">
                                    <h5>📁 Project Addition</h5>
                                    <form action="/add_project" method="POST" class="mt-3">
                                        <div class="mb-2"><span class="label-title">Project Name</span><input type="text" name="name" class="form-control" required></div>
                                        <div class="mb-2"><span class="label-title">Revenue</span><input type="number" step="0.01" name="revenue" class="form-control" required></div>
                                        <div class="mb-3"><span class="label-title">Expenses</span><input type="number" step="0.01" name="expenses" class="form-control" required></div>
                                        <button class="btn btn-violet w-100">Create Project</button>
                                    </form>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="glass-card p-4">
                                    <h5>👥 Employee Onboarding</h5>
                                    <form action="/onboard" method="POST" class="mt-3">
                                        <div class="row g-2">
                                            <div class="col-md-6 mb-2"><span class="label-title">Name</span><input type="text" name="name" class="form-control" required></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Username</span><input type="text" name="username" class="form-control" required></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Password</span><input type="password" name="password" class="form-control" required></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Role</span><select name="role" class="form-select"><option>Employee</option><option>RM</option><option>Admin</option></select></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Experience</span><select name="experience" class="form-select"><option>Fresher</option><option>Experienced</option></select></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Qualification</span><select name="qualification" class="form-select" onchange="toggleOther(this)"><option>BTech</option><option>MTech</option><option>PHD</option><option value="Other">Other</option></select></div>
                                            <div class="col-md-12 mb-2" id="other_qual" style="display:none;"><input type="text" name="qual_other" class="form-control" placeholder="Specify Qualification"></div>
                                            <div class="col-md-12 mb-2"><span class="label-title">Skills (Comma separated)</span><input type="text" name="skills" class="form-control"></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Salary</span><input type="number" step="0.01" name="salary" class="form-control"></div>
                                            <div class="col-md-6 mb-2"><span class="label-title">Project</span><select name="project_id" class="form-select">{% for p in projects %}<option value="{{p.id}}">{{p.name}}</option>{% endfor %}</select></div>
                                            <div class="col-md-12 mb-3"><span class="label-title">Reporting Manager</span><select name="manager_id" class="form-select">{% for u in users if u.role == 'RM' or u.role == 'Admin' %}<option value="{{u.id}}">{{u.name}}</option>{% endfor %}</select></div>
                                        </div>
                                        <button class="btn btn-violet w-100">Onboard Employee</button>
                                    </form>
                                </div>
                            </div>
                        </div>
                        <div class="glass-card p-4 mt-4">
                            <h5>Employee Directory & Project Management</h5>
                            <table class="table table-borderless text-white">
                                <thead><tr><th>Name</th><th>Project</th><th>RM</th><th>Salary</th><th>Action</th></tr></thead>
                                <tbody>
                                    {% for user in users %}
                                    <tr>
                                        <td>{{user.name}}</td>
                                        <td><a href="/edit_user/{{user.id}}" class="text-info">{{user.project_name}}</a></td>
                                        <td>{{user.manager_name}}</td>
                                        <td>${{user.salary or '100'}}</td>
                                        <td><a href="/offboard/{{user.id}}" class="btn btn-sm btn-outline-danger">Offboard</a></td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-4 mb-4">
                            <h5>📢 Enterprise Broadcast</h5>
                            <form action="/post_news" method="POST">
                                <div class="mb-2"><span class="label-title">Title</span><input type="text" name="title" class="form-control" required></div>
                                <div class="mb-2"><span class="label-title">Content</span><textarea name="content" class="form-control"></textarea></div>
                                <div class="mb-2"><span class="label-title">Media URL</span><input type="text" name="media_url" class="form-control"></div>
                                <select name="type" class="form-select mb-3"><option value="Company">Company</option><option value="Project">Project</option><option value="User">User</option></select>
                                <button class="btn btn-violet w-100">Broadcast News</button>
                            </form>
                        </div>
                        <div class="glass-card p-4">
                            <h5>Live Feed</h5>
                            <div class="news-container">
                                {% for n in news %}
                                <div class="mb-3 border-bottom border-white opacity-75 pb-2">
                                    <div class="d-flex justify-content-between"><strong>{{n.title}}</strong>{% if n.is_new %}<span class="blink">NEW</span>{% endif %}</div>
                                    <p class="small">{{n.content}}</p>
                                    {% if n.media_url %}<img src="{{n.media_url}}" class="media-content">{% endif %}
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <script>
                function toggleOther(select) {
                    document.getElementById('other_qual').style.display = (select.value === 'Other') ? 'block' : 'none';
                }
            </script>
        </body></html>""",

        "user_dashboard.html": """
        <html><head>[[CSS]]</head>
        <body>
            <nav class="navbar navbar-dark px-4 py-3 mb-4 sticky-top" style="background: rgba(10,5,20,0.9); backdrop-filter: blur(10px);">
                <div class="d-flex align-items-center">
                    <a href="/" class="nav-link-custom">Dashboard</a>
                    <a href="/leave" class="nav-link-custom">Request Leave</a>
                    <a href="/timesheet" class="nav-link-custom">Time Sheet</a>
                    <a href="/request_offboard" class="nav-link-custom">Offboard Request</a>
                </div>
                <div class="ms-auto d-flex align-items-center">
                    <div class="text-end me-3">
                        <div class="fw-bold">{{ current_user.name }}</div>
                        <div class="small opacity-50">{{ current_user.role }} | {{ current_user.formatted_id }}</div>
                    </div>
                    <a href="/logout" class="btn btn-danger btn-sm">Logout</a>
                </div>
            </nav>
            <div class="container-fluid px-5">
                <div class="row">
                    <div class="col-md-8">
                        <div class="glass-card p-5 text-center mb-4 animate-fade">
                            <h1 class="display-5 fw-bold">Welcome, {{ current_user.name }}! 👋</h1>
                            <div class="row mt-4">
                                <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Salary</h6><div class="fs-4 fw-bold text-info">${{ current_user.salary or '100' }}</div></div></div>
                                <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Project</h6><a href="/project_details/{{ current_user.project_id }}" class="text-info text-decoration-none fs-4 fw-bold">{{ user_project }}</a></div></div>
                                <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Reporting Mgr</h6><div class="fs-4 fw-bold text-info">{{ manager_name }}</div></div></div>
                            </div>
                        </div>
                        <div class="glass-card p-4 mb-4">
                            <h5>📊 My Project Intelligence</h5>
                            {% if project_data %}
                            <div class="row mt-3">
                                <div class="col-md-3"><h6>Project Name: <br><span class="text-info fw-bold">{{ project_data.name }}</span></h6></div>
                                <div class="col-md-3"><h6>Revenue: <br><span class="text-info fw-bold">${{ project_data.revenue }}</span></h6></div>
                                <div class="col-md-3"><h6>Expenses: <br><span class="text-info fw-bold">${{ project_data.expenses }}</span></h6></div>
                                <div class="col-md-3"><h6>Net Profit: <br><span class="text-info fw-bold">${{ project_data.profit }}</span></h6></div>
                            </div>
                            <div class="row mt-3">
                                <div class="col-md-6"><h6>Project Manager: <span class="text-info">{{ project_manager }}</span></h6></div>
                                <div class="col-md-6"><h6>Team Size: <span class="text-info">{{ team_size }} Members</span></h6></div>
                            </div>
                            {% if project_data.expenses >= project_data.revenue %}
                            <div class="alert alert-danger mt-3 small"><b>⚠️ WARNING:</b> Project expenses have exhausted the allocated revenue!</div>
                            {% endif %}
                            {% else %}
                            <div class="text-center opacity-50 mt-3">You are currently not allocated to any active project.</div>
                            {% endif %}
                        </div>
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="glass-card p-4">
                                    <h5>🛠️ IT Support Ticket</h5>
                                    <form action="/report_issue" method="POST" class="mt-3">
                                        <div class="mb-2"><span class="label-title">Issue Type</span>
                                            <select name="issue_type" class="form-select">
                                                <option>Internet Connectivity</option><option>Laptop Hardware</option><option>Software Crash</option><option>VPN Access</option>
                                                <option>Email Login</option><option>Password Reset</option><option>Printer Issue</option><option>Database Access</option>
                                                <option>Slow Performance</option><option>Mouse/Keyboard</option><option>Monitor Issue</option><option>System Update</option>
                                                <option>Application Error</option><option>Network Lag</option><option>Firewall Block</option><option>API Key Access</option>
                                                <option>Disk Space Full</option><option>Blue Screen (BSOD)</option><option>Peripheral Connection</option><option>Other Issue</option>
                                            </select>
                                        </div>
                                        <div class="mb-3"><span class="label-title">Description</span><textarea name="description" class="form-control" required></textarea></div>
                                        <button class="btn btn-violet w-100">File Ticket</button>
                                    </form>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="glass-card p-4">
                                    <h5>💬 Enterprise Messaging</h5>
                                    <div class="chat-box mb-3" id="msg-box" style="height: 200px; overflow-y: auto; background: rgba(0,0,0,0.3); border-radius: 15px; padding: 15px;">
                                        {% for m in messages %}
                                        <div class="small mb-2 d-flex justify-content-between">
                                            <span><b>{{ m.sender_name or 'Broadcast' }}:</b> 
                                            {% if m.content|length > 100 %}
                                                {{ m.content[:100] }}... <a href="/message/{{ m.id }}" class="text-info">Read More</a>
                                            {% else %}
                                                {{ m.content }}
                                            {% endif %}
                                            </span>
                                            {% if loop.index <= 3 %}<span class="blink">NEW</span>{% endif %}
                                        </div>
                                        {% endfor %}
                                    </div>
                                    <div class="position-relative">
                                        <input type="text" id="msg-receiver" class="form-control w-100" placeholder="Search Name or ID..." onkeyup="searchUsers(this.value)">
                                        <div id="user-suggestions" class="search-results" style="display:none;"></div>
                                    </div>
                                    <form action="/send_message" method="POST" class="d-flex gap-2 mt-2">
                                        <input type="hidden" name="receiver_id" id="hidden-receiver">
                                        <input type="text" name="content" class="form-control w-100" placeholder="Message...">
                                        <button class="btn btn-violet">Send</button>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-4 mb-4">
                            <h5>📰 Live News Portal</h5>
                            <div class="news-container">
                                {% for n in news %}
                                <div class="mb-3 border-bottom border-white opacity-75 pb-2">
                                    <div class="d-flex justify-content-between"><strong>{{n.title}}</strong>{% if n.is_new %}<span class="blink">NEW</span>{% endif %}</div>
                                    <p class="small">{{n.content}}</p>
                                    {% if n.media_url %}<img src="{{n.media_url}}" class="media-content">{% endif %}
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                        <div class="glass-card p-4">
                            <h5>🤖 AI HR Assistant</h5>
                            <div id="chat-box" style="height: 200px; overflow-y: auto;" class="small border p-2 mb-2 bg-dark bg-opacity-25 rounded"></div>
                            <div class="input-group">
                                <input type="text" id="u-input" class="form-control" placeholder="Ask AI...">
                                <button class="btn btn-violet" onclick="sendMsg()">Send</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <script>
                async function searchUsers(val) {
                    let box = document.getElementById('user-suggestions');
                    if(val.length < 1) { box.style.display = 'none'; return; }
                    const res = await fetch('/search_users?q=' + val);
                    const users = await res.json();
                    box.innerHTML = '';
                    if(users.length > 0) {
                        box.style.display = 'block';
                        users.forEach(u => {
                            let div = document.createElement('div');
                            div.className = 'search-item';
                            div.innerHTML = `<b>${u.name}</b> (ID: ${u.id})`;
                            div.onclick = () => {
                                document.getElementById('msg-receiver').value = u.name;
                                document.getElementById('hidden-receiver').value = u.id;
                                box.style.display = 'none';
                            };
                            box.appendChild(div);
                        });
                    } else { box.style.display = 'none'; }
                }
                async function sendMsg() {
                    let inp = document.getElementById('u-input');
                    let box = document.getElementById('chat-box');
                    let msg = inp.value;
                    if(!msg) return;
                    box.innerHTML += `<div><b>You:</b> ${msg}</div>`;
                    inp.value = '';
                    const res = await fetch('/chat', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: msg})
                    });
                    const data = await res.json();
                    box.innerHTML += `<div class="text-info"><b>AI:</b> ${data.response}</div><hr>`;
                    box.scrollTop = box.scrollHeight;
                }
            </script>
        </body></html>""",

        "project_details.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Hub</a>
            <div class="glass-card p-5">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Project: {{ project.name }}</h1>
                    {% if current_user.role == 'Admin' %}
                    <a href="/edit_project/{{ project.id }}" class="btn btn-violet">Edit Project</a>
                    {% endif %}
                </div>
                <div class="row g-4">
                    <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Total Revenue</h6><div class="fs-3 fw-bold text-info">${{ project.revenue }}</div></div></div>
                    <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Total Expenses</h6><div class="fs-3 fw-bold text-danger">${{ project.expenses }}</div></div></div>
                    <div class="col-md-4"><div class="p-3 border border-violet rounded-4"><h6>Net Profit</h6><div class="fs-3 fw-bold text-success">${{ project.revenue - project.expenses }}</div></div></div>
                </div>
                <div class="mt-5">
                    <h4>Project Team</h4>
                    <table class="table table-borderless text-white">
                        <thead><tr><th>Name</th><th>Role</th><th>Skills</th></tr></thead>
                        <tbody>
                            {% for u in team %}
                            <tr><td>{{u.name}}</td><td>{{u.role}}</td><td>{{u.skills}}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </body></html>""",

        "message_detail.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Hub</a>
            <div class="glass-card p-5">
                <h3 class="mb-4">Enterprise Message Detail</h3>
                <div class="mb-3"><span class="label-title">Sender:</span> <span class="text-info">{{ sender }}</span></div>
                <div class="mb-3"><span class="label-title">Date:</span> <span class="text-info">{{ timestamp }}</span></div>
                <hr>
                <div class="fs-5 p-3 bg-dark bg-opacity-25 rounded">{{ content }}</div>
            </div>
        </body></html>""",

        "leave.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Hub</a>
            <div class="glass-card p-4">
                <h3 class="mb-4">📅 Leave Management</h3>
                {% if current_user.role == 'Employee' %}
                <form method="POST" class="row g-3 mb-5">
                    <div class="col-md-4"><span class="label-title">Start Date</span><input type="date" name="start" class="form-control" required></div>
                    <div class="col-md-4"><span class="label-title">End Date</span><input type="date" name="end" class="form-control" required></div>
                    <div class="col-md-4" style="display:flex; align-items:flex-end;"><button class="btn btn-violet w-100">Apply Leave</button></div>
                </form>
                {% endif %}
                <table class="table table-borderless text-white">
                    <thead><tr><th>User ID</th><th>Project</th><th>Dates</th><th>Status</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for r in requests %}
                        <tr><td>{{r.user_id}}</td><td>({{r.project_name}})</td><td>{{r.start_date}} to {{r.end_date}}</td>
                        <td><span class="badge {% if r.status=='Approved' %}bg-success{% else %}bg-warning{% endif %}">{{r.status}}</span></td>
                        <td>
                            {% if current_user.role == 'Admin' %}
                            <form method="POST" class="d-inline">
                                <input type="hidden" name="req_id" value="{{r.id}}">
                                <select name="status" onchange="this.form.submit()" class="form-select form-select-sm bg-dark text-white">
                                    <option>Update</option><option value="Approved">Approve</option><option value="Rejected">Reject</option>
                                </select>
                            </form>
                            {% endif %}
                        </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body></html>""",

        "timesheet.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Hub</a>
            <div class="glass-card p-4">
                <h3 class="mb-4">⏰ Work Time Sheet</h3>
                {% if current_user.role == 'Employee' %}
                <form method="POST" class="row g-3 mb-5">
                    <div class="col-md-3"><span class="label-title">Date</span><input type="date" name="date" class="form-control" required></div>
                    <div class="col-md-2"><span class="label-title">Hours</span><input type="number" step="0.1" name="hours" class="form-control" required></div>
                    <div class="col-md-5"><span class="label-title">Task Performed</span><input type="text" name="task" class="form-control" required></div>
                    <div class="col-md-2" style="display:flex; align-items:flex-end;"><button class="btn btn-violet w-100">Log Hours</button></div>
                </form>
                {% endif %}
                <table class="table table-borderless text-white">
                    <thead><tr><th>User</th><th>Date</th><th>Hours</th><th>Task</th><th>Status</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for t in sheets %}
                        <tr><td>{{t.user_id}}</td><td>{{t.date}}</td><td>{{t.hours}}</td><td>{{t.task}}</td>
                        <td><span class="badge {% if t.status=='Approved' %}bg-success{% else %}bg-warning{% endif %}">{{t.status}}</span></td>
                        <td>
                            {% if current_user.role == 'Admin' or current_user.role == 'RM' %}
                            <form method="POST" class="d-inline">
                                <input type="hidden" name="req_id" value="{{t.id}}">
                                <select name="status" onchange="this.form.submit()" class="form-select form-select-sm bg-dark text-white">
                                    <option>Update</option><option value="Approved">Approve</option><option value="Rejected">Reject</option>
                                </select>
                            </form>
                            {% endif %}
                        </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body></html>""",

        "offboard_request.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Hub</a>
            <div class="glass-card p-4">
                <h3 class="mb-4">🚪 Offboarding Request</h3>
                {% if current_user.role == 'Employee' %}
                <form method="POST" class="mb-5">
                    <div class="mb-3"><span class="label-title">Reason for Leaving</span><textarea name="reason" class="form-control" required placeholder="Please provide a detailed reason..."></textarea></div>
                    <button class="btn btn-violet w-100">Submit Request to Manager</button>
                </form>
                {% endif %}
                <table class="table table-borderless text-white">
                    <thead><tr><th>User ID</th><th>Reason</th><th>Status</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for o in requests %}
                        <tr><td>{{o.user_id}}</td><td>{{o.reason}}</td>
                        <td><span class="badge {% if o.status=='Approved' %}bg-success{% else %}bg-warning{% endif %}">{{o.status}}</span></td>
                        <td>
                            {% if current_user.role == 'Admin' or current_user.role == 'RM' %}
                            <form method="POST" class="d-inline">
                                <input type="hidden" name="req_id" value="{{o.id}}">
                                <select name="status" onchange="this.form.submit()" class="form-select form-select-sm bg-dark text-white">
                                    <option>Update</option><option value="Approved">Approve</option><option value="Rejected">Reject</option>
                                </select>
                            </form>
                            {% endif %}
                        </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body></html>""",

        "edit_user.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Dashboard</a>
            <div class="glass-card p-4">
                <h3>Edit Employee Allocation</h3>
                <form method="POST" class="mt-4">
                    <div class="mb-3"><span class="label-title">Current User: {{ user.name }}</span></div>
                    <div class="mb-3"><span class="label-title">New Project</span>
                        <select name="project_id" class="form-select">
                            {% for p in projects %}<option value="{{p.id}}" {% if p.id == user.project_id %}selected{% endif %}>{{p.name}}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="mb-3"><span class="label-title">New Reporting Manager</span>
                        <select name="manager_id" class="form-select">
                            {% for u in managers %}<option value="{{u.id}}" {% if u.id == user.manager_id %}selected{% endif %}>{{u.name}}</option>{% endfor %}
                        </select>
                    </div>
                    <button class="btn btn-violet w-100">Update & Broadcast Change</button>
                </form>
            </div>
        </body></html>""",

        "edit_project.html": """
        <html><head>[[CSS]]</head>
        <body class="container mt-5">
            <a href="/" class="btn btn-outline-light mb-4">← Back to Dashboard</a>
            <div class="glass-card p-4">
                <h3>Edit Project Details</h3>
                <form method="POST" class="mt-4">
                    <div class="mb-3"><span class="label-title">Project Name</span><input type="text" name="name" class="form-control" value="{{ project.name }}" required></div>
                    <div class="mb-3"><span class="label-title">Revenue</span><input type="number" step="0.01" name="revenue" class="form-control" value="{{ project.revenue }}" required></div>
                    <div class="mb-3"><span class="label-title">Expenses</span><input type="number" step="0.01" name="expenses" class="form-control" value="{{ project.expenses }}" required></div>
                    <div class="mb-3"><span class="label-title">Project Manager</span>
                        <select name="manager_id" class="form-select">
                            {% for u in users %}<option value="{{u.id}}" {% if u.id == project.manager_id %}selected{% endif %}>{{u.name}}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="mb-3"><span class="label-title">Project Supervisor</span>
                        <select name="supervisor_id" class="form-select">
                            {% for u in users %}<option value="{{u.id}}" {% if u.id == project.supervisor_id %}selected{% endif %}>{{u.name}}</option>{% endfor %}
                        </select>
                    </div>
                    <button class="btn btn-violet w-100">Save Changes & Broadcast</button>
                </form>
            </div>
        </body></html>"""
    }

    for filename, content in templates.items():
        final_content = content.replace('[[CSS]]', DARK_VIOLET_CSS)
        with open(os.path.join(TEMPLATE_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(final_content)

# =============================================================================
# 4. ROUTES & LOGIC
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    today = datetime.now().date()
    for i in range(1, 4):
        check_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        if check_date in BENGALI_HOLIDAYS:
            holiday_name = BENGALI_HOLIDAYS[check_date]
            exists = News.query.filter_by(title=f"Upcoming Holiday: {holiday_name}").first()
            if not exists:
                db.session.add(News(title=f"Upcoming Holiday: {holiday_name}", content=f"Get ready! {holiday_name} is coming up on {check_date}.", type="Company"))
                db.session.commit()

    news_list = News.query.order_by(News.id.desc()).filter_by(status="Approved").all()
    if current_user.role == 'Admin':
        users = User.query.all()
        projects = Project.query.all()
        total_rev = sum(p.revenue for p in projects)
        total_prof = sum(p.revenue - p.expenses for p in projects)
        user_list_with_proj = []
        for u in users:
            p = db.session.get(Project, u.project_id)
            m = db.session.get(User, u.manager_id)
            user_list_with_proj.append({
                "name": u.name, "project_name": p.name if p else "Unallocated",
                "manager_name": m.name if m else "N/A", "salary": u.salary,
                "id": u.id, "role": u.role
            })
        return render_template('admin_dashboard.html', users=user_list_with_proj, projects=projects, 
                               news=news_list, total_rev=total_rev, total_prof=total_prof, 
                               user_count=len(users), proj_count=len(projects))
    
    proj = db.session.get(Project, current_user.project_id)
    user_proj = proj.name if proj else "Unallocated"
    project_data = None
    project_manager = "N/A"
    team_size = 0
    if proj:
        project_data = {"name": proj.name, "revenue": proj.revenue, "expenses": proj.expenses, "profit": proj.revenue - proj.expenses}
        mgr = db.session.get(User, proj.manager_id)
        project_manager = mgr.name if mgr else "Not Assigned"
        team_size = User.query.filter_by(project_id=proj.id).count()

    manager = db.session.get(User, current_user.manager_id)
    manager_name = manager.name if manager else "No Assigned Manager"
    raw_messages = Message.query.order_by(Message.timestamp.desc()).filter((Message.receiver_id == current_user.id) | (Message.receiver_id == None)).all()
    processed_messages = []
    for m in raw_messages:
        sender = db.session.get(User, m.sender_id)
        processed_messages.append({
            "id": m.id, "sender_name": sender.name if sender else "Broadcast",
            "content": m.content, "timestamp": m.timestamp.strftime("%Y-%m-%d %H:%M")
        })
    
    return render_template('user_dashboard.html', news=news_list, user_project=user_proj, 
                           project_data=project_data, project_manager=project_manager, team_size=team_size,
                           manager_name=manager_name, messages=processed_messages)

@app.route('/project_details/<int:id>')
@login_required
def project_details(id):
    proj = db.session.get(Project, id)
    if not proj: return "Project Not Found", 404
    team = User.query.filter_by(project_id=id).all()
    return render_template('project_details.html', project=proj, team=team)

@app.route('/search_users')
@login_required
def search_users():
    q = request.args.get('q', '')
    users = User.query.filter(User.name.contains(q) | User.username.contains(q)).limit(10).all()
    return jsonify([{"id": u.id, "name": u.name} for u in users])

@app.route('/add_project', methods=['POST'])
@login_required
def add_project():
    if current_user.role != 'Admin': return "Unauthorized", 403
    new_p = Project(name=request.form['name'], revenue=float(request.form['revenue']), expenses=float(request.form['expenses']))
    db.session.add(new_p)
    db.session.commit()
    db.session.add(News(title=f"New Project: {new_p.name}", content=f"Project {new_p.name} has been added to the portfolio.", type="Project"))
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/edit_project/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_project(id):
    if current_user.role != 'Admin': return "Unauthorized", 403
    proj = db.session.get(Project, id)
    if request.method == 'POST':
        proj.name = request.form['name']
        proj.revenue = float(request.form['revenue'])
        proj.expenses = float(request.form['expenses'])
        proj.manager_id = request.form['manager_id']
        proj.supervisor_id = request.form['supervisor_id']
        db.session.commit()
        db.session.add(News(title=f"Project Updated: {proj.name}", content=f"Details for {proj.name} have been updated.", type="Project"))
        db.session.commit()
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('edit_project.html', project=proj, users=users)

@app.route('/onboard', methods=['POST'])
@login_required
def onboard():
    if current_user.role != 'Admin': return "Unauthorized", 403
    salary_val = request.form.get('salary')
    salary_float = float(salary_val) if salary_val and salary_val.strip() else 100.0
    new_user = User(username=request.form['username'], password=generate_password_hash(request.form['password']), 
                    name=request.form['name'], role=request.form['role'], salary=salary_float, 
                    project_id=request.form.get('project_id'), manager_id=request.form.get('manager_id'),
                    skills=request.form.get('skills'), experience=request.form.get('experience'),
                    qualification=request.form.get('qualification'), qual_other=request.form.get('qual_other'))
    db.session.add(new_user)
    db.session.commit()
    proj = db.session.get(Project, new_user.project_id)
    p_name = proj.name if proj else "General"
    db.session.add(News(title=f"New Joiner: {new_user.name}", content=f"{new_user.name} joined as {new_user.role} in {p_name}!", type="User"))
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'Admin': return "Unauthorized", 403
    user = db.session.get(User, id)
    if request.method == 'POST':
        old_proj_id = user.project_id
        user.project_id = request.form['project_id']
        user.manager_id = request.form['manager_id']
        db.session.commit()
        if old_proj_id != user.project_id:
            old_p = db.session.get(Project, old_proj_id)
            new_p = db.session.get(Project, user.project_id)
            old_name = old_p.name if old_p else "General"
            new_name = new_p.name if new_p else "General"
            db.session.add(News(title=f"Reallocation: {user.name}", content=f"{user.name} moved from {old_name} to {new_name}.", type="User"))
            db.session.commit()
        return redirect(url_for('dashboard'))
    projects = Project.query.all()
    managers = User.query.filter(User.role.in_(['Admin', 'RM'])).all()
    return render_template('edit_user.html', user=user, projects=projects, managers=managers)

@app.route('/offboard/<int:id>')
@login_required
def offboard(id):
    if current_user.role != 'Admin': return "Unauthorized", 403
    user = db.session.get(User, id)
    db.session.add(News(title=f"Farewell: {user.name}", content=f"{user.name} has left the company.", type="User"))
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/post_news', methods=['POST'])
@login_required
def post_news():
    if current_user.role != 'Admin': return "Unauthorized", 403
    db.session.add(News(title=request.form['title'], content=request.form['content'], type=request.form['type'], media_url=request.form['media_url']))
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/report_issue', methods=['POST'])
@login_required
def report_issue():
    sn = "".join([str(random.randint(0,9)) for _ in range(6)])
    db.session.add(ITIssue(ticket_sn=sn, user_id=current_user.id, issue_type=request.form['issue_type'], description=request.form['description']))
    db.session.commit()
    db.session.add(News(title=f"IT Ticket #{sn}", content=f"Ticket raised by {current_user.name} for {request.form['issue_type']}.", type="IT"))
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    receiver_input = request.form.get('receiver_id')
    content = request.form.get('content')
    rid = None
    if receiver_input and receiver_input.strip():
        if receiver_input.isdigit():
            rid = int(receiver_input)
        else:
            user = User.query.filter_by(username=receiver_input).first()
            if user: rid = user.id
    db.session.add(Message(sender_id=current_user.id, receiver_id=rid, content=content))
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/leave', methods=['GET', 'POST'])
@login_required
def leave():
    if request.method == 'POST':
        if current_user.role == 'Admin':
            req = db.session.get(LeaveRequest, request.form.get('req_id'))
            if req:
                req.status = request.form['status']
                if req.status == "Approved":
                    db.session.add(News(title="Leave Approved", content=f"User {req.user_id} leave approved ({req.project_name})", type="Leave"))
        else:
            proj = db.session.get(Project, current_user.project_id)
            p_name = proj.name if proj else "General"
            db.session.add(LeaveRequest(user_id=current_user.id, project_name=p_name, start_date=request.form['start'], end_date=request.form['end']))
        db.session.commit()
        return redirect(url_for('leave'))
    requests = LeaveRequest.query.all() if current_user.role == 'Admin' else LeaveRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('leave.html', requests=requests)

@app.route('/timesheet', methods=['GET', 'POST'])
@login_required
def timesheet():
    if request.method == 'POST':
        try:
            t = TimeSheet(user_id=current_user.id, date=request.form.get('date'), hours=float(request.form.get('hours', 0)), task=request.form.get('task'))
            db.session.add(t)
            db.session.commit()
        except Exception as e: flash(f"Error: {e}")
        return redirect(url_for('timesheet'))
    sheets = TimeSheet.query.all() if current_user.role in ['Admin', 'RM'] else TimeSheet.query.filter_by(user_id=current_user.id).all()
    return render_template('timesheet.html', sheets=sheets)

@app.route('/request_offboard', methods=['GET', 'POST'])
@login_required
def request_offboard():
    if request.method == 'POST':
        db.session.add(OffboardRequest(user_id=current_user.id, reason=request.form['reason']))
        db.session.commit()
        return redirect(url_for('dashboard'))
    requests = OffboardRequest.query.all() if current_user.role in ['Admin', 'RM'] else OffboardRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('offboard_request.html', requests=requests)

@app.route('/approve_offboard', methods=['POST'])
@login_required
def approve_offboard():
    if current_user.role not in ['Admin', 'RM']: return "Unauthorized", 403
    req = db.session.get(OffboardRequest, request.form.get('req_id'))
    if req:
        req.status = "Approved"
        user = db.session.get(User, req.user_id)
        db.session.add(News(title="Farewell", content=f"Employee {user.name} has left the company.", type="User"))
        db.session.commit()
    return redirect(url_for('request_offboard'))

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    user_msg = request.json.get("message")
    try:
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "You are the AI HR of RupankarChakraborty.io."}, {"role": "user", "content": user_msg}])
        ans = response.choices[0].message.content
    except: ans = "AI is offline."
    return jsonify({"response": ans})

# =============================================================================
# 5. EXECUTION
# =============================================================================
if __name__ == '__main__':
    setup_templates()
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", password=generate_password_hash("admin123"), role="Admin", name="Rupankar Chakraborty")
            db.session.add(admin)
            db.session.add(Project(name="Enterprise Alpha", revenue=500000, expenses=200000))
            db.session.commit()
    app.run(debug=True)