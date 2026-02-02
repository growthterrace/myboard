import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
from datetime import datetime
import json

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import folium

import psycopg2
from psycopg2.extras import DictCursor


# [그래프 한글 깨짐 방지 설정]
plt.rc('font', family='Malgun Gothic') 
plt.switch_backend('Agg') # 중요! 웹 서버에서 그래프 그릴 때 필수 설정


# 로컬 환경에서는 .env를 읽고, Azure에서는 패스.

if os.path.exists('.env'):

    load_dotenv()

app = Flask(__name__)

app.secret_key = os.urandom(24)


# 데이터베이스 연결 함수

def get_db_connection():

    conn = psycopg2.connect(

        host=os.getenv('DB_HOST'),

        port=os.getenv('DB_PORT'),

        dbname=os.getenv('DB_NAME'),

        user=os.getenv('DB_USER'),

        password=os.getenv('DB_PASSWORD'),

        #sslmode='require' #Azure를 위해 반드시 추가

    )

    print('get_db_connection', conn)

    conn.autocommit = True

    return conn


@app.route('/')

def index():

    # 1. 데이터 베이스에 접속

    conn = get_db_connection()

    print('get_db_connection', conn)

    cursor = conn.cursor(cursor_factory=DictCursor)

    # 2. SELECT

    cursor.execute("SELECT id, title, author, created_at, view_count, like_count FROM board.posts ORDER BY created_at DESC")

    posts = cursor.fetchall()

    cursor.close()

    conn.close()

    # 3. index.html 파일에 변수로 넘겨주기

    return render_template('index.html', posts = posts)


@app.route('/create/', methods=['GET'] )

def create_form():

    return render_template('create.html')


@app.route('/create/',methods=['POST']  )

def create_post():

    #1. 폼에 있는 정보들을 get

    title = request.form.get('title')

    author = request.form.get('author')

    content = request.form.get('content')


    if not title or not author or not content:

        flash('모든 필드를 똑바로 채워주세요!!!!')

        return redirect(url_for('create_form'))


    # 1. 데이터 베이스에 접속

    conn = get_db_connection()

    cursor = conn.cursor(cursor_factory=DictCursor)

    # 2. INSERT

    cursor.execute("INSERT INTO board.posts (title, content, author) VALUES (%s, %s, %s) RETURNING id", (title,author,content ))

    post_id = cursor.fetchone()[0]

    cursor.close()

    conn.close()

    flash('게시글이 성공적으로 등록되었음')

    return redirect(url_for('view_post', post_id=post_id))


@app.route('/post/<int:post_id>')

def view_post(post_id):

    conn = get_db_connection()

    cursor = conn.cursor(cursor_factory=DictCursor)


    cursor.execute('UPDATE board.posts SET view_count = view_count + 1 WHERE id = %s', (post_id,))


    cursor.execute('SELECT * FROM board.posts WHERE id = %s', (post_id,))

    post = cursor.fetchone()


    if post is None:

        cursor.close()

        conn.close()

        flash('게시글을 찾을 수 없습니다.')

        return redirect(url_for('index'))


    cursor.execute('SELECT * FROM board.comments WHERE post_id = %s ORDER BY created_at', (post_id,))

    comments = cursor.fetchall()


    cursor.close()

    conn.close()


    user_ip = request.remote_addr

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))

    liked = cursor.fetchone()[0] > 0

    cursor.close()

    conn.close()


    return render_template('view.html', post=post, comments=comments, liked=liked)


@app.route('/edit/<int:post_id>', methods=['GET'])

def edit_form(post_id):

    conn = get_db_connection()

    cursor = conn.cursor(cursor_factory=DictCursor)

    cursor.execute('SELECT * FROM board.posts WHERE id = %s', (post_id,))

    post = cursor.fetchone()

    cursor.close()

    conn.close()


    if post is None:

        flash('게시글을 찾을 수 없습니다.')

        return redirect(url_for('index'))


    return render_template('edit.html', post=post)


