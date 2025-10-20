import os
from flask import Flask, request, redirect, url_for, session, flash, abort, jsonify, render_template
from jinja2 import DictLoader
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'database.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'uma_chave_default')

# --- Templates ---
TEMPLATES = {
    'base.html': '''
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title or 'Site de Vídeos' }}</title>
<style>
body{font-family:Arial,sans-serif;max-width:1000px;margin:0 auto;padding:20px;background:#f8f9fb}
header{display:flex;justify-content:space-between;align-items:center}
nav a{margin-left:12px;text-decoration:none}
.video-card{background:#fff;padding:12px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:12px}
.comment{border-top:1px solid #eee;padding:8px 0}
.comment small{color:#666}
form textarea{width:100%;height:80px}
.btn{display:inline-block;padding:8px 12px;border-radius:6px;background:#0b6cff;color:#fff;text-decoration:none}
.login-box{max-width:360px;margin:20px auto;background:#fff;padding:16px;border-radius:8px}
.meta{color:#666;font-size:90%}
.avatar{width:40px;height:40px;border-radius:50%;vertical-align:middle;margin-right:8px;cursor:pointer;object-fit:cover}
.comment-actions{font-size:12px;color:#999;margin-left:8px;cursor:pointer}
.blocked{color:red;font-weight:bold}
</style>
<script>
function submitComment(event, form) {
    event.preventDefault();
    fetch(form.action, {
        method:'POST',
        body:new FormData(form)
    }).then(res=>res.json()).then(data=>{
        if(data.success){
            let container = document.getElementById('comments');
            let html = '<div class="comment"><strong>'+data.username+'</strong> <small>— '+data.created_at+'</small><p>'+data.content+'</p></div>';
            container.innerHTML = html + container.innerHTML;
            form.reset();
        } else {
            alert(data.error);
        }
    });
}
function deleteComment(comment_id){
    if(confirm('Deseja realmente deletar este comentário?')){
        fetch('/comment/'+comment_id+'/delete',{method:'POST'}).then(()=>location.reload());
    }
}
function editComment(comment_id){
    let content = prompt('Edite seu comentário:');
    if(content) fetch('/comment/'+comment_id+'/edit',{method:'POST',body:new URLSearchParams({content})}).then(()=>location.reload());
}
function blockUser(user_id){if(confirm('Deseja bloquear este usuário?'))fetch('/user/'+user_id+'/block',{method:'POST'}).then(()=>location.reload());}
function unblockUser(user_id){if(confirm('Deseja desbloquear este usuário?'))fetch('/user/'+user_id+'/unblock',{method:'POST'}).then(()=>location.reload());}
function visitUser(user_id){window.location.href='/user/'+user_id;}
</script>
</head>
<body>
<header>
<h1><a href="/">Site de Filmes</a></h1>
<nav>
{% if 'user_id' in session %}
Olá, {{ session.get('username') }}
<a href="{{ url_for('logout') }}">Sair</a>
{% else %}
<a href="{{ url_for('login') }}">Entrar</a>
<a href="{{ url_for('register') }}">Registrar</a>
{% endif %}
</nav>
</header>
<main>
{% with messages = get_flashed_messages() %}
{% if messages %}
<ul>
{% for m in messages %}<li>{{ m }}</li>{% endfor %}
</ul>
{% endif %}
{% endwith %}
{% block content %}{% endblock %}
</main>
</body>
</html>
''',
    'index.html': '''
{% extends 'base.html' %}
{% block content %}
<h2>Vídeos</h2>
{% for v in videos %}
<div class="video-card">
<h3><a href="{{ url_for('video_page', video_id=v['id']) }}">{{ v['title'] }}</a></h3>
<p class="meta">{{ v['description'] }}</p>
<p><a class="btn" href="{{ url_for('video_page', video_id=v['id']) }}">Ver</a></p>
</div>
{% else %}
<p>Nenhum vídeo cadastrado.</p>
{% endfor %}
{% endblock %}
''',
    'login.html': '''
{% extends 'base.html' %}
{% block content %}
<div class="login-box">
<h2>Entrar</h2>
<form method="post">
<label>Usuário<br><input name="username" required></label><br><br>
<label>Senha<br><input type="password" name="password" required></label><br><br>
<button class="btn" type="submit">Entrar</button>
</form>
<p>Não tem conta? <a href="{{ url_for('register') }}">Registre-se</a></p>
</div>
{% endblock %}
''',
    'register.html': '''
{% extends 'base.html' %}
{% block content %}
<div class="login-box">
<h2>Registrar</h2>
<form method="post">
<label>Usuário<br><input name="username" required></label><br><br>
<label>Senha<br><input type="password" name="password" required></label><br><br>
<button class="btn" type="submit">Criar conta</button>
</form>
</div>
{% endblock %}
''',
    'video.html': '''
{% extends 'base.html' %}
{% block content %}
<a href="{{ url_for('index') }}">&larr; Voltar</a>
<h2>{{ video['title'] }}</h2>
<p class="meta">{{ video['description'] }}</p>
<div style="background:#000;padding:10px;border-radius:8px">
{% if video['filepath'] %}
<video width="100%" controls>
<source src="/{{ video['filepath'] }}" type="video/mp4">
Seu navegador não suporta a tag video.
</video>
{% else %}
<p>Vídeo não encontrado. Coloque o arquivo em static/videos/ e atualize o campo filepath no DB.</p>
{% endif %}
</div>
<section style="margin-top:18px">
<h3>Comentários ({{ comments|length }})</h3>
{% if 'user_id' in session %}
<form method="post" action="{{ url_for('add_comment', video_id=video['id']) }}" onsubmit="submitComment(event,this)">
<textarea name="content" required placeholder="Escreva seu comentário..."></textarea>
<button class="btn" type="submit">Comentar</button>
</form>
{% else %}
<p>Você precisa <a href="{{ url_for('login') }}">entrar</a> para comentar.</p>
{% endif %}
<div id="comments" style="margin-top:12px">
{% for c in comments %}
<div class="comment">
<img src="{{ c['avatar'] or 'static/avatars/default.png' }}" class="avatar" onclick="visitUser({{ c['user_id'] }})">
<strong>{{ c['username'] }}</strong>
<small>— {{ c['created_at'] }}</small>
<p>{{ c['content'] }}</p>
{% if session.get('user_id')==c['user_id'] %}<span class="comment-actions" onclick="editComment({{ c['id'] }})">[Editar]</span><span class="comment-actions" onclick="deleteComment({{ c['id'] }})">[Excluir]</span>{% endif %}
{% if session.get('user_id')!=c['user_id'] %}<span class="comment-actions" onclick="blockUser({{ c['user_id'] }})">[Bloquear]</span>{% endif %}
</div>
{% else %}<p>Seja o primeiro a comentar.</p>{% endfor %}
</div>
</section>
{% endblock %}
''',
    'user.html': '''
{% extends 'base.html' %}
{% block content %}
<a href="{{ url_for('index') }}">&larr; Voltar</a>
<h2>Perfil de {{ user['username'] }}</h2>
<img src="{{ user['avatar'] or 'static/avatars/default.png' }}" class="avatar" style="width:100px;height:100px">
<p>Id do usuário: {{ user['id'] }}</p>
{% if session.get('user_id')!=user['id'] %}
{% if blocked %}<button class="btn" onclick="unblockUser({{ user['id'] }})">Desbloquear</button>{% else %}<button class="btn" onclick="blockUser({{ user['id'] }})">Bloquear</button>{% endif %}
{% endif %}
{% endblock %}
'''
}

