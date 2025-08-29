from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, FloatField, SubmitField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, ValidationError
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
import os
import bcrypt
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'changeme')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
csrf = CSRFProtect(app)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# WTForms
class RegisterForm(FlaskForm):
    username = StringField('닉네임', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('이메일', validators=[DataRequired(), Email()])
    height = IntegerField('키', validators=[DataRequired(), NumberRange(min=100, max=250)])
    target_weight = FloatField('목표 몸무게', validators=[DataRequired(), NumberRange(min=20, max=300)])
    password = PasswordField('비밀번호', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('비밀번호 확인', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('회원가입')

class LoginForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(), Email()])
    password = PasswordField('비밀번호', validators=[DataRequired()])
    submit = SubmitField('로그인')

class WeightForm(FlaskForm):
    weight = FloatField('몸무게', validators=[DataRequired(), NumberRange(min=20, max=300)])
    submit = SubmitField('저장')

# 유저 정보 가져오기
def get_user(user_id):
    res = supabase.table('users').select('*').eq('id', user_id).single().execute()
    return res.data if res.data else None

def get_user_by_email(email):
    res = supabase.table('users').select('*').eq('email', email).limit(1).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if get_user_by_email(form.email.data):
            flash('이미 등록된 이메일입니다.')
            return render_template('register.html', form=form)
        hashed = generate_password_hash(form.password.data)
        user = {
            'username': form.username.data,
            'email': form.email.data,
            'height': form.height.data,
            'target_weight': form.target_weight.data,
            'password': hashed
        }
        res = supabase.table('users').insert(user).execute()
        if res.data:
            flash('회원가입 성공! 로그인 해주세요.')
            return redirect(url_for('login'))
        else:
            flash('회원가입 실패. 다시 시도해주세요.')
    return render_template('register.html', form=form)

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_email(form.email.data)
        if user and check_password_hash(user['password'], form.password.data):
            session['user_id'] = user['id']
            flash('로그인 성공!')
            return redirect(url_for('index'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html', form=form)

# 로그아웃
@app.route('/logout')
def logout():
    session.clear()
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))

# 대시보드
@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = get_user(session['user_id'])
    # 몸무게 기록
    recs = supabase.table('weight_records').select('*').eq('user_id', user['id']).order('date', desc=True).execute().data or []
    latest = recs[0]['weight'] if recs else None
    # 목표 진행률
    progress = 0
    if recs and user['target_weight']:
        start = recs[-1]['weight']
        now = recs[0]['weight']
        target = user['target_weight']
        progress = int(100 * abs(now - start) / abs(target - start)) if start != target else 100
    # BMI
    bmi = None
    bmi_status = ''
    if latest and user['height']:
        h = user['height'] / 100
        bmi = round(latest / (h*h), 1)
        if bmi < 18.5:
            bmi_status = '저체중'
        elif bmi < 23:
            bmi_status = '정상'
        elif bmi < 25:
            bmi_status = '과체중'
        else:
            bmi_status = '비만'
    # 그래프 데이터
    chart_labels = [r['date'] for r in recs[::-1]]
    chart_data = [r['weight'] for r in recs[::-1]]
    # 통계
    week_ago = (datetime.now().date() - pd.Timedelta(days=7)).isoformat()
    month_ago = (datetime.now().date() - pd.Timedelta(days=30)).isoformat()
    week_start = [r['weight'] for r in recs if r['date'] <= week_ago]
    month_start = [r['weight'] for r in recs if r['date'] <= month_ago]
    week_change = latest - week_start[-1] if week_start else 0
    month_change = latest - month_start[-1] if month_start else 0
    # 메모
    memos = [{'date': r['date'], 'memo': r['memo']} for r in recs if r.get('memo')]
    form = WeightForm()
    return render_template('index.html',
        target_weight=user['target_weight'],
        progress=progress,
        bmi=bmi,
        bmi_status=bmi_status,
        latest_weight=latest,
        chart_labels=chart_labels,
        chart_data=chart_data,
        week_change=week_change,
        month_change=month_change,
        memos=memos,
        form=form)

# 몸무게 기록 추가
@app.route('/add_weight', methods=['POST'])
def add_weight():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    form = WeightForm()
    if form.validate_on_submit():
        weight = form.weight.data
        today = datetime.now().date().isoformat()
        memo = request.form.get('memo', '')
        # 이미 오늘 기록이 있으면 수정
        res = supabase.table('weight_records').select('*').eq('user_id', session['user_id']).eq('date', today).execute()
        recs = res.data or []
        if recs:
            rec = recs[0]
            supabase.table('weight_records').update({'weight': weight, 'memo': memo}).eq('id', rec['id']).execute()
            flash('오늘 기록이 수정되었습니다.')
        else:
            supabase.table('weight_records').insert({'user_id': session['user_id'], 'weight': weight, 'date': today, 'memo': memo}).execute()
            flash('몸무게가 기록되었습니다.')
        return redirect(url_for('index'))
    else:
        flash('유효한 몸무게를 입력하세요.')
        return redirect(url_for('index'))

# 몸무게 기록 내역
@app.route('/history')
def history():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    recs = supabase.table('weight_records').select('*').eq('user_id', session['user_id']).order('date', desc=True).execute().data or []
    return render_template('weight_history.html', records=recs)

# 몸무게 기록 수정
@app.route('/edit_weight/<int:rec_id>', methods=['POST'])
def edit_weight(rec_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    weight = request.form.get('weight', type=float)
    memo = request.form.get('memo', '')
    if not weight or weight < 20 or weight > 300:
        flash('유효한 몸무게를 입력하세요.')
        return redirect(url_for('history'))
    supabase.table('weight_records').update({'weight': weight, 'memo': memo}).eq('id', rec_id).execute()
    flash('기록이 수정되었습니다.')
    return redirect(url_for('history'))

# 몸무게 기록 삭제
@app.route('/delete_weight/<int:rec_id>', methods=['POST'])
def delete_weight(rec_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    supabase.table('weight_records').delete().eq('id', rec_id).execute()
    flash('기록이 삭제되었습니다.')
    return redirect(url_for('history'))

# 메모 추가
@app.route('/add_memo', methods=['POST'])
def add_memo():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    memo = request.form.get('memo', '')
    today = datetime.now().date().isoformat()
    res = supabase.table('weight_records').select('*').eq('user_id', session['user_id']).eq('date', today).execute()
    recs = res.data or []
    if recs:
        rec = recs[0]
        supabase.table('weight_records').update({'memo': memo}).eq('id', rec['id']).execute()
        flash('메모가 저장되었습니다.')
    else:
        supabase.table('weight_records').insert({'user_id': session['user_id'], 'weight': 0, 'date': today, 'memo': memo}).execute()
        flash('메모가 저장되었습니다.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
