# 몸무게 관리 웹앱 (Flask + Supabase)

## 소개
- Flask, Supabase, Bootstrap 5, Chart.js 기반의 미니멀한 몸무게 관리 웹앱입니다.
- 회원가입/로그인, 몸무게 기록, 목표/진행률, BMI, 통계, 메모, 반응형 UI 제공

## 주요 기능
- 사용자 회원가입/로그인 (비밀번호 해싱, 세션, CSRF 보호)
- 일일 몸무게 기록 입력/수정/삭제
- 몸무게 변화 그래프 (Chart.js)
- 목표 몸무게 설정 및 진행률 표시
- BMI 자동 계산 및 건강 상태 표시
- 주간/월간 몸무게 변화 통계
- 간단한 메모 기능 (운동, 식단 등)
- 모바일 최적화

## 데이터베이스 구조 (Supabase)
- `users`: id, username, email, height, target_weight
- `weight_records`: id, user_id, weight, date, memo

## 환경변수 (.env)
- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_KEY`: Supabase 서비스 키
- `SECRET_KEY`: Flask 시크릿키

## 실행 방법
```bash
pip install -r requirements.txt
cp .env.example .env # 환경변수 입력
python app.py
```

## Railway 배포
- `Procfile` 포함 (web: gunicorn app:app)
- 환경변수는 Railway 대시보드에서 설정

## 라이선스
MIT