app.jinja_loader = DictLoader(TEMPLATES)

# --- Banco de dados ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if os.path.exists(DB_PATH): return
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    avatar TEXT
);
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    filepath TEXT
);
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(video_id) REFERENCES videos(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL,
    blocked_id INTEGER NOT NULL
);
''')
    # Inserir vídeos de exemplo
    cur.executemany('INSERT INTO videos (title, description, filepath) VALUES (?,?,?)', [
        ('Vídeo Exemplo 1','Descrição 1','static/videos/sample1.mp4'),
        ('Vídeo Exemplo 2','Descrição 2','static/videos/sample2.mp4')
    ])
    conn.commit()
    conn.close()

init_db()

# --- Rotas ---
@app.route('/')
def index():
    conn = get_db()
    videos = [dict(v) for v in conn.execute('SELECT * FROM videos ORDER BY id DESC').fetchall()]
    conn.close()
    return render_template('index.html', videos=videos)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Preencha usuário e senha'); return redirect(url_for('register'))
        pw_hash = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username,password_hash) VALUES (?,?)',(username,pw_hash))
            conn.commit()
            flash('Conta criada. Faça login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Nome de usuário já existe'); return redirect(url_for('register'))
        finally: conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'],password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logado com sucesso'); return redirect(url_for('index'))
        else: flash('Usuário ou senha inválidos'); return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Você saiu'); return redirect(url_for('index'))

@app.route('/video/<int:video_id>')
def video_page(video_id):
    conn = get_db()
    video = conn.execute('SELECT * FROM videos WHERE id=?',(video_id,)).fetchone()
    if not video: conn.close(); abort(404)
    comments = conn.execute('''SELECT c.id,c.content,c.created_at,c.user_id,u.username,u.avatar
                              FROM comments c JOIN users u ON c.user_id=u.id
                              WHERE c.video_id=? ORDER BY c.id DESC''',(video_id,)).fetchall()
    conn.close()
    return render_template('video.html', video=dict(video), comments=[dict(c) for c in comments])

@app.route('/video/<int:video_id>/comment', methods=['POST'])
def add_comment(video_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login'})
    content = request.form.get('content','').strip()
    if not content: return jsonify({'success':False,'error':'Comentário vazio'})
    conn = get_db()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO comments (video_id,user_id,content,created_at) VALUES (?,?,?,?)',
                 (video_id,session['user_id'],content,now))
    conn.commit()
    username = session['username']
    conn.close()
    return jsonify({'success':True,'username':username,'content':content,'created_at':now})

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session: abort(403)
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE id=?',(comment_id,)).fetchone()
    if not comment or comment['user_id']!=session['user_id']: conn.close(); abort(403)
    conn.execute('DELETE FROM comments WHERE id=?',(comment_id,))
    conn.commit(); conn.close()
    return '',204

@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(comment_id):
    if 'user_id' not in session: abort(403)
    content = request.form.get('content','').strip()
    if not content: abort(400)
    conn = get_db()
    comment = conn.execute('SELECT * FROM comments WHERE id=?',(comment_id,)).fetchone()
    if not comment or comment['user_id']!=session['user_id']: conn.close(); abort(403)
    conn.execute('UPDATE comments SET content=? WHERE id=?',(content,comment_id))
    conn.commit(); conn.close()
    return '',204

@app.route('/user/<int:user_id>/block', methods=['POST'])
def block_user(user_id):
    if 'user_id' not in session or session['user_id']==user_id: abort(403)
    conn = get_db()
    exists = conn.execute('SELECT * FROM blocks WHERE blocker_id=? AND blocked_id=?',(session['user_id'],user_id)).fetchone()
    if not exists: conn.execute('INSERT INTO blocks (blocker_id,blocked_id) VALUES (?,?)',(session['user_id'],user_id))
    conn.commit(); conn.close()
    return '',204

@app.route('/user/<int:user_id>/unblock', methods=['POST'])
def unblock_user(user_id):
    if 'user_id' not in session: abort(403)
    conn = get_db()
    conn.execute('DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?',(session['user_id'],user_id))
    conn.commit(); conn.close()
    return '',204

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    if not user: conn.close(); abort(404)
    blocked = False
    if 'user_id' in session and session['user_id']!=user_id:
        exists = conn.execute('SELECT * FROM blocks WHERE blocker_id=? AND blocked_id=?',(session['user_id'],user_id)).fetchone()
        if exists: blocked = True
    conn.close()
    return render_template('user.html', user=dict(user), blocked=blocked)

# --- Criar pastas static/videos e static/avatars ---
os.makedirs(os.path.join(APP_DIR,'static','videos'),exist_ok=True)
os.makedirs(os.path.join(APP_DIR,'static','avatars'),exist_ok=True)

# --- Rodar app ---
if __name__=='__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)