@app.route('/edit/<int:post_id>', methods=['POST'])

def edit_post(post_id):

    title = request.form.get('title')

    content = request.form.get('content')


    if not title or not content:

        flash('제목과 내용을 모두 입력해주세요.')

        return redirect(url_for('edit_form', post_id=post_id))


    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(

        'UPDATE board.posts SET title = %s, content = %s, updated_at = %s WHERE id = %s',

        (title, content, datetime.now(), post_id)

    )

    cursor.close()

    conn.close()


    flash('게시글이 성공적으로 수정되었습니다.')

    return redirect(url_for('view_post', post_id=post_id))


@app.route('/delete/<int:post_id>', methods=['POST'])

def delete_post(post_id):

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute('DELETE FROM board.posts WHERE id = %s', (post_id,))

    cursor.close()

    conn.close()


    flash('게시글이 성공적으로 삭제되었습니다.')

    return redirect(url_for('index'))


@app.route('/post/comment/<int:post_id>', methods=['POST'])

def add_comment(post_id):

    author = request.form.get('author')

    content = request.form.get('content')


    if not author or not content:

        flash('작성자와 내용을 모두 입력해주세요.')

        return redirect(url_for('view_post', post_id=post_id))


    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(

        'INSERT INTO board.comments (post_id, author, content) VALUES (%s, %s, %s)',

        (post_id, author, content)

    )

    cursor.close()

    conn.close()


    flash('댓글이 등록되었습니다.')

    return redirect(url_for('view_post', post_id=post_id))


@app.route('/post/like/<int:post_id>', methods=['POST'])

def like_post(post_id):

    user_ip = request.remote_addr


    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))

    already_liked = cursor.fetchone()[0] > 0


    if already_liked:

        cursor.execute('DELETE FROM board.likes WHERE post_id = %s AND user_ip = %s', (post_id, user_ip))

        cursor.execute('UPDATE board.posts SET like_count = like_count - 1 WHERE id = %s', (post_id,))

        message = '좋아요가 취소되었습니다.'

    else:

        cursor.execute('INSERT INTO board.likes (post_id, user_ip) VALUES (%s, %s)', (post_id, user_ip))

        cursor.execute('UPDATE board.posts SET like_count = like_count + 1 WHERE id = %s', (post_id,))

        message = '좋아요가 등록되었습니다.'


    cursor.close()

    conn.close()   

    flash(message)

    return redirect(url_for('view_post', post_id=post_id))


if __name__ == '__main__':

    app.run(debug=True)

# [새로운 기능] FMS 통합 데이터 조회 페이지
@app.route('/fms')
def fms_dashboard():
    # 1. DB 연결
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # 2. 데이터 가져오기
    query = """
        SELECT c.chick_no, c.breeds, c.gender, c.farm, p.raw_weight
        FROM fms.chick_info c
        LEFT JOIN fms.prod_result p ON c.chick_no = p.chick_no
        ORDER BY c.chick_no ASC;
    """
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # 3. 그래프 그리기 (데이터가 있을 때만!)
    plot_url = None # 초기화
    if rows:
        try:
            # 데이터프레임 변환
            df = pd.DataFrame(rows, columns=['chick_no', 'breeds', 'gender', 'farm', 'raw_weight'])
            
            # 그림 그리기
            img = io.BytesIO()
            plt.figure(figsize=(10, 5))
            sns.barplot(data=df, x='breeds', y='raw_weight', ci=None, palette='viridis')
            plt.title('품종별 평균 무게')
            plt.grid(True, alpha=0.3)
            
            # 저장 및 변환
            plt.savefig(img, format='png')
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode()
            plt.close()
        except Exception as e:
            print("그래프 에러:", e) # 에러나면 터미널에 알려줘

    # 4. HTML로 데이터와 그림주소 보내기
    return render_template('fms.html', data=rows, plot_url=plot_url)

