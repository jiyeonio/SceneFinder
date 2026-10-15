import React, { useState } from 'react';
import {
  ArrowLeft,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  User,
} from 'lucide-react';
import { API_BASE_URL } from '../services/searchApi';

interface AuthViewProps {
  onNavigateHome: () => void;
  onLoginSuccess: (user: { name: string; email: string }) => void;
}

export const AuthView: React.FC<AuthViewProps> = ({
  onNavigateHome,
  onLoginSuccess,
}) => {
  const [mode, setMode] = useState<'login' | 'signup'>('login');

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'signup' && !name.trim()) {
      setError('이름을 입력해주세요.');
      return;
    }

    if (!email.trim()) {
      setError('이메일을 입력해주세요.');
      return;
    }

    if (!password) {
      setError('비밀번호를 입력해주세요.');
      return;
    }

    if (mode === 'signup' && password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }

    // 회원가입: 실제 백엔드 API 사용
    if (mode === 'signup') {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/auth/signup`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              email: email.trim(),
              password,
              name: name.trim(),
            }),
          }
        );

        const data = await response.json();

        if (!response.ok) {
          setError(data.detail || '회원가입에 실패했습니다.');
          return;
        }

        alert('회원가입이 완료되었습니다. 로그인해주세요.');

        setMode('login');
        setError('');
        setPassword('');
        setPasswordConfirm('');
      } catch (error) {
        console.error('회원가입 API 오류:', error);
        setError('서버에 연결할 수 없습니다.');
      }

      return;
    }

    // 로그인: 실제 백엔드 API 사용
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/auth/login`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: email.trim(),
            password,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || '로그인에 실패했습니다.');
        return;
      }

      const loginEmail = data.email || email.trim();

      const user = {
        name: data.name || loginEmail.split('@')[0],
        email: loginEmail,
      };

      // 사용자 정보 저장
      localStorage.setItem(
        'scenefinder-user',
        JSON.stringify(user)
      );

      // 이후 즐겨찾기 API 인증에 사용할 토큰 저장
      localStorage.setItem(
        'scenefinder-access-token',
        data.access_token
      );

      localStorage.setItem(
        'scenefinder-refresh-token',
        data.refresh_token
      );

      onLoginSuccess(user);
    } catch (error) {
      console.error('로그인 API 오류:', error);
      setError('서버에 연결할 수 없습니다.');
    }
  };

  const changeMode = (nextMode: 'login' | 'signup') => {
    setMode(nextMode);
    setError('');
    setPassword('');
    setPasswordConfirm('');
  };

  return (
    <main className="flex-1 flex items-center justify-center px-4 py-12 bg-slate-50">
      <div className="w-full max-w-md">
        <button
          type="button"
          onClick={onNavigateHome}
          className="mb-5 flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          홈으로 돌아가기
        </button>

        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-7 sm:p-8">
          <div className="mb-7 text-center">
            <div className="inline-flex items-center justify-center px-3 py-1 mb-4 rounded-full bg-blue-50 text-blue-600 text-xs font-semibold">
              SceneFinder
            </div>

            <h1 className="text-2xl font-bold text-slate-900">
              {mode === 'login' ? '다시 만나서 반가워요!' : 'SceneFinder 시작하기'}
            </h1>

            <p className="mt-2 text-sm text-slate-500">
              {mode === 'login'
                ? '로그인하고 저장한 영상 구간을 다시 확인해보세요.'
                : '계정을 만들고 원하는 영상 구간을 저장해보세요.'}
            </p>
          </div>

          <div className="grid grid-cols-2 p-1 mb-6 bg-slate-100 rounded-xl">
            <button
              type="button"
              onClick={() => changeMode('login')}
              className={`py-2.5 rounded-lg text-sm font-semibold transition-all ${mode === 'login'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
                }`}
            >
              로그인
            </button>

            <button
              type="button"
              onClick={() => changeMode('signup')}
              className={`py-2.5 rounded-lg text-sm font-semibold transition-all ${mode === 'signup'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
                }`}
            >
              회원가입
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block mb-1.5 text-sm font-medium text-slate-700">
                  이름
                </label>

                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="이름을 입력해주세요"
                    className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm outline-none transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block mb-1.5 text-sm font-medium text-slate-700">
                이메일
              </label>

              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@email.com"
                  className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm outline-none transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </div>
            </div>

            <div>
              <label className="block mb-1.5 text-sm font-medium text-slate-700">
                비밀번호
              </label>

              <div className="relative">
                <LockKeyhole className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />

                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="비밀번호를 입력해주세요"
                  className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-11 text-sm outline-none transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  aria-label="비밀번호 보기"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {mode === 'signup' && (
              <div>
                <label className="block mb-1.5 text-sm font-medium text-slate-700">
                  비밀번호 확인
                </label>

                <div className="relative">
                  <LockKeyhole className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />

                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={passwordConfirm}
                    onChange={(e) => setPasswordConfirm(e.target.value)}
                    placeholder="비밀번호를 다시 입력해주세요"
                    className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm outline-none transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="w-full mt-2 rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
            >
              {mode === 'login' ? '로그인' : '가입하기'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {mode === 'login' ? '아직 계정이 없으신가요?' : '이미 계정이 있으신가요?'}{' '}
            <button
              type="button"
              onClick={() => changeMode(mode === 'login' ? 'signup' : 'login')}
              className="font-semibold text-blue-600 hover:text-blue-700"
            >
              {mode === 'login' ? '회원가입' : '로그인'}
            </button>
          </p>
        </div>
      </div>
    </main>
  );
};