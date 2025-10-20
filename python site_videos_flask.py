from flask import Flask, request, redirect, url_for, session, flash, abort, jsonify, render_template
from jinja2 import DictLoader
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# --- Configurações ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'database.db')
AVATAR_FOLDER = os.path.join(APP_DIR, 'static', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = 'troque_esta_chave_para_uma_secreta_e_complexa'
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(os.path.join(APP_DIR,'static','videos'), exist_ok=True)

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
body {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width:1000px; margin:0 auto; padding:20px; background:#f0f2f5; color:#333;}
header {display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;}
nav a {margin-left:12px; text-decoration:none; color:#0b6cff;}
.video-card {background:#fff; padding:16px; border-radius:12px; box-shadow:0 3px 10px rgba(0,0,0,0.1); margin-bottom:16px; transition: transform 0.2s;}
.video-card:hover {transform: translateY(-2px);}
.comment {border-top:1px solid #eee; padding:12px 0;}
.comment small {color:#666;}
form textarea {width:100%; height:80px; padding:8px; border-radius:6px; border:1px solid #ccc; resize: vertical;}
.btn {display:inline-block; padding:10px 16px; border-radius:6px; background:#0b6cff; color:#fff; text-decoration:none; border:none; cursor:pointer; transition: background 0.2s;}
.btn:hover {background:#0951d4;}
.login-box {max-width:360px; margin:40px auto; background:#fff; padding:24px; border-radius:12px; box-shadow:0 3px 10px rgba(0,0,0,0.1);}
.meta {color:#666; font-size:90%;}
#comment-list .comment {transition: background 0.3s;}
#comment-list .comment:nth-child(odd) {background:#f9f9f9;}
.avatar {width:50px; height:50px; border-radius:50%; vertical-align:middle; margin-right:12px; object-fit:cover; border:2px solid #0b6cff; box-shadow:0 2px 6px rgba(0,0,0,0.2); transition: transform 0.2s;}
.avatar:hover {transform: scale(1.1);}
</style>
<script>
function submitComment(event, videoId){
    event.preventDefault();
    const textarea = document.querySelector('#comment-textarea');
    const content = textarea.value.trim();
    if(!content) return alert('Comentário vazio!');
    fetch('/video/' + videoId + '/comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({content: content})
    })
    .then(res => res.json())
    .then(data => {
        if(data.success){
            const list = document.querySelector('#comment-list');
            const newComment = document.createElement('div');
            newComment.className = 'comment';
            newComment.dataset.id = data.comment_id;
            newComment.innerHTML = `<a href="/user/${data.user_id}"><img src="/static/avatars/${data.avatar}" class="avatar"></a><strong>${data.username}</strong> <small>— ${data.created_at}</small>
            <p class="content">${data.content}</p>
            <button class="btn edit-comment">Editar</button>
            <button class="btn delete-comment">Deletar</button>`;
            list.prepend(newComment);
            textarea.value = '';
        } else {
            alert(data.error);
        }
    })
    .catch(err => console.error(err));
}

document.addEventListener('click', function(e){
    const target = e.target;
    const commentDiv = target.closest('.comment');
    if(commentDiv){
        const commentId = commentDiv.dataset.id;

        // Editar comentário
        if(target.classList.contains('edit-comment')){
            const p = commentDiv.querySelector('.content');
            const newText = prompt('Edite seu comentário:', p.textContent);
            if(!newText) return;
            fetch('/comment/' + commentId + '/edit', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({content:newText})
            }).then(res=>res.json()).then(data=>{
                if(data.success) p.textContent = data.content;
                else alert(data.error);
            });
        }

        // Deletar comentário
        if(target.classList.contains('delete-comment')){
            if(!confirm('Deseja deletar este comentário?')) return;
            fetch('/comment/' + commentId + '/delete', {method:'POST'})
            .then(res=>res.json()).then(data=>{
                if(data.success) commentDiv.remove();
                else alert(data.error);
            });
        }

        // Bloquear usuário
        if(target.classList.contains('block-user')){
            const userId = target.dataset.userId;
            if(!confirm('Deseja bloquear este usuário?')) return;
            fetch('/user/' + userId + '/block', {method:'POST'})
            .then(res=>res.json()).then(data=>{
                if(data.success) commentDiv.remove();
                else alert(data.error);
            });
        }
    }

    // Desbloquear usuário na página de bloqueados
    if(target.classList.contains('unblock-btn')){
        const blockId = target.dataset.id;
        if(!confirm('Deseja desbloquear este usuário?')) return;
        fetch('/unblock/' + blockId, {method:'POST'})
        .then(res=>res.json()).then(data=>{
            if(data.success) target.closest('li').remove();
            else alert(data.error);
        });
    }
});
</script>
</head>
<body>
<header>
<h1><a href="/">Site de Filmes</a></h1>
<nav>
{% if 'user_id' in session %}
{% if session.get('avatar') %}
<a href="{{ url_for('user_profile', user_id=session['user_id']) }}">
<img src="{{ url_for('static', filename='avatars/' + session.get('avatar')) }}" class="avatar" alt="Avatar">
</a>
{% endif %}
Olá, {{ session.get('username') }}
<a href="{{ url_for('logout') }}">Sair</a>
<a href="{{ url_for('upload_avatar') }}">Alterar Avatar</a>
<a href="{{ url_for('blocked_users_page') }}">Usuários Bloqueados</a>
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
{% for m in messages %}
<li>{{ m }}</li>
{% endfor %}
</ul>
{% endif %}
{% endwith %}
{% block content %}{% endblock %}
</main>
</body>
</html>
''',

'login.html': '''{% extends 'base.html' %}{% block content %}
<div class="login-box">
<h2>Entrar</h2>
<form method="post">
<label>Usuário<br><input name="username" required></label><br><br>
<label>Senha<br><input type="password" name="password" required></label><br><br>
<button class="btn" type="submit">Entrar</button>
</form>
<p>Não tem conta? <a href="{{ url_for('register') }}">Registre-se</a></p>
</div>
{% endblock %}''',

'register.html': '''{% extends 'base.html' %}{% block content %}
<div class="login-box">
<h2>Registrar</h2>
<form method="post">
<label>Usuário<br><input name="username" required></label><br><br>
<label>Senha<br><input type="password" name="password" required></label><br><br>
<button class="btn" type="submit">Criar conta</button>
</form>
</div>
{% endblock %}''',

'upload_avatar.html': '''{% extends 'base.html' %}{% block content %}
<div class="login-box">
<h2>Alterar Avatar</h2>
<form method="post" enctype="multipart/form-data">
<input type="file" name="avatar" accept="image/*" required><br><br>
<button class="btn" type="submit">Enviar Avatar</button>
</form>
</div>
{% endblock %}''',

'index.html': '''{% extends 'base.html' %}{% block content %}
<h2>Vídeos</h2>
{% for v in videos %}
<div class="video-card">
<h3><a href="{{ url_for('video_page', video_id=v['id']) }}">{{ v['title'] }}</a></h3>
<p class="meta">{{ v['description'] }}</p>
<p><a class="btn" href="{{ url_for('video_page', video_id=v['id']) }}">Ver</a></p>
</div>
{% else %}<p>Nenhum vídeo cadastrado.</p>{% endfor %}
{% endblock %}''',

'video.html': '''{% extends 'base.html' %}{% block content %}
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
<form onsubmit="submitComment(event, {{ video['id'] }})">
<textarea id="comment-textarea" required placeholder="Escreva seu comentário..."></textarea>
<button class="btn" type="submit">Comentar</button>
</form>
{% else %}
<p>Você precisa <a href="{{ url_for('login') }}">entrar</a> para comentar.</p>
{% endif %}

<div id="comment-list" style="margin-top:12px">
{% for c in comments %}
<div class="comment" data-id="{{ c['id'] }}">
{% if c.avatar %}
<a href="{{ url_for('user_profile', user_id=c.user_id) }}">
<img src="{{ url_for('static', filename='avatars/' + c.avatar) }}" class="avatar">
</a>
{% endif %}
<strong>{{ c['username'] }}</strong> <small>— {{ c['created_at'] }}</small>
<p class="content">{{ c['content'] }}</p>
{% if 'user_id' in session and session['user_id']==c['user_id'] %}
<button class="btn edit-comment">Editar</button>
<button class="btn delete-comment">Deletar</button>
{% endif %}
{% if 'user_id' in session and session['user_id']!=c['user_id'] %}
<button class="btn block-user" data-user-id="{{ c['user_id'] }}">Bloquear Usuário</button>
{% endif %}
</div>
{% else %}<p>Seja o primeiro a comentar.</p>{% endfor %}
</div>
</section>
{% endblock %}''',

'user_profile.html': '''{% extends 'base.html' %}{% block content %}
<h2>Perfil de {{ user.username }}</h2>
{% if user.avatar %}
<img src="{{ url_for('static', filename='avatars/' + user.avatar) }}" class="avatar" style="width:100px;height:100px;">
{% endif %}
<h3>Comentários feitos</h3>
{% if comments %}
<ul>
{% for c in comments %}
<li>
Em <a href="{{ url_for('video_page', video_id=c.video_id) }}">{{ c.video_title }}</a>: {{ c.content }} <small>— {{ c.created_at }}</small>
</li>
{% endfor %}
</ul>
{% else %}
<p>Este usuário não comentou ainda.</p>
{% endif %}
{% endblock %}''',

'blocked_users.html': '''{% extends 'base.html' %}{% block content %}
<h2>Usuários Bloqueados</h2>
{% if blocked %}
<ul>
{% for u in blocked %}
<li style="margin-bottom:12px;">
{% if u.avatar %}
<img src="{{ url_for('static', filename='avatars/' + u.avatar) }}" class="avatar">
{% endif %}
{{ u.username }}
<button class="btn unblock-btn" data-id="{{ u.block_id }}">Desbloquear</button>
</li>
{% endfor %}
</ul>
{% else %}<p>Você não bloqueou nenhum usuário.</p>{% endif %}
{% endblock %}'''
}

app.jinja_loader = DictLoader(TEMPLATES)

# --- Banco de dados ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        avatar TEXT
    );
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        filepath TEXT
    );
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(video_id) REFERENCES videos(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS blocked_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blocker_id INTEGER NOT NULL,
        blocked_id INTEGER NOT NULL,
        FOREIGN KEY(blocker_id) REFERENCES users(id),
        FOREIGN KEY(blocked_id) REFERENCES users(id)
    );
    ''')
    if not conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]:
        cur.executemany('INSERT INTO videos (title,description,filepath) VALUES (?,?,?)', [
            ('Vídeo Exemplo 1','Descrição do filme exemplo 1','static/videos/sample1.mp4'),
            ('Vídeo Exemplo 2','Descrição do filme exemplo 2','static/videos/sample2.mp4')
        ])
    conn.commit(); conn.close()

init_db()

# --- Helpers ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# --- Rotas principais ---
@app.route('/')
def index():
    conn = get_db()
    videos = conn.execute('SELECT * FROM videos ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', videos=[dict(v) for v in videos])

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
            conn.execute('INSERT INTO users (username,password_hash) VALUES (?,?)', (username,pw_hash))
            conn.commit()
            flash('Conta criada. Faça login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Nome de usuário já existe'); return redirect(url_for('register'))
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['avatar'] = user['avatar']
            flash('Logado com sucesso')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos'); return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu')
    return redirect(url_for('index'))

# --- Upload avatar ---
@app.route('/upload_avatar', methods=['GET','POST'])
def upload_avatar():
    if 'user_id' not in session:
        flash('Faça login para alterar avatar'); return redirect(url_for('login'))
    if request.method=='POST':
        if 'avatar' not in request.files:
            flash('Nenhum arquivo enviado'); return redirect(request.url)
        file = request.files['avatar']
        if file.filename=='' or not allowed_file(file.filename):
            flash('Arquivo inválido'); return redirect(request.url)
        filename = secure_filename(f"{session['user_id']}_{file.filename}")
        file.save(os.path.join(AVATAR_FOLDER, filename))
        conn = get_db()
        conn.execute('UPDATE users SET avatar=? WHERE id=?',(filename,session['user_id']))
        conn.commit(); conn.close()
        session['avatar'] = filename
        flash('Avatar atualizado')
        return redirect(url_for('index'))
    return render_template('upload_avatar.html')

# --- Página do vídeo ---
@app.route('/video/<int:video_id>')
def video_page(video_id):
    conn = get_db()
    video = conn.execute('SELECT * FROM videos WHERE id=?',(video_id,)).fetchone()
    if not video: conn.close(); abort(404)
    blocked_ids = [r['blocked_id'] for r in conn.execute('SELECT blocked_id FROM blocked_users WHERE blocker_id=?',(session.get('user_id',0),)).fetchall()]
    if not blocked_ids: blocked_ids=[0]
    comments = conn.execute(f'''
        SELECT c.id, c.content, c.created_at, u.username, u.id as user_id, u.avatar
        FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.video_id=? AND u.id NOT IN ({','.join(['?']*len(blocked_ids))})
        ORDER BY c.id DESC
    ''',(video_id,*blocked_ids)).fetchall()
    conn.close()
    return render_template('video.html', video=dict(video), comments=[dict(c) for c in comments])

# --- Comentários AJAX ---
@app.route('/video/<int:video_id>/comment', methods=['POST'])
def add_comment(video_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login para comentar'})
    data = request.get_json(); content = data.get('content','').strip()
    if not content: return jsonify({'success':False,'error':'Comentário vazio'})
    conn = get_db(); now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.execute('INSERT INTO comments (video_id,user_id,content,created_at) VALUES (?,?,?,?)',
                       (video_id, session['user_id'], content, now))
    comment_id = cur.lastrowid; conn.close()
    return jsonify({'success':True,'username':session['username'],'content':content,'created_at':now,'comment_id':comment_id,'user_id':session['user_id'],'avatar':session.get('avatar','')})

@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(comment_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login'})
    data = request.get_json(); new_content = data.get('content','').strip()
    if not new_content: return jsonify({'success':False,'error':'Comentário vazio'})
    conn=get_db()
    comment=conn.execute('SELECT * FROM comments WHERE id=?',(comment_id,)).fetchone()
    if not comment or comment['user_id']!=session['user_id']: conn.close(); return jsonify({'success':False,'error':'Não pode editar'})
    conn.execute('UPDATE comments SET content=? WHERE id=?',(new_content,comment_id))
    conn.commit(); conn.close()
    return jsonify({'success':True,'content':new_content})

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login'})
    conn=get_db()
    comment=conn.execute('SELECT * FROM comments WHERE id=?',(comment_id,)).fetchone()
    if not comment or comment['user_id']!=session['user_id']: conn.close(); return jsonify({'success':False,'error':'Não pode deletar'})
    conn.execute('DELETE FROM comments WHERE id=?',(comment_id,))
    conn.commit(); conn.close()
    return jsonify({'success':True})

# --- Bloquear usuário ---
@app.route('/user/<int:user_id>/block', methods=['POST'])
def block_user(user_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login'})
    if user_id==session['user_id']: return jsonify({'success':False,'error':'Não pode bloquear você mesmo'})
    conn=get_db()
    exists = conn.execute('SELECT * FROM blocked_users WHERE blocker_id=? AND blocked_id=?',(session['user_id'],user_id)).fetchone()
    if exists: conn.close(); return jsonify({'success':False,'error':'Usuário já bloqueado'})
    conn.execute('INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (?,?)',(session['user_id'],user_id))
    conn.commit(); conn.close()
    return jsonify({'success':True})

# --- Desbloquear usuário ---
@app.route('/unblock/<int:block_id>', methods=['POST'])
def unblock_user(block_id):
    if 'user_id' not in session: return jsonify({'success':False,'error':'Faça login'})
    conn=get_db()
    deleted = conn.execute('DELETE FROM blocked_users WHERE id=? AND blocker_id=?',(block_id,session['user_id']))
    conn.commit(); conn.close()
    if deleted.rowcount: return jsonify({'success':True})
    else: return jsonify({'success':False,'error':'Não foi possível desbloquear'})

@app.route('/blocked_users')
def blocked_users_page():
    if 'user_id' not in session: flash('Faça login'); return redirect(url_for('login'))
    conn=get_db()
    blocked = conn.execute('''
        SELECT bu.id as block_id, u.username, u.avatar
        FROM blocked_users bu
        JOIN users u ON bu.blocked_id = u.id
        WHERE bu.blocker_id=?
    ''',(session['user_id'],)).fetchall()
    conn.close()
    return render_template('blocked_users.html', blocked=[dict(b) for b in blocked])

# --- Perfil do usuário ---
@app.route('/user/<int:user_id>')
def user_profile(user_id):
    conn = get_db()
    user = conn.execute('SELECT id, username, avatar FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: conn.close(); abort(404)
    comments = conn.execute('''
        SELECT c.id, c.content, c.created_at, v.title AS video_title, v.id AS video_id
        FROM comments c
        JOIN videos v ON c.video_id = v.id
        WHERE c.user_id = ?
        ORDER BY c.id DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return render_template('user_profile.html', user=dict(user), comments=[dict(c) for c in comments])

# --- Rodar app ---
if __name__=='__main__':
    app.run(debug=True)