@app.route('/fms_result')
def fms_result():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # 1. 데이터 가져오기
    query = """
        SELECT c.chick_no, c.breeds, c.gender, c.farm, p.raw_weight, p.prod_date
        FROM fms.chick_info c
        LEFT JOIN fms.prod_result p ON c.chick_no = p.chick_no
        ORDER BY c.chick_no ASC;
    """
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return "데이터가 없습니다."

    # 2. 데이터프레임 변환
    df = pd.DataFrame(rows, columns=['chick_no', 'breeds', 'gender', 'farm', 'raw_weight', 'prod_date'])
    
    # ---------------------------------------------------------
    # [1] KPI 지표 계산 (HTML에 표시할 숫자들)
    # ---------------------------------------------------------
    target_weight = 1000  # 목표 중량 1000g
    df['raw_weight'] = df['raw_weight'].fillna(0) # 무게 없으면 0 처리
    
    total_count = len(df)
    pass_count = len(df[df['raw_weight'] >= target_weight]) # 정상
    # fail_count = total_count - pass_count # (필요시 사용)
    
    # 달성률 계산 (0으로 나누기 방지)
    pass_rate = round((pass_count / total_count) * 100, 1) if total_count > 0 else 0

    # ---------------------------------------------------------
    # [2] 그래프 그리기
    # ---------------------------------------------------------
    
    # (1) 품종 분포 (Pie Chart) -> HTML변수명: breed_plot
    img1 = io.BytesIO()
    plt.figure(figsize=(6, 6))
    breed_counts = df['breeds'].value_counts()
    plt.pie(breed_counts, labels=breed_counts.index, autopct='%1.1f%%', 
            colors=sns.color_palette('pastel'), startangle=90, wedgeprops=dict(width=0.6))
    plt.title('품종 점유율', fontsize=15, fontweight='bold')
    plt.tight_layout()
    plt.savefig(img1, format='png', transparent=True)
    img1.seek(0)
    breed_plot = base64.b64encode(img1.getvalue()).decode()
    plt.close()

    # (2) 농장별 성과 (Bar Chart) -> HTML변수명: farm_plot
    img2 = io.BytesIO()
    plt.figure(figsize=(8, 5))
    # 농장별 평균 무게 계산
    farm_avg = df.groupby('farm')['raw_weight'].mean().reset_index()
    sns.barplot(data=farm_avg, x='farm', y='raw_weight', palette='viridis')
    plt.title('농장별 평균 무게 (g)', fontsize=14, fontweight='bold')
    plt.axhline(target_weight, color='red', linestyle='--', label='목표(1kg)') # 목표선 추가
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(img2, format='png', transparent=True)
    img2.seek(0)
    farm_plot = base64.b64encode(img2.getvalue()).decode()
    plt.close()

    # (3) 지도 생성 -> HTML변수명: map_html
    farm_locations = {
        'A': [37.5665, 126.9780], 'B': [35.1796, 129.0756], 
        'C': [35.1595, 126.8526], 'D': [36.3504, 127.3845], 'E': [37.4563, 126.7052]
    }
    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles='cartodbpositron')
    
    for farm in df['farm'].unique():
        if farm in farm_locations:
            lat, lng = farm_locations[farm]
            count = len(df[df['farm'] == farm])
            # 농장 마커
            folium.CircleMarker(
                location=[lat, lng], radius=15, color='#3182f6', fill=True, fill_opacity=0.7,
                popup=f"<b>농장 {farm}</b><br>{count}마리"
            ).add_to(m)

    map_html = m._repr_html_()

    # ---------------------------------------------------------
    # [3] HTML로 데이터 배달
    # ---------------------------------------------------------
    return render_template('fms_result.html', 
                           data=rows, 
                           total_count=total_count,
                           pass_count=pass_count,
                           pass_rate=pass_rate,
                           breed_plot=breed_plot,
                           farm_plot=farm_plot,
                           map_html=map_html)